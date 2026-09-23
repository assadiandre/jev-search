"""Query-specific BM25: one corpus read, compact counts, no corpus index.

Uses the same Porter/unicode61 tokenizer and BM25 formula as the reference.
Only benchmark .txt exports are supported. All state dies with the query.
"""
from array import array
from collections import Counter, deque
import codecs
import heapq
import math
import os
from pathlib import Path
import re
import sys
import stat
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'memory_deps'))
import apsw

TEXT_BUDGET = 500_000
CHUNK_BYTES = 16_384
MAX_SEGMENT_BYTES = 32_768
MAX_QUERY_BYTES = 4096


class StreamingInputError(ValueError):
    """Cannot give complete, trustworthy results for this input."""


def signature(st):
    return st.st_size, st.st_mtime_ns, st.st_ino


class StreamingBM25:
    def __init__(self, root, retrieval='streaming'):
        if retrieval != 'streaming':
            raise ValueError('StreamingBM25 requires streaming retrieval')
        self.root = Path(root)
        # Connection exposes the native tokenizer; no corpus tables are created.
        self.db = apsw.Connection(':memory:')
        self.tokenize = self.db.fts5_tokenizer('porter', ['unicode61'])
        self.records = {}
        self.count = self.bytes_read = self.evidence_bytes_read = 0
        self.scan_seconds = self.passage_seconds = 0
        self.query = None
        self.ranked = []
        self.peak_segment_bytes = self.count_storage_bytes = 0
        self.evidence_retained_bytes = 0
        self._signatures = {}
        self._evidence_ids = set()
        self._snippet_db = None

    def _segments(self, path, evidence=False, offsets=True):
        """Never cut a tokenizer word or a UTF-8 character between segments.

        An exceptionally long single word fails explicitly instead of growing
        the carry buffer without bound or silently changing tokenization.
        """
        decoder = codecs.getincrementaldecoder('utf-8')('strict')
        carry = b''
        fd=os.open(path, os.O_RDONLY | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_NONBLOCK',0))
        with os.fdopen(fd,'rb',buffering=0) as source:
            info=os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or bool(getattr(info,'st_flags',0)&0x40000000):
                raise StreamingInputError('Content is not a downloaded regular file.')
            while True:
                raw = source.read(CHUNK_BYTES)
                if b'\x00' in raw:
                    raise StreamingInputError('Binary content is not streamed as text.')
                if evidence:
                    self.evidence_bytes_read += len(raw)
                else:
                    self.bytes_read += len(raw)
                final = len(raw) < CHUNK_BYTES
                data = carry + decoder.decode(raw, final=final).encode('utf-8')
                if len(data) > MAX_SEGMENT_BYTES:
                    raise StreamingInputError('A word exceeds the bounded tokenizer buffer; search is incomplete.')
                self.peak_segment_bytes = max(self.peak_segment_bytes, len(data))
                # Most benchmark documents fit in one read. Avoid allocating
                # byte-offset tuples when the count pass needs only token text.
                tokens = self.tokenize(data, apsw.FTS5_TOKENIZE_DOCUMENT, None,
                                       include_offsets=(offsets or not final), include_colocated=False)
                # Keep the last token until its end is certain. Punctuation-only
                # segments can be discarded and never require an unbounded carry.
                if not final and tokens:
                    cut = tokens[-1][0]
                    carry = data[cut:]
                    yield data[:cut], tokens[:-1] if offsets else [t[2] for t in tokens[:-1]]
                else:
                    carry = b''
                    yield data, tokens
                if final:
                    break

    def _phrases(self, query):
        if len(query.encode('utf-8')) > MAX_QUERY_BYTES:
            raise StreamingInputError('Query exceeds the 4096-byte limit.')
        words = dict.fromkeys(re.findall(r'[^\W_]+', query.lower()))
        # Preserve duplicate stems: the reference OR expression gives each
        # original query word its own BM25 contribution.
        return [tuple(self.tokenize(w.encode(), apsw.FTS5_TOKENIZE_QUERY, None,
                                    include_offsets=False, include_colocated=False)) for w in words]

    def _counts(self, path, phrases):
        wanted = {p[0] for p in phrases if len(p) == 1}
        singles = Counter()
        multi = {p: 0 for p in phrases if len(p) > 1}
        tail = deque(maxlen=max((len(p) for p in multi), default=1))
        length = 0
        for _, tokens in self._segments(path, offsets=False):
            length += len(tokens)
            # Counter's C loop is faster than a Python test for every token.
            # The temporary vocabulary covers one bounded chunk only.
            chunk_counts = Counter(tokens)
            for word in wanted:
                singles[word] += chunk_counts.get(word, 0)
            if multi:
                for token in tokens:
                    tail.append(token)
                    recent = tuple(tail)
                    for phrase in multi:
                        if recent[-len(phrase):] == phrase:
                            multi[phrase] += 1
        return length, [singles[p[0]] if len(p) == 1 else multi.get(p, 0) for p in phrases]

    def search(self, query, limit=500):
        if not 0 <= limit <= 500:
            raise ValueError('Streaming retrieval retains at most 500 results')
        if self.query is not None:
            if query != self.query:
                raise ValueError('Create a fresh scanner for every new query')
            return self.ranked[:limit]
        started = time.perf_counter()
        self.query = query
        phrases = self._phrases(query)
        dfs = [0] * len(phrases)
        counts = array('Q')
        names = []
        stamps = array('Q')
        total_length = 0
        # Directory enumeration is streaming too; no sorted list of all paths.
        with os.scandir(self.root) as entries:
            for entry in entries:
                if not entry.name.endswith('.txt') or not entry.is_file(follow_symlinks=False):
                    continue
                path = Path(entry.path)
                before = path.stat()
                length, frequencies = self._counts(path, phrases)
                if signature(before) != signature(path.stat()):
                    raise StreamingInputError('A document changed during the scan; run the search again.')
                self.count += 1
                total_length += length
                for i, frequency in enumerate(frequencies):
                    dfs[i] += bool(frequency)
                if any(frequencies):
                    names.append(entry.name)
                    counts.extend([length, *frequencies])
                    stamps.extend(signature(before))
        self.count_storage_bytes = counts.itemsize * len(counts)
        self.metadata_storage_bytes = stamps.itemsize * len(stamps)
        average = total_length / self.count if self.count else 0
        idfs = [math.log((self.count - df + .5) / (df + .5)) for df in dfs]
        idfs = [idf if idf > 0 else 1e-6 for idf in idfs]
        width = len(phrases) + 1

        def scored():
            for j, name in enumerate(names):
                offset = j * width
                norm = 1.2 * (.25 + .75 * counts[offset] / average)
                score = 0.0
                for i, idf in enumerate(idfs):
                    frequency = counts[offset + i + 1]
                    score += idf * ((frequency * 2.2) / (frequency + norm))
                yield -score, name[:-4], j

        best = heapq.nsmallest(500, scored())
        self.ranked = [(identifier, score) for score, identifier, _ in best]
        for _, identifier, j in best:
            path = self.root / names[j]
            st = path.stat()
            expected = tuple(stamps[j * 3:j * 3 + 3])
            if signature(st) != expected:
                raise StreamingInputError('A candidate changed during the scan; run the search again.')
            self.records[identifier] = (path, st)
            self._signatures[identifier] = expected
        # Counts and noncandidate names are released here, before excerpt/API work.
        self.scan_seconds = time.perf_counter() - started
        return self.ranked[:limit]

    def compact(self, identifier, query):
        """Bounded per-segment FTS snippets; exact reference snippet for small docs.

        Only one <=32 KiB segment is in this tiny scratch table at a time.
        Large documents choose the segment covering the most distinct query
        stems. This excerpt policy is separately evaluated, not assumed equal.
        """
        if query != self.query:
            raise ValueError('Evidence query must match the scan')
        if identifier in self._evidence_ids:
            raise ValueError('Extract each candidate once')
        path, _ = self.records[identifier]
        if signature(path.stat()) != self._signatures[identifier]:
            raise StreamingInputError('A candidate changed before excerpt extraction.')
        words = dict.fromkeys(re.findall(r'[^\W_]+', query.lower()))
        expr = ' OR '.join('"' + word + '"' for word in words)
        wanted = {token for phrase in self._phrases(query) for token in phrase}
        if self._snippet_db is None:
            self._snippet_db = apsw.Connection(':memory:')
            self._snippet_db.execute('PRAGMA temp_store=MEMORY')
            self._snippet_db.execute("CREATE VIRTUAL TABLE piece USING fts5(text, tokenize='porter unicode61')")
        db = self._snippet_db
        title = ''
        best = ''
        best_score = (-1, -1)
        for data, tokens in self._segments(path, evidence=True):
            if not title:
                title = data[:640].decode('utf-8', errors='ignore').split('\n', 1)[0][:160]
            matches = Counter(t[2] for t in tokens if t[2] in wanted)
            score = (len(matches), sum(matches.values()))
            if not matches or score <= best_score:
                continue
            db.execute('DELETE FROM piece')
            db.execute('INSERT INTO piece(text) VALUES (?)', (data.decode('utf-8'),))
            row = db.execute("SELECT snippet(piece,0,'','',' … ',48) FROM piece WHERE piece MATCH ?", (expr,)).fetchone()
            if row:
                best, best_score = row[0][:650], score
            db.execute('DELETE FROM piece')
        if signature(path.stat()) != self._signatures[identifier]:
            raise StreamingInputError('A candidate changed during excerpt extraction.')
        from backend.core import redact
        text = best if title and title in best else title + '\n' + best
        text = redact(text[:650])[:650]
        self.evidence_retained_bytes += len(text.encode('utf-8'))
        # Reserve 160 KB for bounded input/carry, decoding, tokenizer input and
        # single-segment snippet text. Python/native bookkeeping is separate.
        if self.evidence_retained_bytes + 160_000 > TEXT_BUDGET:
            raise StreamingInputError('Excerpt text budget exceeded.')
        self._evidence_ids.add(identifier)
        return text, 'Title + query-focused 48-token passage (650 characters maximum)'

    def diagnostics(self):
        return {'retrievalMode': 'streaming-bm25', 'filesRead': self.count,
                'bytesRead': self.bytes_read, 'freshScanSeconds': self.scan_seconds,
                'evidenceBytesRead': self.evidence_bytes_read,
                'queryCountBytes': self.count_storage_bytes,
                'candidateStampBytes': getattr(self, 'metadata_storage_bytes', 0),
                'peakTextSegmentBytes': self.peak_segment_bytes,
                'retainedEvidenceBytes': self.evidence_retained_bytes,
                'textBudgetBytes': TEXT_BUDGET, 'textWorkspaceReserveBytes': 160_000,
                'corpusIndexStored': False, 'scanComplete': True}

    def close(self):
        if self._snippet_db is not None:
            self._snippet_db.close()
            self._snippet_db = None
        if self.db is not None:
            self.db.close()
            self.db = None
