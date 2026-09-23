# JEV SEARCH

A local Mac app with a **Python search core** and an **Electron / JavaScript UI**. Every query reads the filesystem fresh. There is **no pre-indexing**, embeddings database, saved inventory, content cache, or search history.

## Open the app

JEV lives in the macOS menu bar without a Dock icon. Click its menu-bar icon to show or hide search; right-click for Settings or Quit. Clicking away dismisses the window. Closing the window keeps JEV running.

After building, double-click **JEV SEARCH.app** in this folder, or use **⌘ ⇧ Space** to bring it forward. The default window is a compact, Spotlight-style search bar. Type a query and press Return; results expand below the bar, with cost, coverage, and file previews.

Use **↑ / ↓**, then **Return**, to open a result. Opening a file dismisses the compact window. Escape stops an active search; when results are finished, Escape clears them and collapses the window. Escape from the empty bar hides it. Clearing the query also collapses the window. Nothing searches automatically while you type.

The folder and gear buttons beside the input open scope selection and settings. The expand arrow opens the full workspace; its collapse button returns to the small bar. Expanded mode keeps the same simple search bar, with more room for results and file details. Both views use a neutral light palette, rounded controls, and the same search engine. Settings temporarily enlarge the compact window, then restore its previous size when closed.

The Desktop is the default location. Settings control the API key, hidden/generated files, content reading, and parallel requests. **⌘ K** focuses the query.

**Search cost** is displayed above the results in USD. It updates with OpenRouter's reported costs as responses arrive, remains visible when the search finishes, and resets on the next search. Stopped or incomplete searches show **Reported cost**, since canceled or unreported requests may still be billed. Missing billing data is marked as unavailable. Filename-only searches cost $0. Look wider starts a separate full search with a new cost total.

## How it works

1. Python uses lightweight `os.scandir` traversal to enumerate the entire selected scope fresh. Names and paths are checked while the walk runs; size/date reads are deferred. Unread metadata is shown as “Not read yet.”
2. **Fast search** checks up to 128 distinct candidates with JEV. Independent routes admit filename/path matches, local synonyms, content matches, folder context, document previews, and exploration. Directory diversity prevents one folder from consuming every candidate slot. Unused slots are redistributed.
3. Content probes run during traversal, including files with no filename match. They rotate across folders, with up to 384 text/code and 16 PDF/Office attempts within a 0.6-second launch window. Slow readers have bounded concurrency; unfinished work is discarded when the fast pass ends. Literal local text matches can appear before semantic judgment, labeled **TEXT · Not JEV-checked**.
4. An early JEV batch can start before the walk finishes. Fast search uses at most four parallel API calls and an eight-request ceiling including retries/splits. A three-second overall API deadline bounds provider waiting; a slow filesystem walk may itself take longer. The normal completion target remains one second, not a guarantee.
5. **Look wider** starts a new, fresh full pass that evaluates every eligible entry with richer excerpts. It has its own cost total, reset to zero, and incurs additional API charges. This broader pass never starts automatically. The full pass uses the configured concurrency (12 by default).
6. Results show names checked, files with sampled text, entries judged by JEV, elapsed time, and actual reported cost. A completed fast pass does not mean every file's contents were inspected. Both modes avoid following symlinks and skip cloud placeholders when reading content.

The Python service reuses HTTP connections across queries and refreshes them when the API key changes. File inventories, excerpts, and candidate pools remain confined to one search; there is no persistent cache or index.

Progress-only updates send small counters instead of repeating unchanged file excerpts. The interface reuses result rows and updates only changed content, so a busy search can keep its cost and progress displays current without rebuilding the results list.

The default **Everyday files** scope skips hidden entries and the contents of dependency/build folders and app bundles. Visible generated folders themselves can still appear. Enable **Include hidden & generated files** to traverse those contents too. Symlinks are listed but never followed; unreadable entries are counted. Nothing is scanned before you submit a query.

## Result filtering

Candidate discovery stays broad; the visible list uses stricter rules:

- Local filename matches require all significant query words in the file's own name, at word boundaries. Spaces, punctuation, underscores, camelCase, and numbers are separated correctly. `cat` does not match `vacation.jpg`; `annual budget` can match `annualBudget_2024.txt`.
- Partial names, parent-folder context, aliases, and scattered content keywords can nominate JEV candidates, but cannot independently qualify as visible results. A literal phrase in sampled content can appear provisionally.
- Every local result is labeled **Not JEV-checked**. After JEV evaluates an entry, its decision controls visibility: scores below 0.6 remove the result, including any earlier local match. Delayed local updates cannot resurrect a rejected result.
- JEV-approved results rank by their JEV score and appear ahead of unchecked local matches. A keyword score no longer inflates a low semantic score. The results count separately identifies unchecked matches.

These rules apply to both fast and full search. Provider failures retain clearly labeled local matches, and every new query starts with fresh decisions. The 128-candidate default, request limits, connection reuse, and billing behavior are unchanged. JEV judgments remain probabilistic; these changes address the local filtering errors, not every possible relevance error.

## Content coverage

- Fast text/code probes: up to 32 KB per file, sampling the start/middle/end of larger files. Excerpts favor query terms and local aliases.
- Fast PDF probes: the first two pages of files under 2 MB. Fast Office probes: bounded XML extraction, up to 128 KB, from files under 2 MB. These probes are selective; generic filenames do not prevent a file from being considered.
- Full-pass text/code reads: up to 192 KB; larger files sample the start, middle, and end.
- Full-pass PDFs: text from up to eight pages distributed through documents under 80 MB.
- Full-pass DOCX, PPTX, XLSX, ODT: bounded XML extraction from archives under 50 MB. RTF receives basic text extraction.
- Full-pass folders: up to 24 immediate child names, plus their own name and path. Fast folder candidates use names and paths.
- Images, audio, video, unsupported/binary formats, scanned PDFs without embedded text, and cloud placeholders: name and path only. There is no OCR or media transcription.

This is a fast relevance search over metadata and sampled text, not an exhaustive byte-by-byte search inside every file. Search speed depends on file count, file formats, network latency, and provider limits. A complete semantic pass can take longer than the first useful results. Stop keeps the matches found so far. API failures are displayed, and filename results remain usable offline.

## Credentials and data

The API key is encrypted with Electron `safeStorage`, backed by macOS Keychain. Only encrypted credentials and preferences are saved in `~/Library/Application Support/JEV SEARCH/`. The key stays in the Electron main process and Python service, never the renderer. The two processes communicate over private stdin/stdout pipes; no local web server or public port is exposed.

Queries, relative paths, filenames, and bounded excerpts are sent to OpenRouter/TypeSafe to perform searches. Common credential files—including `jev.txt`, `.env` files, private keys, and keychains—are excluded from remote classification. Common token patterns are redacted from other excerpts. This is a best-effort filter, not a general secret detector. File contents are treated as untrusted data in the model request.

## Develop

This repository contains source code, not a prebuilt app. Development and packaging target macOS. Add your own OpenRouter API key in Settings for JEV semantic search; without a key, filename search works locally. The `~typesafe/jev-latest` model and alpha endpoint must be available to your OpenRouter account.


Requires Python 3.12+ and Node.js 22+ for development; the packaged app includes both runtimes and works without a development environment.

```sh
git clone git@github.com:assadiandre/jev-search.git
cd jev-search
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
npm ci
npm start
```

```sh
npm test                       # Python behavior and failure-path tests
npm run test:renderer           # Isolated renderer / keyboard behavior
npm run test:window             # Native compact/workspace resizing; no API or Keychain access
node tests/electron-smoke.cjs   # Real Electron UI / Python integration
npm run build                  # Bundle Python and build a local Mac .app
```

The build uses PyInstaller and Electron Packager. The app is signed ad hoc for this Mac, not notarized for distribution. `package-lock.json` and `requirements-lock.txt` pin the tested dependencies. Source is in `backend/`, `electron/`, and `ui/`; `scripts/build.cjs` creates the application bundle. Tests use temporary fixtures and mocked API responses, and the smoke test uses an isolated settings directory (`JEV_USER_DATA_DIR`). An explicitly configured `JEV_KEY_FILE` enables paid API calls in that optional smoke test.

The request structure follows [OpenRouter’s JEV batching example](https://openrouter.ai/labs/jev/compile). The renderer uses the isolation pattern in [Electron’s context isolation documentation](https://www.electronjs.org/docs/latest/tutorial/context-isolation).

## Initial fast-pass measurements

Three live searches over approximately 21,500 Desktop entries completed in **1.11–1.45 seconds**, each using **4 requests / 128 candidates**, and reporting **$0.00121–$0.00135**. The earlier broad-pass baseline was 17.72 seconds and $0.3036. These are observed runs, not a p95 guarantee or a recall benchmark. Results depend on filesystem warmth, query, content readers, and the provider. These measurements came from local development runs; raw logs are not included in the repository.

Tests cover content-only retrieval behind vague text/PDF filenames, filename crowding, directory diversity, content-disabled searches, new files in a fresh full pass, cancellation, request budgets, billing, and renderer mode/coverage behavior. Compact group screening, fuzzy spelling, and a larger labeled recall evaluation remain future work; see [SEARCH_PLAN.md](SEARCH_PLAN.md).

## Contributing

Run `npm test` before submitting a change. For UI changes, also run `npm run test:renderer` and `npm run test:window` on macOS. Keep credentials, personal file samples, search logs, and app bundles out of commits. Use synthetic fixtures when reporting search bugs. Regenerate the icon assets with `.venv/bin/python scripts/make-icon.py`.
