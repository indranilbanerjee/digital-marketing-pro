#!/usr/bin/env python3
"""
crawler-log-report.py
=====================
What AI and search crawlers actually did on a site, from its own access logs.

robots.txt says what a crawler may fetch; the logs say what it fetched. This reads the
logs on this machine, finds the requests whose user agent names a crawler in
crawler_ranges.json (OAI-SearchBot, ChatGPT-User, GPTBot, ClaudeBot, PerplexityBot,
Googlebot, Google-Agent, bingbot, Applebot and the rest), and checks each against the
IP addresses that crawler's vendor publishes. A user-agent string can be sent by anyone,
so a request is "verified" only from a published address, "spoofed" when it names a
crawler from an address the vendor does not list, and "unverified" when the lists have
not been downloaded.

Privacy: access logs hold visitors' IP addresses, which are personal data under GDPR and
India's DPDP Act. The logs are read here and nothing from them leaves the machine. The
report never prints a full address: a spoofing source is shown as its /24 (IPv4) or /48
(IPv6) network, and query strings are cut from paths. The only network call is
--refresh-ranges, which downloads the vendors' public address lists (no log data, no key)
into the local data folder.

Usage:
    python crawler-log-report.py --refresh-ranges
    python crawler-log-report.py --log access.log [--log access.log.1.gz] [--top 10]
    python crawler-log-report.py --log cloudflare.jsonl --format jsonl

Log formats: the Apache/Nginx combined format (one request per line, the user agent the
last quoted field; a leading virtual-host field is allowed), and JSON lines with the
usual keys (Cloudflare Logpush ClientIP/ClientRequestUserAgent/ClientRequestURI/
EdgeResponseStatus/EdgeStartTimestamp, or ip/user_agent/path/status/time). A .gz file is
read as gzip. "-" (stdin) is refused: name a file.

Exit codes: 0 report written (or lists downloaded); 1 a log could not be read, or
--refresh-ranges on its own downloaded nothing; 2 bad arguments.
"""
from __future__ import annotations

import argparse
import gzip
import ipaddress
import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: E402

TABLE = Path(__file__).resolve().parent / "crawler_ranges.json"
USER_AGENT = "DMP-crawler-log-report/1.0 (+https://github.com/indranilbanerjee/digital-marketing-pro)"
MAX_LIST_BYTES = 4 * 1024 * 1024
TIMEOUT = 20

COMBINED = re.compile(
    r'^(?:(?P<vhost>\S+)\s+)?(?P<ip>[0-9A-Fa-f:.]+)\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)\]\s+'
    r'"(?P<method>[A-Z]+)\s+(?P<path>\S+)(?:\s+[^"]*)?"\s+(?P<status>\d{3})\s+\S+'
    r'(?:\s+"(?P<referer>[^"]*)"\s+"(?P<ua>[^"]*)")?')
JSON_KEYS = {
    "ip": ("ClientIP", "client_ip", "clientIp", "ip", "remote_addr", "c-ip"),
    "ua": ("ClientRequestUserAgent", "user_agent", "userAgent", "http_user_agent", "cs(User-Agent)"),
    "path": ("ClientRequestURI", "ClientRequestPath", "request_uri", "uri", "path", "cs-uri-stem"),
    "status": ("EdgeResponseStatus", "OriginResponseStatus", "status", "sc-status"),
    "time": ("EdgeStartTimestamp", "timestamp", "time", "date"),
}


class UsageError(Exception):
    pass


# ── The table and the downloaded lists ──────────────────────────────────────────

def load_table() -> dict:
    return _common.read_json(TABLE)


def cache_path() -> Path:
    return _common.workspace_root() / "cache" / "crawler-ranges.json"


def load_cache() -> dict:
    path = cache_path()
    if not path.exists():
        return {}
    try:
        data = _common.read_json(path)
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def parse_prefixes(doc) -> list:
    """The networks in a vendor list ({creationTime, prefixes: [{ipv4Prefix|ipv6Prefix}]}).
    Raises ValueError on anything else, so a broken download never becomes an empty list."""
    if not isinstance(doc, dict) or not isinstance(doc.get("prefixes"), list) or not doc["prefixes"]:
        raise ValueError("not a crawler address list (no 'prefixes')")
    nets = []
    for item in doc["prefixes"]:
        value = item.get("ipv4Prefix") or item.get("ipv6Prefix") if isinstance(item, dict) else None
        if not value:
            raise ValueError(f"a prefix entry has no ipv4Prefix or ipv6Prefix: {item!r}")
        nets.append(ipaddress.ip_network(value, strict=False))
    return nets


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _http_get(url: str, timeout: int) -> bytes:
    """The ONE place this script touches the network (tests patch it). No redirect is
    followed: each list is served from the vendor's own URL, and a redirect elsewhere is a
    failure, not a new source."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.build_opener(_NoRedirect).open(req, timeout=timeout) as resp:
        if urlparse(resp.geturl()).hostname != urlparse(url).hostname:
            raise ValueError(f"the response came from {urlparse(resp.geturl()).hostname}, not {urlparse(url).hostname}")
        body = resp.read(MAX_LIST_BYTES + 1)
    if len(body) > MAX_LIST_BYTES:
        raise ValueError(f"the list is larger than {MAX_LIST_BYTES // (1024 * 1024)} MB")
    return body


def refresh_ranges(table: dict) -> dict:
    """Download every vendor list into the local cache. A list that fails keeps its last good
    copy, if there is one, and is named in the result."""
    old = load_cache().get("lists", {})
    lists, fetched, failed = dict(old), [], []
    for name, entry in table["lists"].items():
        url = entry["url"]
        if urlparse(url).scheme != "https":
            failed.append({"list": name, "error": "only https:// lists are fetched"})
            continue
        try:
            doc = json.loads(_common.decode_text(_http_get(url, TIMEOUT), name))
            nets = parse_prefixes(doc)
        except urllib.error.HTTPError as exc:
            failed.append({"list": name, "error": f"HTTP {exc.code}" + (" (a redirect; not followed)" if 300 <= exc.code < 400 else "")})
            continue
        except (urllib.error.URLError, OSError, ValueError) as exc:
            failed.append({"list": name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        lists[name] = {"url": url, "vendor": entry["vendor"], "creationTime": doc.get("creationTime"),
                       "fetched_on": _common.now_iso(), "prefixes": [str(n) for n in nets]}
        fetched.append({"list": name, "prefixes": len(nets), "creationTime": doc.get("creationTime")})
    if fetched:
        _common.atomic_write_json(cache_path(), {"lists": lists, "updated": _common.now_iso()})
    result = {"action": "refresh-ranges", "cache": str(cache_path()), "fetched": fetched, "failed": failed,
              "note": "Only the vendors' public address lists were downloaded; nothing from your logs was sent."}
    if not fetched:
        result["error"] = "no list could be downloaded"
        result["recovery"] = ("Check the network or proxy, then run --refresh-ranges again. Reports still run, "
                              "with every crawler request marked unverified.")
    return result


def _age_days(stamp: str | None) -> int | None:
    if not stamp:
        return None
    try:
        when = datetime.fromisoformat(stamp.replace("Z", "+00:00")).date()
    except ValueError:
        return None
    return (date.today() - when).days


# ── Reading logs ────────────────────────────────────────────────────────────────

def _open_lines(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as fh:
        first = True
        for raw in fh:
            if first and raw.startswith(b"\xef\xbb\xbf"):
                raw = raw[3:]
            first = False
            yield raw.decode("utf-8", errors="replace").rstrip("\r\n")


def _pick(record: dict, field: str):
    for key in JSON_KEYS[field]:
        if record.get(key) not in (None, ""):
            return record[key]
    return None


def parse_line(line: str, fmt: str):
    """{ip, ua, path, status, time} or None when the line is not a request."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if fmt in ("jsonl", "auto") and line.startswith("{"):
        try:
            record = json.loads(line)
        except ValueError:
            return None
        if not isinstance(record, dict):
            return None
        ip, ua = _pick(record, "ip"), _pick(record, "ua")
        if not ip:
            return None
        status = _pick(record, "status")
        return {"ip": str(ip), "ua": str(ua or ""), "path": str(_pick(record, "path") or ""),
                "status": int(status) if str(status or "").isdigit() else None,
                "time": str(_pick(record, "time") or "") or None}
    if fmt == "jsonl":
        return None
    m = COMBINED.match(line)
    if not m:
        return None
    return {"ip": m.group("ip"), "ua": m.group("ua") or "", "path": m.group("path"),
            "status": int(m.group("status")), "time": m.group("time")}


def _clean_path(path: str) -> str:
    """The path without its query string or fragment, which can carry emails or tokens."""
    if "://" in path:
        path = urlparse(path).path or "/"
    return path.split("?", 1)[0].split("#", 1)[0] or "/"


def _network_of(ip) -> str:
    return str(ipaddress.ip_network(f"{ip}/{24 if ip.version == 4 else 48}", strict=False))


def _parse_time(stamp):
    if stamp in (None, ""):
        return None
    if isinstance(stamp, (int, float)) or str(stamp).isdigit():
        n = int(stamp)
        n = n / 1e9 if n > 1e15 else n / 1e3 if n > 1e12 else n  # ns, ms or s since the epoch
        return datetime.fromtimestamp(n, tz=timezone.utc)
    for fmt in ("%d/%b/%Y:%H:%M:%S %z",):
        try:
            return datetime.strptime(stamp, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None


# ── The report ──────────────────────────────────────────────────────────────────

def build_report(logs: list[Path], fmt: str, top: int, table: dict, cache: dict) -> dict:
    cached = cache.get("lists", {})
    networks = {}
    for name, entry in cached.items():
        try:
            networks[name] = [ipaddress.ip_network(p, strict=False) for p in entry.get("prefixes", [])]
        except ValueError:
            continue
    crawlers = table["crawlers"]
    stats = {c["token"]: {"token": c["token"], "vendor": c["vendor"], "role": c["role"], "requests": 0,
                          "verified": 0, "spoofed": 0, "unverified": 0, "robots_txt_fetches": 0,
                          "status": Counter(), "paths": Counter(), "spoof_nets": Counter(),
                          "first_seen": None, "last_seen": None} for c in crawlers}
    lowered = [(c["token"].lower(), c) for c in crawlers]
    verdicts: dict = {}
    lines_read = unparsed = 0
    for log in logs:
        for line in _open_lines(log):
            lines_read += 1
            row = parse_line(line, fmt)
            if row is None:
                if line.strip():
                    unparsed += 1
                continue
            ua = row["ua"].lower()
            match = next((c for token, c in lowered if token in ua), None)
            if match is None:
                continue
            try:
                ip = ipaddress.ip_address(row["ip"].strip("[]"))
            except ValueError:
                unparsed += 1
                continue
            key = (match["token"], ip)
            if key not in verdicts:
                # Verified from any downloaded list; spoofed only when every list the vendor
                # publishes for that crawler is here and none holds the address.
                lists = [networks[n] for n in match["lists"] if n in networks]
                if any(ip in net for nets in lists for net in nets):
                    verdicts[key] = "verified"
                elif lists and len(lists) == len(match["lists"]):
                    verdicts[key] = "spoofed"
                else:
                    verdicts[key] = "unverified"
            verdict = verdicts[key]
            s = stats[match["token"]]
            s["requests"] += 1
            s[verdict] += 1
            if verdict == "spoofed":
                s["spoof_nets"][_network_of(ip)] += 1
                continue
            path = _clean_path(row["path"])
            s["paths"][path] += 1
            if path == "/robots.txt":
                s["robots_txt_fetches"] += 1
            if row["status"] is not None:
                s["status"][f"{row['status'] // 100}xx"] += 1
            when = _parse_time(row["time"])
            if when is not None:
                iso = when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                s["first_seen"] = min(filter(None, (s["first_seen"], iso)))
                s["last_seen"] = max(filter(None, (s["last_seen"], iso)))

    max_age = int(table.get("max_age_days", 14))
    ages = [a for a in (_age_days(e.get("fetched_on")) for e in cached.values()) if a is not None]
    oldest = max(ages) if ages else None
    missing = sorted({n for c in crawlers for n in c["lists"] if n not in networks})
    out_rows = []
    for s in stats.values():
        if not s["requests"]:
            continue
        out_rows.append({
            "token": s["token"], "vendor": s["vendor"], "role": s["role"], "requests": s["requests"],
            "verified": s["verified"], "spoofed": s["spoofed"], "unverified": s["unverified"],
            "robots_txt_fetches": s["robots_txt_fetches"], "status": dict(sorted(s["status"].items())),
            "first_seen": s["first_seen"], "last_seen": s["last_seen"],
            "top_paths": [{"path": p, "requests": n} for p, n in s["paths"].most_common(top)],
            "spoofing_networks": [{"network": net, "requests": n} for net, n in s["spoof_nets"].most_common(5)],
        })
    out_rows.sort(key=lambda r: -r["requests"])
    totals = {k: sum(r[k] for r in out_rows) for k in ("requests", "verified", "spoofed", "unverified")}
    return {
        "action": "report",
        "logs": [str(p) for p in logs],
        "lines_read": lines_read,
        "lines_unparsed": unparsed,
        "crawler_requests": totals,
        "ranges": {"cache": str(cache_path()), "oldest_list_days": oldest, "stale": oldest is not None and oldest > max_age,
                   "max_age_days": max_age, "lists_missing": missing},
        "crawlers": out_rows,
        "not_seen": [c["token"] for c in crawlers if not stats[c["token"]]["requests"]],
        "findings": findings(out_rows, [c["token"] for c in crawlers if not stats[c["token"]]["requests"]],
                             missing, oldest, max_age),
        "privacy": ("Read on this machine only; nothing from the logs was sent anywhere. Full IP addresses are "
                    "never printed: spoofing sources appear as /24 (IPv4) or /48 (IPv6) networks, and query "
                    "strings are cut from paths."),
    }


def findings(rows, not_seen, missing, oldest, max_age) -> list[str]:
    out = []
    if missing:
        out.append(f"{len(missing)} vendor address list(s) are not downloaded, so requests from those crawlers are "
                   f"unverified, not genuine: run --refresh-ranges ({', '.join(missing[:4])}{'…' if len(missing) > 4 else ''}).")
    if oldest is not None and oldest > max_age:
        out.append(f"The address lists are {oldest} days old (more than {max_age}); vendors add addresses often, so "
                   f"a genuine crawler can show as spoofed. Run --refresh-ranges.")
    for r in rows:
        if r["spoofed"]:
            out.append(f"{r['spoofed']} request(s) named {r['token']} from addresses {r['vendor']} does not publish. "
                       f"robots.txt will not stop them; block those networks at the firewall or CDN if they cost you.")
        errors = sum(n for k, n in r["status"].items() if k in ("4xx", "5xx"))
        served = sum(r["status"].values())
        if served and errors / served >= 0.2:
            out.append(f"{r['token']} got an error on {errors} of {served} requests (4xx/5xx): check those paths "
                       f"before reading its visits as interest.")
    for token in not_seen:
        if token in ("OAI-SearchBot", "Claude-SearchBot", "PerplexityBot"):
            out.append(f"No request from {token} in these logs. If robots.txt allows it, the site may not yet be in "
                       f"that assistant's search index; check the robots rules with agent-readiness-audit.")
    return out


def main(argv=None) -> None:
    _common.ensure_utf8_stdout()
    parser = argparse.ArgumentParser(
        prog="crawler-log-report.py",
        description="What AI and search crawlers did on a site, from its own access logs, with each request "
                    "checked against the vendor's published addresses. Logs never leave this machine.")
    parser.add_argument("--log", action="append", default=[], metavar="FILE",
                        help="an access log (combined format or JSON lines; .gz allowed). Repeat for more files.")
    parser.add_argument("--format", choices=["auto", "combined", "jsonl"], default="auto",
                        help="log format (default: auto, per line)")
    parser.add_argument("--top", type=int, default=10, help="paths to list per crawler (default 10)")
    parser.add_argument("--refresh-ranges", action="store_true",
                        help="download the vendors' crawler address lists into the local data folder (the only "
                             "network call; sends nothing from the logs)")
    args = parser.parse_args(argv)
    if not args.log and not args.refresh_ranges:
        parser.error("name at least one --log FILE, or pass --refresh-ranges")
    if any(p == "-" for p in args.log):
        parser.error("stdin is not read: name the log file")
    if args.top < 1 or args.top > 100:
        parser.error("--top takes 1 to 100")
    table = load_table()
    result = {}
    if args.refresh_ranges:
        result = refresh_ranges(table)
        if not args.log:
            _common.finish(result)
    logs = [Path(p) for p in args.log]
    unreadable = [str(p) for p in logs if not p.is_file()]
    if unreadable:
        _common.finish({"error": f"no such log file: {', '.join(unreadable)}",
                        "recovery": "Pass the path of a file your web server or CDN wrote."})
    try:
        report = build_report(logs, args.format, args.top, table, load_cache())
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        _common.finish({"error": f"could not read the logs: {type(exc).__name__}: {exc}",
                        "recovery": "Check the file is a plain-text or gzip access log."})
    if result:
        report["refresh"] = {k: result[k] for k in ("fetched", "failed")}
    _common.finish(report)


if __name__ == "__main__":
    main()
