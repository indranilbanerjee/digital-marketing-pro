---
description: An unrelated coding request must not invoke any of this plugin's skills (over-triggering is the context tax showing up as behavior).
tags: [trigger, negative]
max_turns: 4
timeout_seconds: 240
allowed_tools: [Read, Glob, Grep, Skill]
---

Fix this Python function so it returns the second-largest number in a list:

def second(xs):
    return sorted(xs)[1]
