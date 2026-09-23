"""Bounded retrieval over a fresh walk. All file state dies with this query."""
from __future__ import annotations

import asyncio
import dataclasses
import os
import queue
import threading
import time
import zlib
from collections import Counter, deque
from pathlib import Path

import httpx

from backend.core import APIError, Matcher, Options, Record, classify, evidence, normalize, scan, sensitive, word_tokens

ALIASES = (
    {"resume", "cv", "curriculum", "vitae"}, {"rental", "lease", "tenancy"},
    {"invoice", "billing"}, {"presentation", "slides", "deck"},
    {"photo", "photos", "photograph", "image", "images"},
    {"expenses", "spending", "expenditure"}, {"meeting", "minutes"},
)
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".odt"}
TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".tsv", ".log", ".svg", ".rtf", ""}
# Global limits also bound unfinished readers after a query is canceled. Daemon
# readers cannot hold app shutdown hostage to a corrupt PDF or slow filesystem.
TEXT_SLOTS = threading.BoundedSemaphore(4)
DOCUMENT_SLOTS = threading.BoundedSemaphore(2)
QUOTAS = {"name": 32, "content": 48, "context": 24, "preview": 8, "explore": 16}


class RetrievalMatcher(Matcher):
    def __init__(self, query):
        super().__init__(query)
        self.groups = [next((group for group in ALIASES if word in group), {word}) for word in self.words]
        self.has_aliases = any(len(group) > 1 for group in self.groups)
        self.expanded_query = query + " " + " ".join(sorted(set().union(*self.groups) if self.groups else set()))

    def text_score(self, text):
        if not self.groups or not text:
            return 0.0
        words = set(word_tokens(text))
        matched = sum(bool(words.intersection(group)) for group in self.groups)
        return (0.48 + 0.38 * matched / len(self.groups)) if matched else 0.0

    def score(self, record):
        score = super().score(record)
        if score >= .72 or not self.has_aliases:
            return score
        path = normalize(record.relative)
        if not all(any(word in path for word in group) for group in self.groups):
            return score
        name_words = set(word_tokens(record.name))
        if all(name_words.intersection(group) for group in self.groups):
            return max(score, .82)
        path_words = set(word_tokens(record.relative))
        if all(path_words.intersection(group) for group in self.groups):
            return max(score, .72)
        return score


@dataclasses.dataclass(slots=True)
class Candidate:
    record: Record
    name_score: float
    content_score: float = 0
    text: str = ""
    coverage: str = "Name and path only"
    probed: bool = False

    @property
    def parent(self):
        return self.record.relative.rpartition("/")[0]


class ProbeQueue:
    """Rotate directories so a large directory cannot monopolize content reads."""
    def __init__(self):
        self.folders = {}
        self.order = deque()

    def add(self, candidate):
        parent = candidate.parent
        if parent not in self.folders:
            self.folders[parent] = deque()
            self.order.append(parent)
        self.folders[parent].append(candidate)

    def pop(self):
        if not self.order:
            return None
        parent = self.order.popleft()
        files = self.folders[parent]
        result = files.popleft()
        if files:
            self.order.append(parent)
        else:
            del self.folders[parent]
        return result


def select_candidates(candidates, limit, excluded=None, used=None, total=128):
    """Independent quotas, with soft directory diversity and adaptive backfill."""
    excluded = set(excluded or ())
    used = used or Counter()
    routes = {route: [] for route in QUOTAS}
    for c in candidates:
        if c.record.path in excluded:
            continue
        if c.name_score >= .45:
            routes["context" if c.name_score == .72 else "name"].append(c)
        if c.content_score >= .45:
            routes["content"].append(c)
        if c.text and c.content_score < .45:
            routes["preview"].append(c)
        routes["explore"].append(c)
    result = []

    def take(route, count):
        if count <= 0:
            return
        values = routes[route]
        if route == "explore":
            values.sort(key=lambda c: zlib.crc32(c.record.relative.encode()))
        else:
            values.sort(key=lambda c: (- (c.content_score if route == "content" else c.name_score), c.record.relative))
        directories = Counter()
        deferred = []
        added = 0
        for c in values:
            if c.record.path in excluded:
                continue
            if directories[c.parent] >= 4 and c.name_score < .96:
                deferred.append(c)
                continue
            result.append((c, route)); excluded.add(c.record.path)
            directories[c.parent] += 1; added += 1
            if added >= count or len(result) >= limit:
                return
        for c in deferred:
            result.append((c, route)); excluded.add(c.record.path)
            added += 1
            if added >= count or len(result) >= limit:
                return

    for route, quota in QUOTAS.items():
        take(route, min(limit - len(result), max(0, round(quota * total / 128) - used[route])))
        if len(result) >= limit:
            break
    if len(result) < limit:
        take("explore", limit - len(result))
    return result


def begin_read(candidate, matcher, options, stop, slots):
    if not slots.acquire(blocking=False):
        return None
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    record = dataclasses.replace(candidate.record)

    def deliver(value):
        if not future.done():
            future.set_result(value)

    def read():
        try:
            value = (record, *evidence(record, matcher.expanded_query, options, stop, quick=True))
        except Exception:
            value = (record, "", "Name and path · text unavailable")
        finally:
            slots.release()
        try:
            loop.call_soon_threadsafe(deliver, value)
        except RuntimeError:
            pass  # The owning query/service has already shut down.

    threading.Thread(target=read, daemon=True, name="jev-content-probe").start()
    return future


async def run_fast(search, root, query, key, options, client=None):
    search.started = time.perf_counter()
    search.matcher = matcher = RetrievalMatcher(query)
    stats = search.stats
    stats.update(mode="fast", sampled=0, probes=0, scanComplete=False,
                 candidateLimit=options.candidate_limit, selected=0, requestLimit=8, routes={})
    owned_client = client is None
    candidates = []
    input_queue = queue.Queue(maxsize=8)
    scan_finished = asyncio.Event()
    probe_stop = threading.Event()
    text_queue, document_queue = ProbeQueue(), ProbeQueue()
    judged = set()
    used = Counter()
    jobs = []
    fatal = []
    probe_deadline = search.started + options.probe_seconds
    api_deadline = search.started + options.api_seconds
    semaphore = asyncio.Semaphore(min(4, options.concurrency))

    def enqueue(value):
        while not search.stop.is_set():
            try:
                input_queue.put(value, timeout=.05)
                return
            except queue.Full:
                pass

    def produce():
        try:
            scan(root, options, search.stop, enqueue, lightweight=True)
        except Exception as error:
            enqueue(error)
        finally:
            enqueue(None)

    async def probe(work, slots, counts, cap):
        per_folder = counts[1]
        while not search.stop.is_set() and time.perf_counter() < probe_deadline and counts[0] < cap:
            candidate = work.pop()
            if candidate is None:
                if scan_finished.is_set():
                    return
                await asyncio.sleep(.003)
                continue
            # Save reads for directories the live walk has not reached yet.
            if not scan_finished.is_set() and per_folder[candidate.parent] >= (2 if slots is DOCUMENT_SLOTS else 8):
                work.add(candidate)
                await asyncio.sleep(.003)
                continue
            future = begin_read(candidate, matcher, options, probe_stop, slots)
            if future is None:
                work.add(candidate)
                await asyncio.sleep(.005)
                continue
            counts[0] += 1; stats["probes"] += 1
            per_folder[candidate.parent] += 1
            record, text, coverage = await future
            candidate.record = record
            candidate.probed = True
            candidate.text, candidate.coverage = text[:1000], coverage
            candidate.content_score = matcher.text_score(text)
            if text:
                stats["sampled"] += 1
                if record.path not in judged:
                    search.add_hit(record, text=candidate.text, coverage=coverage)
            await search.update("scanning" if not scan_finished.is_set() else "thinking")

    async def judge(batch):
        async with semaphore:
            if search.stop.is_set() or fatal:
                return
            if time.perf_counter() >= api_deadline:
                stats["deadlineReached"] = True
                return
            records = [c.record for c, _ in batch]
            excerpts = [(c.text, c.coverage) for c, _ in batch]
            try:
                scores, _ = await classify(client, records, excerpts, query, stats)
                stats["evaluated"] += len(records)
                for record, score, (text, coverage) in zip(records, scores, excerpts):
                    search.add_hit(record, score, text, coverage)
            except APIError as error:
                stats["failed"] += len(records)
                if error.fatal:
                    fatal.append(str(error))
                await search.emit({"type": "warning", "message": str(error)})
            await search.update("scanning" if not scan_finished.is_set() else "thinking")

    def submit(chosen):
        for c, route in chosen:
            judged.add(c.record.path); used[route] += 1
        stats["selected"] = len(judged)
        stats["routes"] = dict(used)
        for i in range(0, len(chosen), options.batch_size):
            jobs.append(asyncio.create_task(judge(chosen[i:i + options.batch_size])))

    readers = []
    try:
        if key and client is None:
            client = httpx.AsyncClient(headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "JEV SEARCH"},
                                       timeout=httpx.Timeout(8, connect=3), limits=httpx.Limits(max_connections=4, max_keepalive_connections=4))
        threading.Thread(target=produce, daemon=True, name="jev-live-scan").start()
        await search.update("scanning", True)
        if key and options.read_contents:
            text_counts, document_counts = [0, Counter()], [0, Counter()]
            readers = [asyncio.create_task(probe(text_queue, TEXT_SLOTS, text_counts, 384)) for _ in range(4)]
            readers += [asyncio.create_task(probe(document_queue, DOCUMENT_SLOTS, document_counts, 16)) for _ in range(2)]
        while not search.stop.is_set():
            try:
                chunk = await asyncio.to_thread(input_queue.get, True, .05)
            except queue.Empty:
                continue
            if chunk is None:
                break
            if isinstance(chunk, Exception):
                raise chunk
            stats["scanned"] += len(chunk["records"])
            stats.update(excluded=chunk["excluded"], unreadable=chunk["unreadable"])
            for record in chunk["records"]:
                name_score = matcher.score(record)
                if name_score >= .45:
                    search.add_hit(record)
                if sensitive(Path(record.name)):
                    stats["protected"] += 1
                    continue
                candidate = Candidate(record, name_score)
                candidates.append(candidate)
                if readers and not record.symlink and not record.placeholder and record.kind != "folder":
                    extension = os.path.splitext(record.name)[1].lower()
                    if extension in DOCUMENT_EXTENSIONS:
                        document_queue.add(candidate)
                    elif record.kind == "code" or extension in TEXT_EXTENSIONS:
                        text_queue.add(candidate)
            # Only one early batch; later content discoveries retain most slots.
            if key and not jobs and time.perf_counter() - search.started >= .16:
                ready = [c for c in candidates if c.probed or c.name_score >= .91]
                if len(ready) >= 8:
                    submit(select_candidates(ready, min(32, options.candidate_limit), total=options.candidate_limit))
            await search.update("scanning")
        if search.stop.is_set():
            raise asyncio.CancelledError
        scan_finished.set()
        stats.update(scanComplete=True, scanTime=time.perf_counter() - search.started)
        if readers:
            await asyncio.wait(readers, timeout=max(0, probe_deadline - time.perf_counter()))
        probe_stop.set()
        for task in readers:
            task.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
        if not key:
            await search.update("complete", True, "Filename search complete. Add an OpenRouter key in Settings to enable JEV.")
            return
        if time.perf_counter() < api_deadline:
            submit(select_candidates(candidates, options.candidate_limit - len(judged), judged, used, options.candidate_limit))
        else:
            stats["deadlineReached"] = True
        await search.update("thinking", True)
        pending = set()
        if jobs:
            _, pending = await asyncio.wait(jobs, timeout=max(0, api_deadline - time.perf_counter()))
            for task in pending:
                task.cancel()
            outcomes = await asyncio.gather(*jobs, return_exceptions=True)
            for outcome in outcomes:
                if isinstance(outcome, Exception):
                    raise outcome
        stats["semanticRemaining"] = max(0, len(candidates) - stats["evaluated"])
        stats["canWiden"] = bool(stats["semanticRemaining"] or (options.read_contents and stats["sampled"] < len(candidates)))
        if pending:
            stats["billingIncomplete"] = True
        limited = pending or stats.get("deadlineReached")
        message = fatal[0] if fatal else ("Fast search reached its time budget. Results found so far are available. Use Look wider to check more files." if limited else "Some candidates could not be checked. Use Look wider to try a full search." if stats["failed"] else "")
        await search.update("partial" if limited or fatal or stats["failed"] else "complete", True, message)
    except asyncio.CancelledError:
        search.stop.set()
        await search.update("stopped", True, "Search stopped. Results found so far are still available.")
    except Exception as error:
        await search.update("error", True, str(error))
    finally:
        search.stop.set(); probe_stop.set(); scan_finished.set()
        for task in readers + jobs:
            task.cancel()
        await asyncio.gather(*readers, *jobs, return_exceptions=True)
        if owned_client and client is not None:
            await client.aclose()
