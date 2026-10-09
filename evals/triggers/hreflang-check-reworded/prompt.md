---
description: "After-only reworded case for hreflang-check: different phrasing from the baseline case, never naming the skill."
tags: [trigger, after-only, family-seo]
max_turns: 1
timeout_seconds: 240
allowed_tools: [Read, Glob, Grep, Skill]
---

Validate the alternate-language tags from our homepage <head> and fix anything broken:

<link rel="alternate" hreflang="en-us" href="https://trailforge-outdoors.com/" />
<link rel="alternate" hreflang="en-uk" href="https://trailforge-outdoors.com/uk/" />
<link rel="alternate" hreflang="de" href="/de/" />
