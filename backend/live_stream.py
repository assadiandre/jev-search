"""Supervise a fresh search process; forward progress without storing a corpus."""
import asyncio
from pathlib import Path
import sys
import time
from backend.memory_guard import supervise


async def run_stream(search,root,query,key,options):
    search.started=time.perf_counter()
    search.stats.update(mode='streaming',scanComplete=False,sampled=0)
    async def forward(event):
        if event.get('type')=='billing':
            search.stats.update(event.get('stats',{}))
            return
        if event.get('type')=='results':
            stats={**event.get('stats',{}),'elapsed':time.perf_counter()-search.started}
            event={**event,'stats':stats}
            search.stats.update(stats)
            if 'hits' in event: search.hits={h['path']:h for h in event['hits']}
        await search.emit(event)
    if getattr(sys,'frozen',False): command=[sys.executable,'--stream-worker']
    else: command=[sys.executable,'-u',str(Path(__file__).with_name('server.py')),'--stream-worker']
    try:
        result=await supervise(command,{'root':str(root),'query':query,'key':key,'config':'streaming128',
            'options':{'mode':'streaming','includeGenerated':options.include_generated,
                       'readContents':options.read_contents,'concurrency':options.concurrency}},on_event=forward)
        search.stats.update(result.get('stats',{}))
        search.stats['workerPeakRSS']=result['memory_guard']['observed_peak_rss_bytes']
        if result.get('phase')!='complete':
            await search.update('partial',True,result.get('message','Search could not finish. Results found so far remain available.'))
        else:
            # Final worker event already contains ranked hits and coverage.
            await search.update('complete',True,result.get('message',''))
    except asyncio.CancelledError:
        if search.stats.get('activeRequests') or search.stats.get('requests',0)>search.stats.get('costReports',0)+search.stats.get('costUnreported',0):
            search.stats['billingIncomplete']=True
        await search.update('stopped',True,'Search stopped. Results found so far remain available.')
    except Exception:
        await search.update('error',True,'The streaming search could not finish. Try the search again.')
