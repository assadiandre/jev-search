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

### How good is the search?

**Better than keyword search alone. Below the published AI systems shown here.**

We tested all **623 questions** in two public document-search tests. The score
below measures how well useful documents appear near the top of the results.
**Higher is better; 100 is a perfect ranking.** It is not a percentage of searches
answered correctly. Compare systems within each column—the tests differ in difficulty.

| Search system | Health & nutrition documents¹ | Scientific documents² |
|---|---:|---:|
| Keyword search alone (our BM25 baseline) | 32.2 | 68.7 |
| **JEV Search** | **37.7** | **74.5** |
| Jina reranker v3.5 · published | 38.5 | 77.2 |
| Mixedbread large v2 · published | 38.4 | 79.9 |
| Qwen3 reranker 4B · published | 42.5 | 78.0 |

**What does that feel like?** JEV placed at least one known relevant document in
the first five results for **71 out of 100** health queries and **80 out of 100**
science queries, versus **64 and 76** with keyword search alone.

**Comparison note:** We tested JEV and keyword search together. The other scores
come from a [published evaluation](https://arxiv.org/html/2607.18152v1#A1) using an
embedding index to find candidates first. JEV scans fresh. Different candidate
selection means these published numbers provide context, not a controlled head-to-head.

¹ NFCorpus: 323 queries, 3,633 documents. ² SciFact: 300 queries, 5,183 documents.
Scores are nDCG@10 × 100. These tests measure document-text retrieval, not Desktop
filename search or the entire BEIR benchmark suite.

### What does it cost?

**About $1 buys 770–1,190 searches at our measured API costs.**

| Per search | Health test | Science test |
|---|---:|---:|
| Average API cost | **0.084¢** | **0.130¢** |
| Average time, including JEV | 0.82 seconds | 1.10 seconds |
| Peak search-worker memory | 56 MiB | 58 MiB |

All 623 searches cost **66.3¢ total**. These are measurements, not guarantees:
Desktop costs and speed vary. Memory excludes the UI and parent service; the OS
file cache may improve timings.

[Full scores, methods & limitations →](docs/streaming-benchmark.md)

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
