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

### Measured, not guessed

**623 benchmark queries · 0.084–0.130¢ per search**

Measured on the full NFCorpus and SciFact test sets with streaming BM25 + JEV.
These are text-retrieval benchmarks; Desktop results and costs vary.

[Results & methodology →](docs/streaming-benchmark.md)

### Your files & privacy

JEV searches send your query, candidate paths, and text excerpts to OpenRouter/TypeSafe.
Common credential files are excluded, but filtering is best-effort. Keys entered in
Settings stay in memory for the session; the app can also read `~/Desktop/jev.txt`.
No Keychain access.

---

[Development & limits](docs/streaming-search.md#develop-and-rebuild) ·
[Validation](VALIDATION.md) ·
[Benchmarks](docs/streaming-benchmark.md)
