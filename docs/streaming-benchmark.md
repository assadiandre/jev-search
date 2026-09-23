# Full streaming BM25 + JEV evaluation

Complete official query IDs, source/export/query hashes, recomputed metrics, complete billing, unique result IDs verified.

Official test qrels select every test query. One isolated query worker at a time; freshly reads all text exports. No training labels enter worker. No full-corpus index. BM25 baseline uses the same pre-JEV ranking. Existing 100-query subsets remain separately identifiable.

Model: `~typesafe/jev-latest`; top 128 reranked using up to 650 characters per document; top 500 local results retained. No persistent or full-corpus in-memory index. Each query scans all exported document text.

| Dataset | Queries | BM25 nDCG@10 | JEV nDCG@10 | BM25 / JEV success@5 | BM25 / JEV Recall@100 | Mean API cost |
|---|---:|---:|---:|---:|---:|---:|
| nfcorpus | 323 | 0.3223 | 0.3773 | 64.4% / 70.9% | 24.9% / 25.5% | 0.0843¢ |
| scifact | 300 | 0.6874 | 0.7451 | 76.3% / 80.3% | 92.5% / 92.9% | 0.1301¢ |

Total reported API cost across all attempts: **$0.662579 (66.258¢)**. BM25 alone makes no API calls.

## Timing and memory

| Dataset | Mean / median / p95 seconds | Maximum worker RSS | Max query counts | Max retained excerpts |
|---|---:|---:|---:|---:|
| nfcorpus | 0.819 / 0.784 / 1.254 | 55.8 MiB | 377,728 bytes | 53,350 bytes |
| scifact | 1.103 / 1.004 / 1.483 | 57.8 MiB | 1,200,136 bytes | 55,571 bytes |

Times include isolated worker startup and remote API calls; operating-system file cache may be warm. RSS excludes the UI and benchmark parent. The 500,000-byte text working budget is not a total process memory limit. Query counts and metadata are additional. Worker RSS watchdog: 256 MiB, sampled every 50 ms; SQLite heap cap: 128 MiB.

## Earlier samples and remaining queries

| Dataset / split | Queries | BM25 nDCG@10 | JEV nDCG@10 | Paired delta, bootstrap 95% interval |
|---|---:|---:|---:|---:|
| nfcorpus / all | 323 | 0.3223 | 0.3773 | +0.0550 [+0.0402, +0.0701] |
| nfcorpus / previous100 | 100 | 0.3124 | 0.3751 | +0.0627 [+0.0372, +0.0898] |
| nfcorpus / remaining | 223 | 0.3268 | 0.3783 | +0.0515 [+0.0339, +0.0699] |
| scifact / all | 300 | 0.6874 | 0.7451 | +0.0576 [+0.0190, +0.0961] |
| scifact / previous100 | 100 | 0.6917 | 0.7862 | +0.0945 [+0.0339, +0.1597] |
| scifact / remaining | 200 | 0.6853 | 0.7245 | +0.0392 [-0.0079, +0.0869] |

Bootstrap uses 10,000 paired query resamples, seed 20260923. Intervals measure query sampling uncertainty, not repeated-model variability. NFCorpus remaining queries were evaluated with earlier algorithms, so they are not a new untouched holdout.

## Interpretation

These are the complete NFCorpus and SciFact official test splits, not the entire BEIR suite. They test text-content retrieval on exported documents, not Desktop filename matching, PDF extraction, OCR, or the app UI. The Desktop fork has additional routing and filename behavior, so these scores do not directly measure it.

Published modern reranker reference values from Jina-reranker-v3.5 Table 6: NFCorpus / SciFact nDCG@10: Jina v3.5 0.3845 / 0.7715; Mixedbread large v2 0.3843 / 0.7993; Qwen3 4B 0.4248 / 0.7795. Their candidates come from Jina embeddings (top 100), whereas this run uses fresh BM25 (top 128). These are context, not a controlled comparison or proof of state of the art. [Primary paper](https://arxiv.org/html/2607.18152v1#A1).

The benchmark run is `full623-v1` in the separate JEV_SEARCH_BENCHMARK workspace. Raw per-query rankings, billing, query lists, and source snapshots remain there; they are not bundled with this app repository.
