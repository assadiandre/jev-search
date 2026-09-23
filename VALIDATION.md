# Streaming app validation

The following checks were performed on the NEW_JEV experimental copy before
integration into this branch. The full retrieval evaluation is documented in
[the benchmark report](docs/streaming-benchmark.md).

- Built `JEV SEARCH Streaming.app` with a bundled Python 3.12 runtime and APSW.
- macOS ad-hoc signature passed `codesign --verify --deep --strict`.
- 67 Python tests passed, including recursive content search, hidden/generated
  handling, protected files, symlinks, invalid content, fresh edits and supervised
  cancellation.
- Five cost-display tests passed.
- Isolated Electron renderer and native-window tests passed.
- The packaged app passed startup, local search, filters, preview, copied path,
  settings and fresh file add/delete checks.
- The packaged app also passed those checks with live JEV. The first one-file
  fixture request reported $0.000018648; it was billed and marked JEV-checked.
  This is a fixture request, not an estimate for a normal Desktop search.
- The original app's backend files still match the pre-fork manifest hashes.

## Actual Desktop local check

Query: `budget`, with everyday-file defaults and **no API key / no API calls**.
Only aggregate measurements were retained here; document text was not logged.

| Measurement | Result |
|---|---:|
| Entries scanned | 21,595 |
| Text files streamed | 7,566 |
| PDFs/Office documents sampled | 13 |
| Names-only entries | 14,015 |
| Content unavailable | 7 |
| Protected files | 1 |
| Excluded folders | 122 |
| Text bytes read | 45,796,670 |
| End-to-end local time | 3.88 seconds |
| Observed search-worker peak RSS | 48.75 MiB |
| Retained excerpt payload | 15,796 bytes |
| Final phase | Complete |

Unavailable content was reported explicitly; those files were searched by name.
This measurement includes query-worker startup, excludes the Electron UI and
parent service's memory, and may benefit from the operating system's file cache.
JEV judging adds network time and provider-reported cost to a normal keyed search.

## Branch integration checks

On `streaming-bm25` in the original repository: all 67 Python tests and all five
cost-display tests pass. APSW installation is included in CI and fresh-checkout
instructions. Native dependencies, generated app bundles, and credentials are
excluded from Git.

The integrated branch also passes the isolated Electron renderer and native-window
checks, builds the packaged app, verifies its ad-hoc signature, and passes the
packaged-app smoke test (startup, local search, preview, copy, filters, fresh
file changes, and settings). The integration smoke used no API key or charges.
