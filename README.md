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

<p align="center">
  <img src="assets/demo.gif" alt="JEV Search on the Desktop">
</p>

---

Search files, documents, and code with **⌘⌥Space**. Fresh local retrieval,
JEV relevance ranking, and live API costs.

### Benchmarks

**623 queries · 66.3¢ total · No saved index**

| Full test set | NFCorpus | SciFact |
|---|---:|---:|
| Documents / queries | 3,633 / 323 | 5,183 / 300 |
| Ranking score: BM25 → JEV¹ | 0.322 → **0.377** | 0.687 → **0.745** |
| Relevant result in top 5 | **70.9%** | **80.3%** |
| Relevant documents found in top 100 | 25.5% | 92.9% |
| Average API cost / search | **0.084¢** | **0.130¢** |
| Average time, including JEV | 0.82s | 1.10s |
| Peak search-worker memory | 55.8 MiB | 57.8 MiB |

¹ nDCG@10: higher means better-ranked results. Complete text-retrieval test sets;
Desktop performance varies. Memory excludes UI/parent; file caching may help timing.
[Full methodology →](docs/streaming-benchmark.md)

### On a real Desktop

**21,595 entries · 3.88 seconds · 48.75 MiB worker memory**

One local-only “budget” search: 7,566 text files streamed, 13 documents sampled,
14,015 entries searched by name. No API calls; JEV adds time and cost. One Mac,
potentially cached files; UI/parent memory excluded. [Details →](VALIDATION.md)

### How it works

**Fresh scan → BM25 shortlist → JEV → ranked results**

Streams text/code; samples PDFs/Office; searches images by name. JEV checks up to
128 candidates. No persistent index or search history. [Search guide →](docs/streaming-search.md)

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

### Privacy

JEV sends queries, candidate paths, and excerpts to OpenRouter/TypeSafe.
Credential filtering is best-effort. Settings keys stay in memory; `~/Desktop/jev.txt`
is also supported. No Keychain access.

---

[Development & limits](docs/streaming-search.md#develop-and-rebuild) ·
[Validation](VALIDATION.md) · [Benchmarks](docs/streaming-benchmark.md)
