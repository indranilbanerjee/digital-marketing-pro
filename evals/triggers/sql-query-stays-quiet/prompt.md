---
description: "A data request with no marketing job in it must not invoke any of this plugin's skills."
tags: [trigger, negative]
max_turns: 1
timeout_seconds: 240
allowed_tools: [Read, Glob, Grep, Skill]
---

Write a SQL query that returns the top 10 customers by total order value from a table orders(customer_id, amount, created_at), for orders placed this year.
