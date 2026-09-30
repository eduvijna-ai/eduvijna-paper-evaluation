# AI quality harness result template

Fill or generate via `python ai/benchmarks/runner.py`.

- Generated at: `{{generated_at}}`
- Manifest: `{{manifest_name}}`
- Provider: `{{provider}}`
- Harness OK (wiring): **{{harness_ok}}**
- Real-paper PASS: **false** (until REAL_PAPER_CORPUS_GATE is satisfied)
- REAL_PAPER_CORPUS_GATE: `EXTERNAL_INPUT_REQUIRED`
- AI_PRODUCTION_PROVIDER_GATE: `EXTERNAL_INPUT_REQUIRED`

## Aggregate metrics

- `student_identity_accuracy`: {{student_identity_accuracy}}
- `answer_region_accuracy`: {{answer_region_accuracy}}
- `question_mapping_accuracy`: {{question_mapping_accuracy}}
- `transcription_accuracy`: {{transcription_accuracy}}
- `evaluation_marking_accuracy`: {{evaluation_marking_accuracy}}
- `teacher_vs_ai_score_agreement`: {{teacher_vs_ai_score_agreement}}

## Notes

- Synthetic / fixed-provider success proves harness wiring only.
- Do not interpret harness_ok as real-paper PASS.
- Do not commit secrets or raw student PII into `results/`.
