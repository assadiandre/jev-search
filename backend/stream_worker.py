"""Isolated query process. API credentials only arrive over the private pipe."""
import asyncio
import json
from pathlib import Path
import sys
import time
import httpx
from backend import core
from backend.desktop_stream import DesktopBM25, apsw
from backend.fast import RetrievalMatcher


def send(message):
    sys.stdout.write(json.dumps(message,ensure_ascii=True,allow_nan=False)+'\n')
    sys.stdout.flush()


async def main():
    request=json.loads(sys.stdin.buffer.readline(65536))
    apsw.hard_heap_limit(128*1024*1024)
    root=Path(request['root'])
    query=request['query']
    options=core.Options.from_dict(request.get('options',{}))
    async def emit(event): send({'type':'event','event':event})
    search=core.Search(emit)
    search.started=time.perf_counter()
    search.matcher=RetrievalMatcher(query)
    search.threshold=0
    search.stats.update(mode='streaming',requestLimit=8,candidateLimit=128,scanComplete=False,sampled=0)
    original_classify=core.classify
    active=0
    async def observed(client,records,excerpts,query,stats):
        nonlocal active
        active+=1
        send({'type':'billing','stats':{**{k:stats.get(k,0) for k in ['cost','requests','costReports','costUnreported']},'activeRequests':active}})
        try: return await original_classify(client,records,excerpts,query,stats)
        finally:
            active-=1
            send({'type':'billing','stats':{**{k:stats.get(k,0) for k in ['cost','requests','costReports','costUnreported']},'activeRequests':active}})
    core.classify=observed
    def progress(stats):
        search.stats.update(stats)
        send({'type':'event','event':{'type':'results','phase':'scanning','stats':dict(search.stats),'matchCount':0,'message':''}})
    index=DesktopBM25(root,options,search.stop,progress)
    tasks=[]
    final_phase='complete'
    message=''
    try:
        await search.update('scanning',True)
        ranked=index.search(query,500)
        search.stats.update(index.stats)
        for position,(identifier,_) in enumerate(ranked):
            record=index.desktop_records[identifier]
            source='name' if search.matcher.score(record)>=.45 else 'content'
            search.hits[record.path]={**record.public(),'probability':None,'localScore':0,
                'matchSource':source,'excerpt':'','coverage':index.coverage[identifier], 'rank':len(ranked)-position}
        chosen=ranked[:128]
        search.stats['selected']=len(chosen)
        await search.update('thinking' if request.get('key') else 'scanning',True)
        records=[]
        excerpts=[]
        for identifier,_ in chosen:
            records.append(index.desktop_records[identifier])
            excerpts.append(index.compact(identifier,query))
        search.stats.update(retainedEvidenceBytes=index.evidence_retained_bytes,textBudgetBytes=500000)
        for record,(text,coverage) in zip(records,excerpts):
            search.hits[record.path].update(excerpt=text,coverage=coverage)
        index.close()
        if request.get('key') and records:
            semaphore=asyncio.Semaphore(min(4,options.concurrency))
            async with httpx.AsyncClient(headers={'Authorization':'Bearer '+request['key'],'Content-Type':'application/json','X-Title':'JEV SEARCH Streaming'},
                timeout=httpx.Timeout(25,connect=8),limits=httpx.Limits(max_connections=4,max_keepalive_connections=4)) as client:
                async def judge(start):
                    async with semaphore:
                        batch=records[start:start+32]; evidence=excerpts[start:start+32]
                        try:
                            scores,_=await core.classify(client,batch,evidence,query,search.stats)
                            search.stats['evaluated']+=len(batch)
                            for record,score,(text,coverage) in zip(batch,scores,evidence):
                                search.add_hit(record,score,text,coverage)
                        except core.APIError as error:
                            search.stats['failed']+=len(batch)
                            await emit({'type':'warning','message':str(error)})
                        finally:
                            send({'type':'billing','stats':{k:search.stats.get(k,0) for k in ['cost','requests','costReports','costUnreported']}})
                            await search.update('thinking')
                tasks=[asyncio.create_task(judge(i)) for i in range(0,len(records),32)]
                done,pending=await asyncio.wait(tasks,timeout=30)
                if pending:
                    search.stats['billingIncomplete']=True
                    final_phase='partial';message='JEV reached its time limit. Local matches remain available.'
                    for task in pending: task.cancel()
                outcomes=await asyncio.gather(*tasks,return_exceptions=True)
                if any(isinstance(value,Exception) for value in outcomes):
                    final_phase='partial';message='Some JEV checks could not finish. Local matches remain available.'
        else:
            message='Local streaming search complete. Load an OpenRouter key in Settings to enable JEV.' if not request.get('key') else ''
        if search.stats.get('failed'): final_phase='partial';message='Some candidates could not be checked by JEV. Local results are retained.'
        if index.stats['contentUnavailable']:
            message=(message+' '+str(index.stats['contentUnavailable'])+' files had unavailable or unsupported content; their names were searched.').strip()
        await search.update(final_phase,True,message)
        send({'type':'result','result':{'phase':final_phase,'stats':search.stats,'message':message}})
    except Exception:
        send({'type':'result','result':{'phase':'incomplete','stats':search.stats,
              'message':'Search could not finish within its resource limits or encountered an unreadable folder. Results found so far remain available.'}})
    finally:
        index.close()
        for task in tasks: task.cancel()
        if tasks: await asyncio.gather(*tasks,return_exceptions=True)
