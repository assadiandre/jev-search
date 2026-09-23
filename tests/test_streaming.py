import asyncio
import threading
import time
from pathlib import Path
import pytest

from backend.core import Options, Search
from backend.desktop_stream import DesktopBM25


def scanner(root, **options):
    return DesktopBM25(root, Options(mode='streaming',**options), threading.Event(), lambda stats: None)


def test_recursive_streaming_fresh_content_names_and_exclusions(tmp_path):
    folder=tmp_path/'Research';folder.mkdir()
    (folder/'neutral.txt').write_text('unrelated '*12000+' zebrafish regenerate cardiac muscle')
    (tmp_path/'budget.png').write_bytes(b'not a real image')
    (tmp_path/'jev.txt').write_text('zebrafish private API key')
    generated=tmp_path/'node_modules';generated.mkdir();(generated/'hidden.txt').write_text('zebrafish')
    scan=scanner(tmp_path)
    try:
        result=scan.search('zebrafish')
        assert [i for i,s in result]==['Research/neutral.txt']
        text,_=scan.compact(result[0][0],'zebrafish')
        assert 'zebrafish' in text
        assert scan.stats['textFilesRead']==1
        assert scan.stats['protected']==1
    finally: scan.close()
    (folder/'neutral.txt').unlink()
    scan=scanner(tmp_path)
    try: assert not scan.search('zebrafish')
    finally: scan.close()
    scan=scanner(tmp_path)
    try: assert scan.search('budget')[0][0]=='budget.png'
    finally: scan.close()
    assert not list(tmp_path.rglob('*.sqlite'))


def test_symlinks_binary_and_corrupt_docs_do_not_stop_search(tmp_path):
    (tmp_path/'source.txt').write_text('needle')
    (tmp_path/'link.txt').symlink_to(tmp_path/'source.txt')
    (tmp_path/'binary.txt').write_bytes(b'\x00needle')
    (tmp_path/'corrupt.pdf').write_bytes(b'not a PDF')
    scan=scanner(tmp_path)
    try:
        result=scan.search('needle')
        assert [i for i,s in result]==['source.txt']
        assert scan.stats['contentUnavailable']==2
    finally: scan.close()


@pytest.mark.asyncio
async def test_supervised_search_and_cancellation(tmp_path):
    (tmp_path/'note.txt').write_text('cardiac repair')
    events=[]
    async def emit(event): events.append(event)
    search=Search(emit)
    await search.run(tmp_path,'cardiac','',Options(mode='streaming'))
    assert events[-1]['phase']=='complete'
    assert events[-1]['hits'][0]['name']=='note.txt'
    assert events[-1]['stats']['requests']==0
    assert events[-1]['stats']['textFilesRead']==1
    assert events[-1]['stats']['workerPeakRSS']>0
    events.clear()
    task=asyncio.create_task(Search(emit).run(tmp_path,'cardiac','',Options(mode='streaming')))
    await asyncio.sleep(.02)
    task.cancel()
    await task
    assert events[-1]['phase']=='stopped'


def test_content_disabled_and_generated_opt_in(tmp_path):
    (tmp_path/'plain.txt').write_text('needle')
    hidden=tmp_path/'.hidden';hidden.mkdir();(hidden/'needle.txt').write_text('needle')
    scan=scanner(tmp_path,read_contents=False)
    try: assert scan.search('needle')==[]
    finally: scan.close()
    scan=scanner(tmp_path,include_generated=True)
    try:
        assert {i for i,s in scan.search('needle')}=={'plain.txt','.hidden/needle.txt'}
    finally: scan.close()
