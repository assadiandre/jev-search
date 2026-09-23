<p align="center">
  <img src="assets/icon.png" alt="JEV Search logo" width="128" height="128">
</p>

# JEV Search

Find files in your own words with **JEV**. JEV Search uses the model to judge which files match your query, based on their names, paths, and text excerpts.

**No pre-indexing. Every search scans your files fresh.**

- Search filenames and text from PDFs, documents, and code.
- See results, file previews, and API cost as they arrive.
- Use **Look wider** when you need a broader search.

## Search algorithm

JEV scores file relevance. Local retrieval first narrows a fresh filesystem scan into a small set of candidates, keeping model calls bounded.

```mermaid
flowchart TD
    A[Your query] --> B[Normalize, tokenize, expand known synonyms]
    B --> C[Fresh filesystem scan + selective text sampling]
    C --> D[Select up to 128 candidates]
    D --> E[Batch relevance scoring with JEV via OpenRouter]
    E --> F[Filter and rank results]
    C --> G[Provisional local matches]
    G --> F
```

1. **Prepare the query locally.** Trim and normalize the text, split it into words, remove common filler words, and use a small built-in synonym list, such as `resume ↔ CV`. JEV does not rewrite or interpret the query before scanning.
2. **Discover candidates.** Walk the chosen folder afresh, matching names and paths while selectively reading text excerpts. Hidden and generated directories are skipped by default. Content probes can discover relevant files even when their names do not match.
3. **Build a diverse shortlist.** Reserve slots for name matches, content matches, folder context, document previews, and exploration. Spread selections across directories and redistribute unused slots. Fast search selects at most **128 distinct candidates**.
4. **Ask JEV for relevance.** Send the original query, candidate metadata, and available excerpts in batches through OpenRouter. An early batch can start while scanning and sampling continue. Fast search allows up to four concurrent requests.
5. **Filter and rank.** Strong local name or literal text matches can appear immediately as **Not JEV-checked**. JEV scores below **0.6** remove a candidate, including a provisional match. Accepted candidates rank by JEV score ahead of unchecked local matches. Reported API cost updates as responses arrive.

The stages overlap; the diagram shows data flow, not a sequence of blocking steps. Fast search trades exhaustive coverage for latency and cost. **Look wider** starts a fresh, broader pass over eligible entries, with richer sampled excerpts and additional API cost. Neither mode builds a persistent index.

[Search limits and content coverage →](docs/search.md)

## Quick start

Requires **macOS**, **Python 3.12+**, and **Node.js 22+**.

```sh
git clone https://github.com/assadiandre/jev-search.git
cd jev-search

python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
npm ci
npm start
```

Add your OpenRouter API key in **Settings** to enable semantic search. Your account needs access to `~typesafe/jev-latest`. Without a key, local filename search works offline.

## Build

```sh
npm run build
```

Creates `JEV SEARCH.app` in the project folder, with Python bundled. Builds are locally signed, not notarized for distribution.

## Privacy

Semantic searches send your query, relative file paths, and sampled text to OpenRouter/TypeSafe. API keys are encrypted using macOS Keychain. No search index or history is saved.

Common credential files are excluded and common token patterns are redacted, but this is a best-effort filter. Only search folders you are comfortable sending excerpts from.

## Development

```sh
npm test                 # Python and cost tests
npm run test:renderer    # UI and keyboard behavior
npm run test:window      # Native window behavior
```

Issues and pull requests are welcome. Use synthetic files for bug reports and run the relevant tests before submitting changes. See [the search roadmap](SEARCH_PLAN.md) for planned work.

Implementation: Python search core in `backend/`, with a small Electron shell in `electron/` and interface in `ui/`.
