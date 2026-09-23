<p align="center">
  <img src="assets/icon.png" alt="JEV Search logo" width="128" height="128">
</p>

<h1 align="center">JEV Search</h1>

<p align="center">
  Find your files. In your own words.<br>
  <strong>No pre-indexing. Every search starts fresh.</strong>
</p>

<p align="center">
  macOS · Python + Electron · Powered by JEV
</p>

---

Search names, documents, and code from a single search bar. Local retrieval finds
candidates; **JEV** judges which ones match what you mean.

- **Fresh by default.** Search the files you have right now.
- **Small shortlist.** Stream text locally, then let JEV rerank up to 128 candidates.
- **Cost in plain sight.** See the reported API charge for every search.

Press **⌘⌥Space**, type a query, and hit Return.

### Benchmarks

**623 queries. Fresh scans. Less than one cent per search.**

Complete NFCorpus and SciFact test sets, with the same BM25 candidates before
and after JEV reranking. nDCG@10 measures ranking relevance; higher is better.

| Dataset | Queries | BM25 nDCG@10 | + JEV | Recall@100¹ | API cost / search |
|---|---:|---:|---:|---:|---:|
| NFCorpus · 3,633 documents | 323 | 0.3223 | **0.3773** | 25.5% | **0.0843¢** |
| SciFact · 5,183 documents | 300 | 0.6874 | **0.7451** | 92.9% | **0.1301¢** |

JEV improved nDCG@10 by **17.1%** and **8.4%** relative to BM25 alone.
The entire run cost **66.3¢**. Per-search costs above are **fractions of a cent**.

| Full scan + JEV | NFCorpus | SciFact |
|---|---:|---:|
| Average search time | 0.82s | 1.10s |
| Peak search-worker memory | 55.8 MiB | 57.8 MiB |

¹ Recall@100 is the share of known relevant documents in JEV's top 100.
These are text-retrieval results from two BEIR datasets, not the full suite or a
Desktop relevance evaluation. Timings may benefit from the OS file cache;
memory excludes the UI and parent service. Costs and timings vary.

[Full results, uncertainty & published comparisons →](docs/streaming-benchmark.md)

### On a real Desktop

One local test searched for **“budget”** across **21,595 entries** in **3.88 seconds**,
with **48.75 MiB** peak search-worker memory. It streamed **7,566 text files**
(45.8 MB), sampled 13 PDF/Office documents, and searched 14,015 entries by name only.

This is an anecdotal measurement on one Mac, using the default everyday-file
scope—not a claim that every file's contents were read. It used **no API calls**;
JEV reranking would add time and cost. Memory excludes the UI and parent service,
and the OS file cache may have helped.

[Desktop measurement & validation →](VALIDATION.md)

### Under the hood

**Your query → fresh scan → BM25 shortlist → JEV → ranked results**

Text and code are streamed in small chunks. PDFs and Office documents use sampled
text; images are searched by name. No persistent index or search history.

[How search works →](docs/streaming-search.md)

### Try it

Requires **macOS**, **Python 3.12**, and **Node.js 22**.

```sh
git clone https://github.com/assadiandre/jev-search.git
cd jev-search
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pip install --target memory_deps --only-binary=:all: --no-deps -r requirements-streaming.txt
npm ci
npm start
```

Add your OpenRouter key in **Settings** to enable JEV. Without a key, local search
works offline. Run `npm run build` to create **JEV SEARCH Streaming.app**.

### Your files & privacy

JEV searches send your query, candidate paths, and text excerpts to OpenRouter/TypeSafe.
Common credential files are excluded, but filtering is best-effort. Keys entered in
Settings stay in memory for the session; the app can also read `~/Desktop/jev.txt`.
No Keychain access.

---

[Development & limits](docs/streaming-search.md#develop-and-rebuild) ·
[Validation](VALIDATION.md) ·
[Benchmarks](docs/streaming-benchmark.md)
