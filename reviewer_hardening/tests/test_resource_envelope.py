from __future__ import annotations

import json
from pathlib import Path
import unittest

from pcrh.bounded_checker import (
    CheckerLimits,
    ResourceEnvelopeError,
    check_certificate_bytes_bounded,
)


HERE = Path(__file__).resolve().parents[1]
VALID_CERT = HERE / "certificates" / "refined-closure.json"


class ResourceEnvelopeTests(unittest.TestCase):
    def test_valid_committed_certificate(self) -> None:
        result = check_certificate_bytes_bounded(VALID_CERT.read_bytes())
        self.assertIsNotNone(result)

    def test_byte_limit(self) -> None:
        limits = CheckerLimits(max_certificate_bytes=7)
        with self.assertRaises(ResourceEnvelopeError):
            check_certificate_bytes_bounded(b'{"x": 1}', limits=limits)

    def test_duplicate_key(self) -> None:
        with self.assertRaises(ResourceEnvelopeError):
            check_certificate_bytes_bounded(b'{"x": 1, "x": 2}')

    def test_nonfinite_constant(self) -> None:
        with self.assertRaises(ResourceEnvelopeError):
            check_certificate_bytes_bounded(b'{"x": NaN}')

    def test_float_is_rejected(self) -> None:
        with self.assertRaises(ResourceEnvelopeError):
            check_certificate_bytes_bounded(b'{"x": 1.25}')

    def test_integer_limit_precedes_semantics(self) -> None:
        with self.assertRaises(ResourceEnvelopeError):
            check_certificate_bytes_bounded(b'{"x": 9223372036854775808}')

    def test_depth_limit(self) -> None:
        value = 0
        for _ in range(10):
            value = [value]
        payload = json.dumps(value).encode()
        limits = CheckerLimits(max_json_depth=4)
        with self.assertRaises(ResourceEnvelopeError):
            check_certificate_bytes_bounded(payload, limits=limits)

    def test_parser_recursion_is_fail_closed(self) -> None:
        payload = ("[" * 2000 + "0" + "]" * 2000).encode()
        with self.assertRaises(ResourceEnvelopeError):
            check_certificate_bytes_bounded(payload)

    def test_invalid_utf8(self) -> None:
        with self.assertRaises(ResourceEnvelopeError):
            check_certificate_bytes_bounded(b'\xff')


if __name__ == "__main__":
    unittest.main()
