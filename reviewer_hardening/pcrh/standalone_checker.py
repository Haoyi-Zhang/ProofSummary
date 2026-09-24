#!/usr/bin/env python3
"""Standalone CLI boundary for the independent checker.

This file imports only the checker module, never generator/search code.  The
release gate additionally scans the import graph and executes it in a copy that
contains no core.py, so accidental producer coupling is a hard failure.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pcrh.checker import CertificateError, check_certificate_bytes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("certificate", type=Path)
    args = parser.parse_args()
    try:
        result = check_certificate_bytes(args.certificate.read_bytes())
    except (OSError, CertificateError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({
        "valid": result.valid,
        "optimal_budgets": result.exact_budgets,
        "safe_budgets": result.safe_budgets,
        "gap_budgets": result.gap_budgets,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
