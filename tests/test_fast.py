import asyncio
import json
import threading
import time
from pathlib import Path

import httpx
import pytest

from backend.core import Options, Record, Search, evidence, scan
from backend.fast import Candidate, ProbeQueue, RetrievalMatcher, select_candidates


def candidate(relative, score=0, content=0):
    return Candidate(Record('/fixture/' + relative, relative, Path(relative).name, 'document', None, None), score, content)


def test_selection_reserves_content_and_diverse_folders():
    names = [candidate(f'copies/resume_{i}.txt', .91) for i in range(200)]
    content = [candidate(f'archive_{i}/untitled.txt', 0, .86) for i in range(48)]
    other = [candidate(f'project_{i}/notes.txt', .7) for i in range(12)]
    selected = select_candidates(names + content + other, 128)
    paths = [c.record.relative for c, _ in selected]
    assert len(paths) == len(set(paths)) == 128
    assert all(c.record.relative in paths for c in content)
    assert all(c.record.relative in paths for c in other)
    assert len(select_candidates(names, 0)) == 0


def test_probe_queue_rotates_across_folders():
    queue = ProbeQueue()
    for i in range(100):
        queue.add(candidate(f'a/file_{i}.txt'))
    queue.add(candidate('b/hidden_target.txt'))
    assert queue.pop().parent == 'a'
    assert queue.pop().parent == 'b'


def test_aliases_work_in_names_paths_and_contents():
    matcher = RetrievalMatcher('my rental agreement')
    assert matcher.text_score('A residential lease agreement') > .8
    assert matcher.text_score('Nothing to do with the search') == 0
    assert RetrievalMatcher('resume').score(candidate('old/CV.pdf').record) > .8
    assert RetrievalMatcher('resume').score(candidate('CV/untitled.pdf').record) == .72


def test_lightweight_scan_avoids_per_entry_stat_and_excludes_special_files(tmp_path, monkeypatch):
    import os
    (tmp_path / 'notes.txt').write_text('hello')
    os.mkfifo(tmp_path / 'fifo')
    chunks = []
    scan(tmp_path, Options(), threading.Event(), chunks.append, lightweight=True)
    records = [r for chunk in chunks for r in chunk['records']]
    assert [r.name for r in records] == ['notes.txt']
    assert records[0].modified is None and records[0].size is None


@pytest.mark.asyncio
async def test_content_rescues_opaque_name_and_cost_budget(tmp_path):
    # Many filename hits cannot displace a target found only inside its text.
    for i in range(150):
        (tmp_path / f'rental_agreement_copy_{i}.txt').write_text('Unrelated boilerplate')
    target = tmp_path / 'untitled.txt'
    target.write_text('Residential lease agreement for the apartment.')
    (tmp_path / 'jev.txt').write_text('protected')
    sent = []
    events = []
    def handler(request):
        data = json.loads(request.content)
        sent.extend(data['state']['records'])
        return httpx.Response(200, json={'answers': {k: {'noul': .9} for k in data['questions']}, 'usage': {'cost': .001}})
    async def emit(event): events.append(event)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await Search(emit).run(tmp_path, 'rental agreement', 'test', Options(probe_seconds=2), client)
    final = events[-1]
    target_record = next(r for r in sent if r['name'] == 'untitled.txt')
    assert 'lease agreement' in target_record['text']
    assert 'jev.txt' not in {r['name'] for r in sent}
    assert final['stats']['evaluated'] == 128
    assert len(sent) == len({r['path'] for r in sent})
    assert final['stats']['requests'] <= 5
    assert final['stats']['cost'] == pytest.approx(final['stats']['requests'] * .001)
    assert final['stats']['sampled'] == 151
    assert any(h['name'] == 'untitled.txt' for h in final['hits'])


@pytest.mark.asyncio
async def test_no_contents_setting_prevents_probes(tmp_path, monkeypatch):
    import backend.fast as fast
    (tmp_path / 'notes.txt').write_text('secret topic')
    def forbidden(*args, **kwargs): raise AssertionError('content was read')
    monkeypatch.setattr(fast, 'begin_read', forbidden)
    sent = []
    def handler(request):
        data = json.loads(request.content); sent.extend(data['state']['records'])
        return httpx.Response(200, json={'answers': {k: {'noul': .1} for k in data['questions']}, 'usage': {'cost': 0}})
    events = []
    async def emit(event): events.append(event)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await Search(emit).run(tmp_path, 'topic', 'test', Options(read_contents=False), client)
    assert all(r['text'] == '' for r in sent)
    assert events[-1]['stats']['sampled'] == 0


@pytest.mark.asyncio
async def test_fast_timeout_keeps_local_hits_and_honest_billing(tmp_path):
    (tmp_path / 'budget.txt').write_text('Budget for next year')
    async def handler(request):
        await asyncio.sleep(10)
        return httpx.Response(500)
    events = []
    async def emit(event): events.append(event)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await Search(emit).run(tmp_path, 'budget', 'test', Options(api_seconds=.1), client)
    assert events[-1]['phase'] == 'partial'
    assert events[-1]['stats']['billingIncomplete']
    assert events[-1]['hits'][0]['name'] == 'budget.txt'


@pytest.mark.asyncio
async def test_wider_mode_reaches_files_outside_fast_candidates(tmp_path):
    for i in range(170):
        (tmp_path / f'file_{i}.txt').write_text('plain text')
    seen = []
    def handler(request):
        data = json.loads(request.content)
        seen.extend(r['path'] for r in data['state']['records'])
        return httpx.Response(200, json={'answers': {k: {'noul': .1} for k in data['questions']}, 'usage': {'cost': .001}})
    events = []
    async def emit(event): events.append(event)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await Search(emit).run(tmp_path, 'rare topic', 'test', Options(read_contents=False), client)
        assert len(set(seen)) == 128
        seen.clear(); events.clear()
        (tmp_path / 'new_file.txt').write_text('Added after fast search')
        await Search(emit).run(tmp_path, 'rare topic', 'test', Options(mode='deep'), client)
    assert len(set(seen)) == 171 and 'new_file.txt' in seen
    assert events[0]['stats']['cost'] == 0
    assert events[-1]['stats']['mode'] == 'deep'


@pytest.mark.asyncio
async def test_network_starts_before_live_walk_finishes(tmp_path, monkeypatch):
    import backend.fast as fast
    entered = threading.Event()
    def delayed_scan(root, options, stop, emit, lightweight=False):
        time.sleep(.17)
        emit({'records': [candidate(f'needle_{i}.txt', .96).record for i in range(32)], 'excluded': 0, 'unreadable': 0})
        assert entered.wait(2), 'JEV was deferred until after traversal'
    monkeypatch.setattr(fast, 'scan', delayed_scan)
    def handler(request):
        entered.set()
        data = json.loads(request.content)
        return httpx.Response(200, json={'answers': {k: {'noul': .9} for k in data['questions']}, 'usage': {'cost': 0}})
    events = []
    async def emit(event): events.append(event)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await Search(emit).run(tmp_path, 'needle', 'test', Options(read_contents=False), client)
    assert events[-1]['phase'] == 'complete'
    assert entered.is_set()


@pytest.mark.asyncio
async def test_fast_cancel_does_not_publish_late_probe_results(tmp_path, monkeypatch):
    import backend.fast as fast
    (tmp_path / 'opaque.txt').write_text('hello')
    reading, release = threading.Event(), threading.Event()
    def slow(*args, **kwargs):
        reading.set(); release.wait(2)
        return 'late target text', 'Text excerpt'
    monkeypatch.setattr(fast, 'evidence', slow)
    events = []
    async def emit(event): events.append(event)
    search = Search(emit)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(500))) as client:
        task = asyncio.create_task(search.run(tmp_path, 'target', 'test', Options(), client))
        assert await asyncio.to_thread(reading.wait, 1)
        search.cancel(); task.cancel()
        await task
        count = len(events)
        release.set(); await asyncio.sleep(.05)
    assert events[-1]['phase'] == 'stopped' and len(events) == count


@pytest.mark.asyncio
async def test_fast_budget_also_limits_overflow_retries(tmp_path):
    for i in range(128):
        (tmp_path / f'item_{i}.txt').write_text('hello')
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(400, json={'error': 'max_tokens_exceeded'})
    events = []
    async def emit(event): events.append(event)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await Search(emit).run(tmp_path, 'hello', 'test', Options(read_contents=False), client)
    assert len(requests) == events[-1]['stats']['requests'] == 8
    assert events[-1]['phase'] == 'partial'


def test_quick_probe_rechecks_replaced_symlinks(tmp_path):
    target = tmp_path / 'notes.txt'
    target.write_text('initial')
    record = Record(str(target), target.name, target.name, 'document', None, None)
    secret = tmp_path / 'jev.txt'; secret.write_text('protected contents')
    target.unlink(); target.symlink_to(secret)
    assert evidence(record, 'protected', Options(), threading.Event(), quick=True)[0] == ''


@pytest.mark.asyncio
async def test_opaque_pdf_gets_content_evidence(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    path = tmp_path / 'scan_0042.pdf'
    writer = PdfWriter(); page = writer.add_blank_page(600, 800)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
    stream = DecodedStreamObject(); stream.set_data(b'BT /F1 12 Tf 50 700 Td (Residential lease agreement) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(stream)
    writer.write(path)
    sent = []
    def handler(request):
        data = json.loads(request.content); sent.extend(data['state']['records'])
        return httpx.Response(200, json={'answers': {k: {'noul': .9} for k in data['questions']}, 'usage': {'cost': 0}})
    events = []
    async def emit(event): events.append(event)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await Search(emit).run(tmp_path, 'rental agreement', 'test', Options(probe_seconds=2), client)
    assert 'lease agreement' in sent[0]['text']
    assert events[-1]['hits'][0]['name'] == path.name


@pytest.mark.asyncio
async def test_weak_text_match_does_not_override_negative_jev_decision(tmp_path):
    (tmp_path / 'opaque.txt').write_text('Mathematics is a subject at school.')
    events = []
    async def emit(event): events.append(event)
    def handler(request):
        data = json.loads(request.content)
        return httpx.Response(200, json={'answers': {k: {'noul': .05} for k in data['questions']}, 'usage': {'cost': 0}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await Search(emit).run(tmp_path, 'mathematics videos', 'test', Options(), client)
    assert not events[-1]['hits']
