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

### Ranking

Across 623 test questions, JEV put a relevant result in the top 5 about **7 times
out of 10** on a hard set (NFCorpus, 70.9%) and **8 times out of 10** on a
science set (SciFact, 80.3%). Plain word-matching scored 0.322 and 0.687. JEV
moved those to **0.377** and **0.745**. Each search cost about **a tenth of a
cent**.

JEV takes the same candidates and moves the right one higher. On the hard set,
many relevant documents never reach JEV, so this is a ranking result.

### On a real Desktop

**21,595 entries · 3.88 seconds · 48.75 MiB worker memory**

One local-only “budget” search: 7,566 text files streamed, 13 documents sampled,
14,015 entries searched by name. No API calls; JEV adds time and cost. One Mac,
potentially cached files; UI/parent memory excluded.

### How it works

Every search starts from scratch. Nothing is saved from the last one.

The app walks the folder you chose and looks at each file. It always checks the
name. For text and code, it reads the file and counts how often your words show
up. PDFs and Office files get a short sample. Pictures and other files are
matched by name only.

Those matches are ranked by how well the words fit, and the best ones stay. If
you have an API key, JEV reads the top 128 and moves the ones that actually
match what you meant to the top. Files JEV does not check stay in the list as
local matches.

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
