# JEV SEARCH: improving recall within a fast search budget

Status: initial changes implemented: bounded fast search, independent content probes, candidate diversity, overlapping work, shared HTTP connections, coverage counts, and an explicit full-pass action. Result filtering now separates broad candidate admission from stricter local matches, applies word boundaries, honors JEV rejection, and labels unchecked results. Group screening and the larger recall benchmark remain planned. Python core, Electron UI, fresh filesystem reads on every query, no pre-indexing or saved content inventory. Everyday files remains the default scope; hidden/generated files remains an explicit option.

## Objective and measured starting point

Aim for useful semantic results within one second on typical everyday searches, while measuring which relevant files are missed. One second is a target to test, not a guarantee of complete semantic coverage.

A local development Desktop run (raw logs are not published) enumerated 21,508 entries, completed in 17.72 seconds, and reported $0.3036 across 681 requests. First local results appeared at 0.13 seconds; first semantic results at 3.03 seconds. A separate warm-filesystem experiment enumerated names without per-entry metadata in about 0.35 seconds. That experiment did not include content reading, ranking, networking, or UI work.

The previous default evaluated every eligible entry with JEV. That behavior is now available through Look wider, which starts a separate fresh full search and resets its cost total. The default fast pass uses at most 128 candidates. Even the broad pass samples document contents, so it is a useful comparison but not a complete ground-truth oracle.

## 1. Give files independent routes into the candidate pool

Simply increasing a filename shortlist preserves its blind spots. Read bounded content from some files that have no filename match, and reserve candidate capacity for that evidence.

| Route | Evidence and selection | What it can rescue |
| --- | --- | --- |
| Names and paths | Exact phrases, word boundaries, typo tolerance, local aliases such as CV/resume, file types, explicit dates | Direct searches, misspellings, common synonyms |
| Content probes | Read eligible text/code in bounded chunks during traversal; search query phrases and aliases before admission | A document whose filename says nothing about its subject |
| Document titles and previews | Read embedded titles or bounded text from a spread of PDFs/Office files with generic names | `document.pdf`, `scan_0042.pdf`, or `final.docx` with useful embedded text |
| Folder context | Use parent names, immediate children, and siblings of locally promising files to nominate candidates | An obscure filename inside a relevant project or alongside a relevant document |
| Exploration | Reserve work across different folders, depths, file types, and low-scoring candidates | Areas systematically neglected by the other routes |

Content probing is essential: it must reach beyond the existing filename winners. Start with inexpensive text reads; PDF/Office parsing gets a smaller, isolated worker budget so one difficult document cannot block early results. Respect the existing read-contents setting, protected-file exclusions, redaction, and cloud-placeholder behavior.

Use a union of these routes, deduplicated by path. An initial experiment could reserve 32 slots for names, 40 for content, 24 for folder context, 16 for document previews, and 16 for exploration: 128 total. These are tuning values, not proven optimal allocations. Redistribute unused capacity and record each candidate's admission reasons.

Apply soft diversity limits so copies or one large folder do not consume the entire pool. Preserve exact matches and allow concentrated results when the query explicitly names a folder. Avoid a default recency bias that buries old documents.

Folder evidence increases priority; a weak folder name must never eliminate its entire subtree. Exploration improves the chance of finding a blind spot but cannot certify coverage. Pure random sampling is weak: 16 uniformly selected files out of 20,000 have only a 0.08% chance of finding one isolated target.

## 2. Test a broader, compact semantic pass

Experiment with sending JEV a wider set of compact paths before paying for rich excerpts. Share directory prefixes, use short IDs, remove redundant metadata, and reduce repeated question wording while preserving record isolation and treatment of file contents as untrusted data.

Two variants should compete at the same cost budget:

- **Individual metadata decisions:** JEV judges many more names/paths with little evidence per file. This may recover conceptual matches missed by local aliases.
- **Group screening:** JEV judges whether a small group of names/paths contains a plausible match; positive or uncertain groups advance to individual inspection. Spread exploration outside the chosen groups.

Group screening could reduce repeated decision overhead, but every supplied name still contributes input cost. Large groups can hide a lone relevant file, and group screening followed by individual judging introduces a dependent network round trip. It must earn its place through recall and latency measurements; it should not become the default exclusion rule on intuition alone.

This pass can rescue a semantic filename mismatch. It cannot discover a topic that exists only inside unread content. JEV produces typed decisions, so free-form query expansion would require another model; keep local aliases on the initial path. See [TypeSafe's model description](https://docs.typesafe.ai/concepts/system-one). Its [retrieval cookbook](https://docs.typesafe.ai/cookbooks/classifying_rag_passages) also separates candidate retrieval from relevance judgment; this design does not adopt the cookbook's stored embeddings.

## 3. Overlap work and control spending

Begin with lightweight entries from `os.scandir`; defer size/date reads until a candidate or explicit query condition needs them. Feed content-probe queues as entries arrive. Submit an early JEV batch when useful candidates are ready, while preserving capacity for later content and exploration discoveries. Breadth-first traversal and rotating probe queues should prevent the first large directory from monopolizing the budget.

Reuse the HTTP client across searches, with correct credential refresh and cancellation isolation. Tune batch size and concurrency against actual payload size and provider response times. Avoid an extra remote query-planning request before retrieval starts.

Use a monotonic deadline plus explicit limits for content bytes, parser jobs, candidate count, requests, retries, and submitted tokens. Treat dollar limits as estimates: API-reported cost arrives after submission, and canceled requests may still be billed. Keep the existing honest cost display.

Within the fast budget, use remaining capacity for underrepresented routes. Additional exploration after that budget requires an explicit **Look wider** action. It can inspect more document sections, expand around JEV-positive siblings, and admit more low-scoring candidates. Keep the full eligible-entry pass available as a separate broader search; do not automatically spend its roughly $0.30 after every fast query.

All candidate and evidence state belongs to the active query. It is discarded when the query is replaced or closed. Look wider can continue that same query, rechecking files before further reads. No Spotlight dependency, embeddings database, saved inventory, or content cache.

## 4. Make coverage understandable

Show time and reported cost alongside concrete coverage, for example:

> 21,508 names checked · 380 files sampled · 128 judged by JEV

Those figures are illustrative. Count unique files and distinguish names checked, content sampled, JEV-reviewed candidates, excluded/unreadable items, and unfinished traversal. A high score on one result says nothing about unread files.

When little evidence is found, offer Look wider. Do not interpret low scores as proof that nothing exists. Even a broader pass cannot guarantee a match hidden on an unread PDF page or in an image without text extraction. OCR would be a separate, slower capability.

## Implementation order and acceptance checks

1. **Establish retrieval quality.** Build a labeled set of approximately 40–60 searches with known targets and distractors. Include opaque names, synonyms, typos, old/deep files, misleading folders, many copies, multilingual terms, late-document evidence, and unsupported image-only documents. Use controlled fixtures plus verified real examples; store evaluation data separately from the runtime search path.
2. **Build the live candidate pipeline.** Separate traversal, candidate selection, and JEV judgment in the Python core. Add lightweight entries, deferred metadata, independent content probes, admission reasons, and diversity. Preserve the current broad mode for comparison.
3. **Add bounded streaming judgment.** Share the HTTP client in the Python service, overlap scanning/reading/API work, and implement deadline/request/byte budgets. Update Electron events and UI with coverage and Look wider. Preserve cancellation isolation, result stability, and billing accounting.
4. **Compare candidate strategies.** Evaluate filename-only, multiple retrieval routes, compact individual JEV screening, and group screening. Compare 64/128/256 candidate budgets. Disable each route in turn to measure its contribution. Count screening and final-ranking calls in total latency/cost.
5. **Choose a default from evidence.** Measure end-to-end time from submission to visible results, p50/p95 time to the first relevant semantic result, final completion, candidate recall, target presence in the top 10, bytes read, and reported dollars. Include first search after launch and repeated queries; label warm filesystem measurements and account for network variance. Report misses separately by file/query class.

Provisional acceptance goals: at least 95% of labeled, supported known-file targets enter the candidate pool, at least 90% appear in the top 10, and p95 time to a relevant result is below one second on the agreed everyday benchmark. These are goals, not measured results; unsupported documents must be reported separately, never silently dropped from the report. Measure broad “find all” queries using recall across all labeled relevant files, since finding one target is insufficient there.

Before setting a default, publish the measured recall/latency/cost tradeoff and inspect individual misses. Retain the previous $0.001–$0.005 fast-search estimate only as a hypothesis until actual billing verifies it. If the one-second goal and recall goal conflict, expose the choice through fast results and explicit wider search rather than claiming complete coverage.

Recommendation: implement independent content retrieval and diversity first. Then test compact semantic screening. Improve admission before optimizing the final ranking, because a ranker cannot return a file it never receives.
