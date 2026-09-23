# Streaming search guide

## Open it

After `npm run build`, double-click **JEV SEARCH Streaming.app** in this folder. Use **⌘⌥Space** to
show the search bar, or click its menu-bar search icon. Enter a query and press
Return. The folder button changes the search root; it starts on your Desktop.

The app reads your existing `~/Desktop/jev.txt` key into memory. No key was
copied into the app, and the app does not access Keychain. A key pasted into
Settings overrides it for the current session. Without a key, local streaming
search still works and costs nothing. The interface displays provider-reported
JEV cost for each search.

The Streaming build keeps a separate bundle identifier (`local.jev.search.streaming`) and
settings directory (`~/Library/Application Support/JEV SEARCH Streaming`).
It does not read or change the original app's preferences or encrypted key.

## Search behavior

- Every query walks the chosen folder afresh. Hidden files, generated folders
  and app packages are excluded by default; Settings can include them.
- Text/code files are read in reusable 16 KiB chunks with up to a 32 KiB
  tokenizer segment. Only query-term counts and lengths are retained.
- Names and paths are searched too, including folders and media. Exact names
  get priority. Protected key/credential files are excluded from JEV.
- PDFs and Office files use the original bounded **sampled** extraction. This
  is labeled separately from streamed text. Images have no OCR. Cloud files
  that are not downloaded and symlinks use names only.
- BM25 selects up to 500 local results. JEV reranks at most 128 candidates,
  using excerpts capped at 650 characters and at most four concurrent requests.
  Local results remain when a candidate is not checked by JEV.
- There is no saved index, temporary disk index, search history or cross-query
  text cache. A tiny in-memory FTS table extracts one bounded snippet at a time.

The 500,000-byte text working budget excludes Python objects, query-count arrays,
PDF/Office parser allocations, native-library overhead and transport copies.
Each query runs in a separate process with a 128 MiB SQLite hard allocation cap
and a sampled 256 MiB RSS watchdog (which can overshoot between samples). The
Electron UI and parent service are additional memory. Cancellation terminates
the query worker. The overall worker timeout is five minutes; JEV judging gets
30 seconds after local retrieval. Failed/changed/unsupported text is reported as
unavailable, while filename matching continues. Very long single words exceeding
the tokenizer buffer also fall back to names; no file is silently called fully read.

## Develop and rebuild

Use Python 3.12 and Node.js 22 on macOS. Install dependencies from a fresh checkout:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pip install --target memory_deps --only-binary=:all: --no-deps -r requirements-streaming.txt
npm ci
```

Run from source or build a self-contained `.app` with its own Python runtime:

```sh
npm start
.venv/bin/python -m pytest tests -q
node --test tests/cost.test.cjs
npm run test:renderer
npm run test:window
npm run build
```

The bundled SQLite/tokenizer dependency is APSW 3.51.0.0, in `memory_deps`.
There is no Swift code.

To restore that dependency, use `.venv/bin/python -m pip install --target memory_deps --only-binary=:all: --no-deps -r requirements-streaming.txt`.
See [validation notes](../VALIDATION.md) for packaged-app checks and the actual Desktop
local-search measurement.
