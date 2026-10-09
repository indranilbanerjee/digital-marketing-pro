---
description: "A file-encoding question must not invoke the plugin's data-import or export skills."
tags: [trigger, negative]
max_turns: 1
timeout_seconds: 240
allowed_tools: [Read, Glob, Grep, Skill]
---

When I open a CSV exported from Excel, names show up as 'JosÃ©' instead of 'José'. How do I fix the encoding?
