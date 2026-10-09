# Eval suite

Run with Claude Code 2.1.269 or later. Every eval run is a real model call and counts against your plan or API bill.

```bash
# skill-routing check (cheap graders, one arm):
claude plugin eval . --tag trigger --ablation none --runs 1 --threshold 0.8
```

`triggers/` holds trigger cases across every skill family in `families.json`, each phrased the way a user would ask without naming the skill, plus unrelated requests (tagged `negative`) that must NOT invoke the plugin. Cases tagged `near-miss` also fail if the confusable sibling skill fires, and run 5 times instead of 3. A failing trigger case means the skill's `description` no longer routes natural requests to it. Results land in `evals/results/` (gitignored).

Every case sets `max_turns: 1`, so the measured quantity is "the model's first action is the right skill" — the thing a description controls. Later turns are subagent work and reference reading (a subagent's turns do not count toward `max_turns`, so a cap of 2 still ran it): on Claude Code 2.1.289 a cap of 1 used about half the usage of a cap of 2 and ran in 6 s instead of 70-90 s, with the same verdict. The run ends with "Reached maximum number of turns (1)"; that is expected, and the Skill call is already in the trace the grader reads. Stay-quiet (`negative`) cases are slightly weaker at this cap: a model that would misfire only in its second turn is not observed.

To measure description wording rather than listing truncation, run with `SLASH_COMMAND_TOOL_CHAR_BUDGET=1000000` in the environment. Without it, the listing budget (context tokens x 4 x 0.01 characters, shared by every installed plugin) truncates descriptions. The variable reaches the eval's child sessions: on 2.1.289 the same case's first-turn prompt was 58,039 tokens with it and 22,995 without.

```bash
SLASH_COMMAND_TOOL_CHAR_BUDGET=1000000 claude plugin eval . --tag trigger --ablation none --no-publish
```

Cases tagged `after-only` (`<skill>-reworded`) re-ask a case that failed, or whose fix borrowed the case's own words, in different phrasing. They were added after the Stage-2 baseline, so they have no "before" result; a fix counts only if its reworded case passes too.

## Known case defects (fix next cycle)

Kept unchanged in Stage 2 so the before/after comparison stays paired:

- `hreflang-check`: the prompt says "Here is the <head> HTML" but attaches none, so the model's first action is to search for HTML files. `hreflang-check-reworded` attaches the tags and is the meaningful measure.
- `seo-audit`: the prompt uses `example.com`, a reserved placeholder domain the model sometimes declines to audit. `seo-audit-reworded` uses a realistic domain.
