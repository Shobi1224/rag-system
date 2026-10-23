---
name: judge-validation
description: Validate the LLM judges used to score RAG answers by comparing them to human labels, measuring agreement, kappa, test-retest stability, and comparing judge prompts or models. Use this skill whenever the user wants to trust, check, calibrate, or compare LLM-as-judge scores (faithfulness, correctness, relevancy), create human labels, or asks how reliable the evaluation is.
---

# Judge validation

## Goal
Know how far each judge score can be trusted, and where it fails.

## Procedure
1. Sample 50-60 answers from existing runs, stratified by question type (static, Jira, mailing list, combined, out of scope) and including both good and bad outputs.
2. Hand-label BEFORE looking at any judge score. Save to eval/labels/labels.csv: run_id, question_id, correctness (correct | partial | wrong), faithful (yes | no), refusal_appropriate (yes | no | n/a), notes.
3. Run each judge (judge prompt A, B, optionally a second model) on the same answers at temperature 0.
4. Compute per judge and per metric: raw agreement, Cohen's kappa, confusion matrix, and the three most informative disagreements (with the answer text).
5. Test-retest: rerun each judge 3 times on the same items; report the share of items whose label changes.
6. Pick the judge with the best agreement, freeze its prompt in eval/judges/ with a version tag, and record its agreement numbers next to every report that uses it.

## Reporting rules
- Show counts and a confidence interval (e.g. Wilson) with each agreement figure; with about 50 items, say the estimate is rough.
- Show where the judge fails (for example it over-credits fluent but unsupported answers).
- If agreement is poor, say so and either fix the rubric or mark the metric as untrusted in the report.

## Output files
eval/labels/labels.csv, results/judge_validation.md (tables plus examples), eval/judges/<name>_v<k>.txt
