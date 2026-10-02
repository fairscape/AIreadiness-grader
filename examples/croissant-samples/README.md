# Croissant samples

Six public Croissant files, saved unmodified. Each has downloadable data and
carries `rai:` properties written by the dataset authors. Each folder holds
`metadata.json`, plus `review/` with the HTML page, the evidence JSON and
`automated-score.json` (see `../score_estimates.py`). Fetched 2026-10-02.

| folder | source | `rai:` | fields | score before → after the Croissant fixes* |
| --- | --- | --- | --- | --- |
| `security-gym-v4` | [j-klawson/security-gym](https://github.com/j-klawson/security-gym) `data/croissant.json` | 16 | 14 | 49.4 → 63.7 (see its README for the standard-vocabulary maximum) |
| `fragbench` | [LidaSafety/fragbench](https://github.com/LidaSafety/fragbench) `docs/croissant.json` (Croissant 1.1) | 21 | 31 | 36.3 → 47.0 |
| `bigcode-the-stack` | mlcommons/croissant `datasets/1.0/bigcode-the-stack` | 9 | 26 | 32.7 → 45.8 |
| `amazon-application-eval-data` | [amazon-science/application-eval-data](https://github.com/amazon-science/application-eval-data) | 9 | 8 | 29.8 → 45.2 |
| `delibsim-bench` | huggingface.co/datasets/anonymous-submissions/delibsim-bench `croissant.json` | 6 | 188 | 31.5 → 36.9 |
| `sustaincluster-weather` | [HewlettPackard/sustain-cluster](https://github.com/HewlettPackard/sustain-cluster) `metadata/weather.jsonld` | 3 | 18 | 24.4 → 29.8 |

\* Overall % of the automated estimates, `--no-network` (security-gym-v4 "after" is the network run). The `review/`
folders were run with network checks.

Things these files exercise:

- **License spellings**: an SPDX-style string (`CC BY 4.0` in amazon), `other`
  (bigcode), and IRIs.
- **Source links**: root `isBasedOn` source links (security-gym, fragbench,
  delibsim).
- **Containment**: a `FileSet` inside a repo `FileObject` (amazon, bigcode).
- **RAI spellings**: `rai:dataCollectionTimeFrame` vs `Timeframe` (amazon), and
  the non-standard `rai:dataNotIntendedUseCases` (security-gym).
- **Example records**: inline `examples` on a RecordSet (weather).
- **Zenodo DOIs**: in `sameAs` (security-gym, the only sample that reaches 0.a = 2).
- **Bad URLs**: GitHub `tree/` page URLs used as `contentUrl` (weather). These
  are not raw files, and the grader does not flag them yet.
