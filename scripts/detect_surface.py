#!/usr/bin/env python3
"""
detect_surface.py — which AI harness is this content run executing on?

Consumed by the content-engine's publish-ready step (and /publish-blog) to
decide whether the brand's AI-assistance disclosure applies when
`ai_disclosure.mode` is "claude-surfaces" (the default). Classification is
conservative and the payload carries its evidence:

    {"surface": "claude" | "non-claude" | "uncertain", "basis": [...]}

Fail-safe direction: "uncertain" means the disclosure APPLIES in
claude-surfaces mode. Over-disclosure is harmless; under-disclosure is the
compliance risk — so skipping the disclosure requires an AFFIRMATIVE
non-Claude fingerprint, never the absence of a Claude one.

Stdlib only, env-var evidence only (Cowork sets its session id in env).
"""
from __future__ import annotations

import json
import os
import sys

for _stream in (sys.stdout, sys.stderr):  # UTF-8 output, even where a Windows pipe defaults to cp1252
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_CLAUDE_ENV = (
    "CLAUDECODE",
    "CLAUDE_CODE_SESSION_ID",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_AGENT_SDK_VERSION",
    "ANTHROPIC_COWORK_SESSION_ID",
)

# Best-effort affirmative fingerprints of NON-Claude harnesses. These gate the
# disclosure OFF in claude-surfaces mode, so each must be an identifier the
# harness itself sets — never something a Claude environment could also carry.
_NON_CLAUDE_ENV = (
    "CODEX_SESSION_ID",
    "CODEX_SANDBOX",
    "OPENAI_CODEX_HOME",
    "COPILOT_AGENT_SESSION",
    "COPILOT_CLI_SESSION",
    "CURSOR_SESSION_ID",
    "CURSOR_TRACE_ID",
    "ANTIGRAVITY_SESSION_ID",
    "GEMINI_CLI_SESSION",
)


def classify_surface(env: dict) -> dict:
    """Pure classifier — every input is a plain value, unit-testable."""
    claude_hits = [k for k in _CLAUDE_ENV if env.get(k)]
    non_claude_hits = [k for k in _NON_CLAUDE_ENV if env.get(k)]
    if claude_hits and not non_claude_hits:
        return {"surface": "claude", "basis": claude_hits}
    if non_claude_hits and not claude_hits:
        return {"surface": "non-claude", "basis": non_claude_hits}
    if claude_hits and non_claude_hits:
        return {"surface": "uncertain", "basis": claude_hits + non_claude_hits}
    return {"surface": "uncertain", "basis": []}


def disclosure_applies(mode: str, surface: str) -> bool:
    """The one decision table, shared by tests and the skills.

    - "always"          -> apply
    - "off"             -> never
    - "claude-surfaces" -> apply unless a non-Claude surface is AFFIRMATIVELY
                           detected; "uncertain" applies (fail-safe).
    """
    mode = (mode or "claude-surfaces").strip().lower()
    if mode == "always":
        return True
    if mode == "off":
        return False
    return surface != "non-claude"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Classify the AI harness surface for the disclosure gate")
    parser.add_argument("--mode", default="claude-surfaces",
                        choices=["claude-surfaces", "always", "off"])
    args = parser.parse_args()
    result = classify_surface(dict(os.environ))
    result["mode"] = args.mode
    result["disclosure_applies"] = disclosure_applies(args.mode, result["surface"])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
