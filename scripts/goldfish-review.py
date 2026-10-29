#!/usr/bin/env python3
"""
goldfish-review.py
==================
A zero-context review of a client deliverable, before the client reads it.

Whoever wrote a plan knows what it assumes, so they read past the gaps. A reviewer that
has seen nothing else, a goldfish, reads it the way the client will. That holds only if
the reviewer is really handed nothing else, so this script writes the review's whole
input to one file, the packet, holding exactly three things: the deliverable, the brief
it answers, and the brand profile. No conversation, notes, memory or other files.

Actions:
    pack    write the packet.
    check   the deterministic first pass, on the packet alone: a money figure the brief and
            profile never state (an unstated budget, fee or forecast), and a benchmark rate
            (CTR, CPC, ROAS, conversion rate, "industry average" ...) with no source on its
            line and no match in the brief or profile. A figure the deliverable marks as an
            assumption or estimate, or as the plan's own target, is stated, not hidden.
    prompt  the reviewer's instructions, naming only the packet. Hand it unchanged to a
            subagent (the quality-assurance agent); on a host without subagents, run it in a
            fresh turn, which is weaker, and the output says so.

Usage:
    python goldfish-review.py --action pack --deliverable plan.md --brief brief.md --brand acme [--out FILE]
    python goldfish-review.py --action check --packet FILE
    python goldfish-review.py --action prompt --packet FILE [--no-subagents]

Exit codes: 0 done (check: nothing found); 1 a file could not be read or written;
2 bad arguments; 3 check found something the deliverable must answer before it goes out
(the same BLOCKED code as eval-runner.py).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: E402

EXIT_BLOCKED = 3
MAX_BYTES = 2 * 1024 * 1024
CONTRACT = ("deliverable", "brief", "brand_profile")

MULT = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mn": 1e6, "million": 1e6, "bn": 1e9, "billion": 1e9,
        "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "l": 1e5, "crore": 1e7, "crores": 1e7, "cr": 1e7}
CURRENCY = r"(?:₹|\$|€|£|¥|Rs\.?|INR|USD|EUR|GBP|AED|SGD|AUD|CAD)"
NUMBER = r"\d[\d,]*(?:\.\d+)?"
UNIT = r"(?:k|K|m|M|mn|bn|thousand|million|billion|lakhs?|lac|L|crores?|[Cc]r)\b"
MONEY = re.compile(rf"(?:{CURRENCY}\s?(?P<a>{NUMBER})\s?(?P<au>{UNIT})?|(?P<b>{NUMBER})\s?(?P<bu>{UNIT})?\s?(?:{CURRENCY}|rupees?|dollars?|euros?|pounds?)\b)")
ANY_NUMBER = re.compile(rf"(?P<n>{NUMBER})\s?(?P<u>{UNIT}|%)?")
BENCHMARK_TERMS = re.compile(
    r"(?i)\b(CTR|click-through rate|CPC|CPM|CPA|CPL|CAC|ROAS|ROI|conversion rate|open rate|click rate|"
    r"engagement rate|bounce rate|churn rate|benchmark|industry average|on average|typical(?:ly)?|"
    r"average\s+\w+\s+rate)\b")
RATE = re.compile(r"(?P<n>\d+(?:\.\d+)?)\s?(?P<u>%|x|×)")
CITED = re.compile(r"(?i)(https?://|\bsource[sd]?\b|according to|\(\s*\w[^)]*,\s*(?:19|20)\d{2}\s*\)|\[\d+\]|\bper\s+[A-Z][\w&.-]+|reported by|\bcited\b)")
DECLARED = re.compile(r"(?i)\b(assum\w*|estimat\w*|to (?:be )?confirm\w*|illustrative|hypothetical|placeholder|"
                      r"tbc|tbd|scenario|if the budget|target\w*|goal\w*|aim\w*|forecast\w* range)\b")


class UsageError(Exception):
    pass


def _value(num: str, unit: str | None) -> float:
    n = float(num.replace(",", ""))
    if unit and unit != "%":
        n *= MULT.get(unit.lower(), 1)
    return n


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= max(1e-9, 0.005 * max(abs(a), abs(b)))


def stated_values(*texts: str) -> list:
    out = []
    for text in texts:
        for m in ANY_NUMBER.finditer(text or ""):
            try:
                out.append(_value(m.group("n"), m.group("u")))
            except ValueError:
                pass
    return out


def _read(path: Path, what: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"{what} not found: {path}")
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError(f"{what} is larger than {MAX_BYTES // (1024 * 1024)} MB: {path}")
    return _common.decode_text(raw, path.name)


def pack(deliverable: Path, brief: Path, brand: str | None, out: Path | None) -> dict:
    profile = None
    if brand:
        bdir, err = _common.get_brand_dir(brand)
        if err:
            raise UsageError(err)
        profile = _common.load_profile(bdir / "profile.json") if (bdir / "profile.json").is_file() else None
        if profile is None:
            raise UsageError(f"brand {brand!r} has no profile.json; run /digital-marketing-pro:brand-setup")
    packet = {
        "deliverable": {"name": deliverable.name, "text": _read(deliverable, "deliverable")},
        "brief": {"name": brief.name, "text": _read(brief, "brief")},
        "brand_profile": {"slug": _common.slugify_brand(brand), "profile": profile} if brand else None,
    }
    if out is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base = _common.brand_dir(brand) if brand else _common.workspace_root()
        out = base / "reviews" / "goldfish" / f"{_common.safe_slug(deliverable.stem, 'deliverable')}-{stamp}.json"  # path-safe: safe_slug output and a timestamp
    _common.atomic_write_json(out, packet)
    return {"action": "pack", "packet": str(out), "contract": list(CONTRACT),
            "sizes": {"deliverable_chars": len(packet["deliverable"]["text"]), "brief_chars": len(packet["brief"]["text"]),
                      "brand_profile": bool(profile)},
            "next": "run --action check on the packet, then --action prompt for the reviewer"}


def load_packet(path: Path) -> dict:
    packet = _common.read_json(path)
    if not isinstance(packet, dict) or set(packet) != set(CONTRACT):
        raise UsageError(f"{path} is not a goldfish packet: it must hold exactly {', '.join(CONTRACT)} "
                         f"(it holds {', '.join(sorted(packet)) if isinstance(packet, dict) else type(packet).__name__})")
    for key in ("deliverable", "brief"):
        item = packet[key]
        if not isinstance(item, dict) or set(item) != {"name", "text"} or not isinstance(item["text"], str):
            raise UsageError(f"the packet's {key} must be {{name, text}}")
    bp = packet["brand_profile"]
    if bp is not None and (not isinstance(bp, dict) or set(bp) != {"slug", "profile"}):
        raise UsageError("the packet's brand_profile must be {slug, profile} or null")
    return packet


def check(packet: dict) -> dict:
    deliverable = packet["deliverable"]["text"]
    profile_text = json.dumps(packet["brand_profile"]["profile"], ensure_ascii=False) if packet["brand_profile"] else ""
    known = stated_values(packet["brief"]["text"], profile_text)
    findings = []
    for n, line in enumerate(deliverable.splitlines(), 1):
        declared = bool(DECLARED.search(line))
        cited = bool(CITED.search(line))
        for m in MONEY.finditer(line):
            num, unit = (m.group("a"), m.group("au")) if m.group("a") else (m.group("b"), m.group("bu"))
            value = _value(num, unit)
            if declared or any(_close(value, k) for k in known):
                continue
            findings.append({"id": f"F{len(findings) + 1}", "kind": "unstated_figure", "line": n,
                             "quote": m.group(0).strip(), "context": line.strip()[:240],
                             "why": "a money figure the brief and the brand profile never state: say where it "
                                    "comes from, or mark it as an assumption for the client to confirm"})
        if BENCHMARK_TERMS.search(line) and not cited and not declared:
            for m in RATE.finditer(line):
                value = _value(m.group("n"), "%")
                if any(_close(value, k) for k in known):
                    continue
                findings.append({"id": f"F{len(findings) + 1}", "kind": "uncited_benchmark", "line": n,
                                 "quote": m.group(0).strip(), "context": line.strip()[:240],
                                 "why": "a benchmark rate with no source on its line and none in the brief or "
                                        "profile: cite the study or platform page and its date, or cut it"})
    blocked = bool(findings)
    return {"action": "check", "verdict": "blocked" if blocked else "clear", "findings": findings,
            "counts": {"unstated_figure": sum(f["kind"] == "unstated_figure" for f in findings),
                       "uncited_benchmark": sum(f["kind"] == "uncited_benchmark" for f in findings)},
            "scope": ("The deterministic pass reads only the packet. It finds money figures and benchmark rates; "
                      "the reviewer (--action prompt) reads for the assumptions, contradictions and questions "
                      "a script can't see.")}


PROMPT = """GOLDFISH REVIEW. Zero-context review of a client deliverable.

Read ONE file, with the Read tool: {packet}
Open no other file and run no command. Use nothing you know about this work from anywhere else: not this conversation, not memory, not the brand's folder. If something is not in that file, it does not exist for this review.

The file is JSON with exactly three keys: "deliverable" (the document the client will read), "brief" (what the client asked for) and "brand_profile" (the brand's stated facts, or null). Read the deliverable as the client would, cold, and return only this JSON:

{{
  "assumptions": [{{"quote": "<exact words from the deliverable>", "why": "<what it depends on that the brief or profile does not state: a budget, timeline, team, audience size, tool, approval>"}}],
  "unsourced_numbers": [{{"quote": "<exact words>", "why": "<a figure presented as fact with no source in the file>"}}],
  "contradictions": [{{"quote": "<exact words>", "conflicts_with": "<brief or brand_profile, quoted>"}}],
  "first_questions": ["<the first questions this client would ask on reading it, at most five>"],
  "verdict": "ready" or "needs_answers"
}}

Quote exactly; do not paraphrase. An empty list is a valid answer. "ready" only when every list but first_questions is empty."""

DEGRADED = ("Ignore everything earlier in this conversation for this one task, including what you know about this "
            "deliverable and this brand.\n\n")


def prompt(packet_path: Path, subagents: bool) -> dict:
    load_packet(packet_path)  # a prompt is only ever written for a valid packet
    text = PROMPT.format(packet=str(packet_path))
    if subagents:
        return {"action": "prompt", "mode": "subagent", "agent": "quality-assurance", "prompt": text,
                "instructions": "Pass the prompt to the subagent unchanged. Add nothing: no summary, no notes, "
                                "no 'for context'. A subagent given anything but the packet is no longer a goldfish."}
    return {"action": "prompt", "mode": "same-session (weaker)", "prompt": DEGRADED + text,
            "instructions": "This host has no subagents, so run the prompt in a fresh turn. The model has seen the "
                            "work and may fill gaps from memory: report the result as a same-session review, weaker "
                            "evidence than a subagent's, and never as zero-context."}


def main(argv=None) -> None:
    _common.ensure_utf8_stdout()
    parser = argparse.ArgumentParser(prog="goldfish-review.py",
                                     description="A zero-context review of a client deliverable: pack, check, prompt.")
    parser.add_argument("--action", required=True, choices=["pack", "check", "prompt"])
    parser.add_argument("--deliverable", help="the document the client will read (pack)")
    parser.add_argument("--brief", help="the brief it answers (pack)")
    parser.add_argument("--brand", type=_common.path_component, help="brand slug; its profile.json goes in the packet (pack)")
    parser.add_argument("--out", help="where to write the packet (pack; default: the brand's reviews/goldfish folder)")
    parser.add_argument("--packet", help="a packet written by --action pack (check, prompt)")
    parser.add_argument("--no-subagents", action="store_true",
                        help="prompt: the host has no subagents; return the weaker same-session form")
    args = parser.parse_args(argv)
    try:
        if args.action == "pack":
            if not args.deliverable or not args.brief:
                parser.error("pack needs --deliverable and --brief")
            result = pack(Path(args.deliverable), Path(args.brief), args.brand, Path(args.out) if args.out else None)
        else:
            if not args.packet:
                parser.error(f"{args.action} needs --packet")
            path = Path(args.packet)
            if not path.is_file():
                raise FileNotFoundError(f"packet not found: {path}")
            if args.action == "check":
                result = check(load_packet(path))
                print(json.dumps(result, indent=2, ensure_ascii=False))
                sys.exit(EXIT_BLOCKED if result["verdict"] == "blocked" else 0)
            result = prompt(path, subagents=not args.no_subagents)
    except UsageError as exc:
        print(json.dumps({"error": str(exc)}, indent=2, ensure_ascii=False))
        sys.exit(2)
    except (FileNotFoundError, OSError, ValueError) as exc:
        _common.finish({"error": str(exc), "recovery": "Check the path and that the file is UTF-8 text."})
    _common.finish(result)


if __name__ == "__main__":
    main()
