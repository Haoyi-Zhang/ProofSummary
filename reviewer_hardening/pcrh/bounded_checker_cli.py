"""Command-line entry point for the resource-bounded checker."""
from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
import sys
from typing import Any

from .bounded_checker import check_certificate_bytes_bounded
from .checker import CertificateError


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a PCRH certificate")
    parser.add_argument("certificate", type=Path)
    parser.add_argument("--expected-model-sha256")
    args = parser.parse_args(argv)
    try:
        result = check_certificate_bytes_bounded(
            args.certificate.read_bytes(),
            expected_model_sha256=args.expected_model_sha256,
        )
    except (CertificateError, OSError) as exc:
        print(json.dumps({"accepted": False, "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({"accepted": True, "result": _jsonable(result)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
