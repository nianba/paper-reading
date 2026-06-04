#!/usr/bin/env python3
"""Check local readiness for the paper-reading workflow."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import urllib.request
from pathlib import Path


TOOLS = ("pdfinfo", "pdftotext", "pdftoppm")


def check_tool(name: str) -> dict:
    path = shutil.which(name)
    return {"available": path is not None, "path": path}


def check_vault(vault: str | None) -> dict:
    if not vault:
        return {"required": False, "exists": False, "writable": False, "path": None}

    path = Path(vault).expanduser()
    exists = path.exists()
    writable = False
    if exists and path.is_dir():
        try:
            with tempfile.NamedTemporaryFile(dir=path, prefix=".paper-reading-", delete=True):
                writable = True
        except OSError:
            writable = False
    return {
        "required": True,
        "exists": exists,
        "writable": writable,
        "path": str(path),
    }


def check_network(url: str, timeout: float) -> dict:
    try:
        request = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {"checked": True, "ok": 200 <= response.status < 500, "status": response.status, "url": url}
    except Exception as exc:  # network diagnostics should not crash local workflows
        return {"checked": True, "ok": False, "error": str(exc), "url": url}


def build_report(args: argparse.Namespace) -> dict:
    tools = {tool: check_tool(tool) for tool in TOOLS}
    vault = check_vault(args.vault)
    network = (
        check_network(args.network_url, args.timeout)
        if args.check_network or args.require_network
        else {"checked": False, "ok": None, "url": args.network_url}
    )

    vault_ok = True if not vault["required"] else bool(vault["exists"] and vault["writable"])
    local_ok = vault_ok
    if args.require_poppler:
        local_ok = local_ok and all(item["available"] for item in tools.values())

    ok = bool(local_ok and (network["ok"] if args.require_network else True))
    return {
        "ok": ok,
        "local_ok": bool(local_ok),
        "network_ok": network["ok"],
        "network_required": bool(args.require_network),
        "tools": tools,
        "vault": vault,
        "network": network,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", help="Path to a paper-vault root to check.")
    parser.add_argument(
        "--check-network",
        action="store_true",
        help="Check optional network availability without making it part of local readiness.",
    )
    parser.add_argument(
        "--require-network",
        action="store_true",
        help="Treat network failure as an overall readiness failure.",
    )
    parser.add_argument("--network-url", default="https://arxiv.org", help="URL used for optional network check.")
    parser.add_argument("--timeout", type=float, default=5.0, help="Network timeout in seconds.")
    parser.add_argument(
        "--require-poppler",
        action="store_true",
        help="Treat missing pdfinfo/pdftotext/pdftoppm as local failure instead of diagnostics only.",
    )
    report = build_report(parser.parse_args())
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
