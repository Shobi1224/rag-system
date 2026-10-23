---
name: metric-sensitivity-and-audit
description: Test whether evaluation metrics actually notice real defects by injecting known faults, and audit the golden question set for quality problems. Use this skill whenever the user asks whether metrics are meaningful or decorative, wants fault injection, wants to check golden set quality, duplicates, bias, or ambiguous expected answers.
---

# Metric sensitivity tests and golden-set audit

## Fault injection (run on a fixed sample of 20-30 questions)
Inject one defect at a time and re-score:
- remove the ground-truth chunk from context
- add 3 distractor chunks
- shuffle context order
- truncate the answer
- replace the answer with a fluent but wrong one
- swap citations between answers
- corrupt a Jira result (wrong status or key)
- force a tool timeout
Expected-movement matrix: write down BEFORE running which metrics should drop and which should stay flat. After running, mark each cell pass or fail. A metric that does not move when it should is decorative; one that moves when it should not is confounded. Save to results/sensitivity.md.

## Golden-set audit
Check and report counts for: duplicate or near-duplicate questions; questions answerable from one chunk only (multi-hop bias); balance of question types; questions with several defensible answers; expected answers not supported by the corpus; leakage (question wording copied from the source); live questions whose snapshot no longer matches. Revise the set, record how many questions changed and why, and version the file (golden_v1, golden_v2). Re-run key experiments on the revised set and report whether conclusions changed.

## Output
results/sensitivity.md, results/golden_audit.md, versioned golden set files.
