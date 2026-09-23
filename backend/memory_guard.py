"""Parent-side RSS watchdog. SQLite limits belong in the isolated child only."""
import asyncio
import json
import time

MIB = 1024 * 1024
DEFAULT_SQLITE_MIB = 128
DEFAULT_WORKER_MIB = 256
DEFAULT_FILE_MIB = 16


async def supervise(command, payload, worker_mib=DEFAULT_WORKER_MIB, poll_seconds=.05, timeout_seconds=300, on_event=None):
    if not 1 <= worker_mib <= 4096:
        raise ValueError('Worker memory limit must be between 1 and 4096 MiB')
    started = time.perf_counter()
    process = await asyncio.create_subprocess_exec(*command, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=2*MIB)
    latest = {'cost':0, 'requests':0, 'costReports':0, 'costUnreported':0}
    result = None
    stderr = bytearray()
    peak_rss = 0
    failure = None
    observed_rss = False

    async def read_stdout():
        nonlocal result
        total = 0
        while line := await process.stdout.readline():
            if len(line) > 2 * MIB:
                raise RuntimeError('Worker output exceeded its buffer limit')
            message = json.loads(line)
            if message.get('type') == 'billing':
                latest.update(message['stats'])
                if on_event is not None: await on_event({'type':'billing','stats':dict(latest)})
            elif message.get('type') == 'event' and on_event is not None:
                event=message['event']
                stats=event.get('stats',{})
                latest.update({k:stats[k] for k in latest if k in stats})
                await on_event(event)
            elif message.get('type') == 'result': result = message['result']
            else: raise RuntimeError('Unexpected worker message')

    async def read_stderr():
        while chunk := await process.stderr.read(4096):
            if len(stderr) < 16384: stderr.extend(chunk[:16384-len(stderr)])

    readers = [asyncio.create_task(read_stdout()), asyncio.create_task(read_stderr())]
    try:
        process.stdin.write(json.dumps(payload).encode() + b'\n')
        await process.stdin.drain()
        process.stdin.close()
        while process.returncode is None:
            for task in readers:
                if task.done() and task.exception():
                    failure = ('worker_protocol_error', 'Search stopped because its worker output was invalid.')
            if time.perf_counter()-started > timeout_seconds:
                failure = ('worker_timeout', 'Search stopped because its worker exceeded the time limit.')
            if failure: break
            try:
                meter = await asyncio.create_subprocess_exec('/bin/ps','-o','rss=','-p',str(process.pid),
                    stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
                output,_ = await asyncio.wait_for(meter.communicate(),timeout=2)
                if output.strip():
                    rss = int(output.strip()) * 1024
                    observed_rss = True
                    peak_rss = max(peak_rss,rss)
                    if rss >= worker_mib * MIB:
                        failure = ('worker_memory_limit',f'Search stopped after the worker reached its {worker_mib} MiB memory threshold.')
                        break
                elif process.returncode is None:
                    try: await asyncio.wait_for(process.wait(),timeout=.1)
                    except asyncio.TimeoutError:
                        failure = ('memory_monitor_unavailable','Search stopped because worker memory could not be monitored.')
                        break
            except (OSError,ValueError,asyncio.TimeoutError):
                if 'meter' in locals() and meter.returncode is None:
                    meter.kill(); await meter.wait()
                failure = ('memory_monitor_unavailable','Search stopped because worker memory could not be monitored.')
                break
            await asyncio.sleep(poll_seconds)
        if failure and process.returncode is None:
            process.kill()
        await process.wait()
        outputs = await asyncio.gather(*readers,return_exceptions=True)
        if any(isinstance(o,Exception) for o in outputs) and not failure:
            failure = ('worker_protocol_error','Search stopped because its worker output was invalid.')
        if not failure and (process.returncode != 0 or result is None):
            failure = ('worker_failed','Search worker stopped unexpectedly.')
        if not failure and not observed_rss:
            failure = ('memory_monitor_unavailable','Search stopped because no worker memory measurement was available.')
        if failure:
            result = {'phase':'incomplete','error':failure[0],'message':failure[1],
                'ranking':[],'candidate_ids':[],'initial_ranking':[],'judgments':{},'evidence':[],
                'cost':latest['cost'], 'stats':{**latest,'evaluated':0,
                    'billingIncomplete':bool(latest.get('activeRequests') or latest['requests'] > latest['costReports']+latest['costUnreported'])}}
        streaming = payload.get('config') == 'streaming128'
        result['memory_guard'] = {'sqlite_heap_mib':payload.get('sqlite_mib',DEFAULT_SQLITE_MIB),
            'worker_threshold_mib':worker_mib,'file_read_mib':None if streaming else payload.get('file_mib',DEFAULT_FILE_MIB),
            'streaming_text_budget_bytes':500000 if streaming else None,
            'poll_interval_ms':round(poll_seconds*1000),'observed_peak_rss_bytes':peak_rss,
            'worker_exit_code':process.returncode,'worker_reaped':True,
            'note':'SQLite allocation limit is hard; RSS watchdog is sampled and may overshoot. UI and benchmark parent are excluded.'}
        result['elapsed'] = time.perf_counter()-started
        return result
    finally:
        if process.returncode is None:
            process.kill(); await process.wait()
        for task in readers:
            if not task.done(): task.cancel()
        await asyncio.gather(*readers,return_exceptions=True)
