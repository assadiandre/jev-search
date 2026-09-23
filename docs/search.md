# Search details

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

