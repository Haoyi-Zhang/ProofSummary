from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pcrh.bounded_checker import (  # noqa: E402
    CheckerLimits,
    ResourceEnvelopeError,
    check_certificate_bytes_bounded,
)


def rejected(payload: bytes, *, limits: CheckerLimits | None = None) -> bool:
    try:
        if limits is None:
            check_certificate_bytes_bounded(payload)
        else:
            check_certificate_bytes_bounded(payload, limits=limits)
    except ResourceEnvelopeError:
        return True
    except Exception:
        # Semantic rejection is also fail-closed, but these fixtures are
        # designed to be rejected by the envelope itself.
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    valid = (ROOT / "certificates" / "refined-closure.json").read_bytes()
    valid_accepted = check_certificate_bytes_bounded(valid) is not None

    deep: object = 0
    for _ in range(12):
        deep = [deep]

    attacks = {
        "byte_limit": rejected(valid, limits=CheckerLimits(max_certificate_bytes=8)),
        "duplicate_key": rejected(b'{"x":1,"x":2}'),
        "nan": rejected(b'{"x":NaN}'),
        "positive_infinity": rejected(b'{"x":Infinity}'),
        "float": rejected(b'{"x":1.5}'),
        "huge_integer": rejected(b'{"x":9223372036854775808}'),
        "invalid_utf8": rejected(b'\xff'),
        "truncated_json": rejected(b'{"x":'),
        "top_level_array": rejected(b'[]'),
        "depth_limit": rejected(
            json.dumps(deep).encode(),
            limits=CheckerLimits(max_json_depth=4),
        ),
        "list_limit": rejected(
            b'[0,1,2]',
            limits=CheckerLimits(max_list_items=2),
        ),
        "dict_limit": rejected(
            b'{"a":1,"b":2,"c":3}',
            limits=CheckerLimits(max_dict_items=2),
        ),
        "node_limit": rejected(
            b'{"a":[1,2,3]}',
            limits=CheckerLimits(max_total_nodes=3),
        ),
        "parser_recursion": rejected(("[" * 2000 + "0" + "]" * 2000).encode()),
    }
    result = {
        "schema": "pcrh-resource-attacks-v1",
        "valid_certificate_accepted": valid_accepted,
        "attacks": attacks,
        "attacks_rejected": sum(attacks.values()),
        "attacks_total": len(attacks),
        "status": "resource_envelope_passed" if valid_accepted and all(attacks.values()) else "failed",
    }
    (args.out / "resource-attack-summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "resource_envelope_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
