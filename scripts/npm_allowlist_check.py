#!/usr/bin/env python3
"""
npm_allowlist_check.py — confirm every allowlisted npx package still is what we think it is.

DMP offers a runnable `npx -y <pkg>@<version>` only for the vendor-published
packages in _connector_registry.VERIFIED_NPX_PACKAGES. This script asks the
public npm registry (read-only GET, no key) whether each one:

  * exists and has not been unpublished,
  * still has the pinned version,
  * is maintained by the vendor's npm account we listed, and
  * points at the vendor repository we listed.

The weekly dated-checks workflow runs it and opens an issue when it fails, so
a removed package, a transferred name or a vanished version is noticed even on
a quiet repo.

Usage:
    python npm_allowlist_check.py           # human-readable report
    python npm_allowlist_check.py --json    # machine-readable

Exit codes: 0 all entries check out · 1 an entry failed or the registry could
not be reached · 2 bad argument.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

for _stream in (sys.stdout, sys.stderr):  # UTF-8 output, even where a Windows pipe defaults to cp1252
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _connector_registry import VERIFIED_NPX_PACKAGES  # noqa: E402

REGISTRY = "https://registry.npmjs.org/"
USER_AGENT = "DigitalMarketingPro-npm-allowlist-check (+https://github.com/indranilbanerjee/digital-marketing-pro)"


def fetch(package: str) -> tuple[int, dict | None]:
    """(HTTP status, parsed document or None) for one package from the npm registry."""
    url = REGISTRY + package.replace("/", "%2f")
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as exc:
        return exc.code, None


def _repo(url: str | None) -> str:
    url = (url or "").strip().lower()
    for prefix in ("git+", "git://"):
        if url.startswith(prefix):
            url = url[len(prefix):]
    url = url.replace("ssh://git@", "https://").replace("git@github.com:", "https://github.com/")
    return url[:-4] if url.endswith(".git") else url.rstrip("/")


def check_entry(package: str, entry: dict, fetcher=fetch) -> list[str]:
    """Problems with one allowlist entry; [] when it checks out."""
    try:
        status, doc = fetcher(package)
    except OSError as exc:
        return [f"{package}: registry unreachable ({type(exc).__name__}: {exc})"]
    if status == 404 or doc is None:
        return [f"{package}: not on npm (HTTP {status}); anyone could register this name"]
    problems = []
    if doc.get("time", {}).get("unpublished"):
        problems.append(f"{package}: unpublished; anyone could register this name")
    version = entry["version"]
    meta = doc.get("versions", {}).get(version)
    if meta is None:
        problems.append(f"{package}: pinned version {version} is gone")
    maintainers = {m.get("name") for m in doc.get("maintainers", [])}
    if entry["npm_maintainer"] not in maintainers:
        problems.append(f"{package}: maintainers are {sorted(maintainers)}, "
                        f"expected {entry['npm_maintainer']}")
    repo = (meta or {}).get("repository") or doc.get("repository")
    repo_url = repo.get("url") if isinstance(repo, dict) else repo
    if _repo(repo_url) != _repo(entry["repository"]):
        problems.append(f"{package}: repository is {repo_url!r}, expected {entry['repository']}")
    return problems


def check_all(table: dict | None = None, fetcher=fetch) -> list[str]:
    table = VERIFIED_NPX_PACKAGES if table is None else table
    problems = []
    for package, entry in table.items():
        problems.extend(check_entry(package, entry, fetcher))
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="print a JSON report")
    args = parser.parse_args(argv)
    problems = check_all()
    if args.json:
        print(json.dumps({"checked": sorted(VERIFIED_NPX_PACKAGES), "problems": problems}, indent=2))
    elif problems:
        print("npm allowlist check FAILED:")
        for p in problems:
            print(f"  - {p}")
    else:
        print(f"npm allowlist check passed: {len(VERIFIED_NPX_PACKAGES)} vendor packages "
              f"exist at their pinned versions with the expected maintainers.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
