# Eval suite

Run with Claude Code 2.1.269 or later. Every eval run is a real model call and counts against your plan or API bill.

```bash
# skill-routing check (cheap graders, one arm):
claude plugin eval . --tag trigger --ablation none --runs 1 --threshold 0.8
```

`triggers/` holds one case per headline skill, phrased the way a user would ask without naming the skill, plus one unrelated request that must NOT invoke the plugin. A failing trigger case means the skill's `description` / `when_to_use` no longer routes natural requests to it. Results land in `evals/results/` (gitignored).
