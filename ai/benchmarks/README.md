# PREPROD-003 — AI quality harness (scaffolding)

Independent, versioned quality metrics for EduVijna paper evaluation. This harness
is **separate from** the in-product B15 gold regression service
(`apps/api/app/ai/providers/benchmark.py`, `apps/api/app/services/benchmark.py`).
B15 remains the locked gold/regression path inside the API; this package is the
pre-production **corpus/metrics** harness for offline scoring and reports.

## Gate: real paper corpus

```
REAL_PAPER_CORPUS_GATE = EXTERNAL_INPUT_REQUIRED
```

Do **not** claim real-paper PASS until an authorized (or licensed) paper corpus is
supplied. Synthetic / fixed-provider fixtures may only prove harness wiring.

Related production gate: `AI_PRODUCTION_PROVIDER_GATE` in
[`docs/production/AI_PROVIDER_READINESS.md`](../../docs/production/AI_PROVIDER_READINESS.md).

## Independent metrics

Each metric is scored separately (no single blended “AI quality” score that hides
weak dimensions):

| Metric key | Meaning |
|------------|---------|
| `student_identity_accuracy` | Correct student/roster match vs gold identity |
| `answer_region_accuracy` | Correct crop/region detection vs gold regions |
| `question_mapping_accuracy` | Region → question mapping vs gold mapping |
| `transcription_accuracy` | Text/LaTeX transcription vs gold transcript |
| `evaluation_marking_accuracy` | AI proposed marks vs gold marks |
| `teacher_vs_ai_score_agreement` | Agreement between teacher final and AI proposal |

## Supported case categories (manifests)

Manifest cases may declare one or more of:

`clean_handwriting`, `poor_handwriting`, `crossed_out`, `continuation`, `faint`,
`rotated`, `pen_colors`, `math`, `equations`, `fractions`, `tables`, `diagrams`,
`incomplete`, `alternate_methods`, `multi_subject`, `multilingual`

## Layout

```
ai/benchmarks/
  README.md
  runner.py                 # CLI runner (fixed provider + safe fixtures)
  scoring.py                # Metric helpers
  report.py                 # Result report writer
  manifests/v1/
    schema.json             # Versioned manifest schema
    fixtures.example.yaml   # Authoring example (all categories illustrated)
    fixtures.safe.json      # Credential-free runnable fixture for CI/local
  templates/result_report.md
  results/                  # Generated reports (gitignored except keepers)
```

## How to run (safe / fixed provider)

From repo root (Python 3.12+; no OpenAI key required for safe fixtures):

```bash
python ai/benchmarks/runner.py \
  --manifest ai/benchmarks/manifests/v1/fixtures.safe.json \
  --provider fixed \
  --out-dir ai/benchmarks/results
```

- `--provider fixed` uses expected/gold fields inside the manifest (deterministic).
- OpenAI / production provider runs require credentials and remain gated by
  `AI_PRODUCTION_PROVIDER_GATE = EXTERNAL_INPUT_REQUIRED`.
- Report JSON + Markdown are written under `results/` and **must not** set
  `real_paper_pass: true` unless `REAL_PAPER_CORPUS_GATE` is satisfied.

## Relationship to B15

| Concern | B15 gold regression | This harness |
|---------|---------------------|--------------|
| Location | API service + DB models | Offline `ai/benchmarks/` |
| CI fixture models | `fixed-benchmark-*` | Manifest cases + fixed scorer |
| Ledger writes | Forbidden | Forbidden |
| Real-paper claim | Not a paper corpus gate | Explicitly EXTERNAL_INPUT_REQUIRED |

Extend B15 for in-product regression; extend this harness for corpus categories and
independent metric reports.

## Safety

- No secrets in manifests or results.
- Do not point corpus paths at founder MAT object storage.
- Do not destroy MAT volumes while collecting fixtures.
