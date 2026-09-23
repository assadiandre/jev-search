"""Fresh recursive Desktop retrieval using query-only BM25 counts."""
from array import array
from collections import Counter
import heapq
import math
from pathlib import Path
import stat
import time

from backend import core
from backend.fast import RetrievalMatcher, TEXT_EXTENSIONS, DOCUMENT_EXTENSIONS
from backend.streaming_bm25 import StreamingBM25, StreamingInputError, signature, apsw


class DesktopBM25(StreamingBM25):
    def __init__(self, root, options, stop, progress):
        super().__init__(root)
        self.options, self.stop, self.progress = options, stop, progress
        self.stats = {'scanned':0,'excluded':0,'unreadable':0,'protected':0,
                      'textFilesRead':0,'documentsSampled':0,'contentUnavailable':0,
                      'nameOnly':0,'bytesRead':0,'mode':'streaming','sampled':0,
                      'scanComplete':False,'candidateLimit':128,'textBudgetBytes':500000}
        self.desktop_records = {}
        self.coverage = {}
        self._last_progress = 0

    def is_text(self, record):
        return record.kind == 'code' or Path(record.name).suffix.lower() in TEXT_EXTENSIONS

    def _segments(self, path, evidence=False, offsets=True):
        # Recheck lstat; also open without following a replacement symlink.
        if path.is_symlink():
            raise StreamingInputError('A file became a symbolic link during the search.')
        yield from super()._segments(path, evidence=evidence, offsets=offsets)

    def _frequencies(self, text, phrases):
        tokens = self.tokenize(text.encode('utf-8'), apsw.FTS5_TOKENIZE_DOCUMENT, None,
                               include_offsets=False, include_colocated=False)
        counts = Counter(tokens)
        frequencies = []
        for phrase in phrases:
            if len(phrase)==1: frequencies.append(counts.get(phrase[0],0))
            else: frequencies.append(sum(tuple(tokens[i:i+len(phrase)])==phrase for i in range(len(tokens))))
        return len(tokens), frequencies

    def search(self, query, limit=500):
        if self.query is not None:
            if query!=self.query: raise ValueError('Use a new scanner for each query')
            return self.ranked[:limit]
        self.query=query
        started=time.perf_counter()
        phrases=self._phrases(query)
        dfs=[0]*len(phrases)
        packed=array('Q')
        matches=[]
        coverages=[]
        total_length=0
        matcher=RetrievalMatcher(query)

        def consume(chunk):
            nonlocal total_length
            self.stats.update(excluded=chunk['excluded'], unreadable=chunk['unreadable'])
            for record in chunk['records']:
                if self.stop.is_set(): raise InterruptedError('Search stopped')
                self.stats['scanned']+=1
                path=Path(record.path)
                if core.sensitive(path):
                    self.stats['protected']+=1
                    continue
                length, frequencies=self._frequencies(record.relative,phrases)
                coverage='Name and path only'
                if self.options.read_contents and not record.symlink and not record.placeholder and record.kind!='folder':
                    try:
                        if self.is_text(record):
                            before=path.lstat()
                            if not stat.S_ISREG(before.st_mode): raise OSError('Not a regular file')
                            doc_length, doc_freq=self._counts(path,phrases)
                            if signature(before)!=signature(path.lstat()):
                                raise StreamingInputError('Document changed')
                            length+=doc_length
                            frequencies=[a+b for a,b in zip(frequencies,doc_freq)]
                            coverage='Entire text streamed · query-focused excerpt'
                            self.stats['textFilesRead']+=1
                        elif path.suffix.lower() in DOCUMENT_EXTENSIONS:
                            # Existing bounded PDF/Office extraction; intentionally
                            # reported as sampled, never as full content coverage.
                            text, detail=core.evidence(record,query,self.options,self.stop,quick=True)
                            if text:
                                doc_length, doc_freq=self._frequencies(text[:1400],phrases)
                                length+=doc_length
                                frequencies=[a+b for a,b in zip(frequencies,doc_freq)]
                                coverage=detail
                                self.stats['documentsSampled']+=1
                            else: self.stats['contentUnavailable']+=1
                    except (OSError,UnicodeError,StreamingInputError):
                        self.stats['contentUnavailable']+=1
                        coverage='Name and path only · content unavailable or changed'
                if coverage.startswith('Name and path'): self.stats['nameOnly']+=1
                self.count+=1
                total_length+=length
                for i,f in enumerate(frequencies): dfs[i]+=bool(f)
                if any(frequencies) or matcher.score(record)>=.91:
                    packed.extend([length,*frequencies])
                    matches.append(record)
                    coverages.append(coverage)
                now=time.perf_counter()
                if now-self._last_progress>.2:
                    self.stats.update(bytesRead=self.bytes_read,elapsed=now-started)
                    self.progress(dict(self.stats))
                    self._last_progress=now

        core.scan(self.root,self.options,self.stop,consume)
        if self.stop.is_set(): raise InterruptedError('Search stopped')
        average=total_length/self.count if self.count else 0
        idfs=[math.log((self.count-df+.5)/(df+.5)) for df in dfs]
        idfs=[v if v>0 else 1e-6 for v in idfs]
        width=len(phrases)+1

        def scored():
            for j,record in enumerate(matches):
                offset=j*width
                norm=1.2*(.25+.75*packed[offset]/average) if average else 1.2
                score=sum(idf*((packed[offset+i+1]*2.2)/(packed[offset+i+1]+norm)) for i,idf in enumerate(idfs))
                name_score=matcher.score(record)
                # Literal filenames remain easy to find among long text files.
                priority=0 if name_score==1 else 1 if name_score>=.91 else 2
                yield priority,-score,record.relative,j

        best=heapq.nsmallest(500,scored())
        for _,score,identifier,j in best:
            record=matches[j]
            self.ranked.append((identifier,score))
            self.desktop_records[identifier]=record
            self.coverage[identifier]=coverages[j]
            if self.is_text(record) and not record.symlink and not record.placeholder and record.kind!='folder':
                try:
                    st=Path(record.path).lstat()
                    self.records[identifier]=(Path(record.path),st)
                    self._signatures[identifier]=signature(st)
                except OSError: pass
        self.count_storage_bytes=packed.itemsize*len(packed)
        self.scan_seconds=time.perf_counter()-started
        self.stats.update(scanComplete=True,scanTime=self.scan_seconds,bytesRead=self.bytes_read,
                          sampled=self.stats['documentsSampled'],queryCountBytes=self.count_storage_bytes)
        return self.ranked[:limit]

    def compact(self, identifier, query):
        record=self.desktop_records[identifier]
        if self.options.read_contents and identifier in self.records and self.coverage[identifier].startswith('Entire text'):
            try:
                text,_=super().compact(identifier,query)
                return text,self.coverage[identifier]
            except (OSError,UnicodeError,StreamingInputError):
                return '', 'Name and path only · content changed or unavailable'
        if not self.options.read_contents: return '', 'Name and path only'
        text,coverage=core.evidence(record,query,self.options,self.stop,quick=True)
        text=text[:650]
        self.evidence_retained_bytes+=len(text.encode('utf-8'))
        if self.evidence_retained_bytes+160000>500000:
            raise StreamingInputError('Excerpt text budget exceeded')
        return text,coverage
