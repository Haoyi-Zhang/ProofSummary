"""Summary ordering is immaterial; frozen consumer bytes are not."""
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

if sys.platform == 'win32':
    with patch.dict(sys.modules, {'resource': Mock()}):
        reproduce = importlib.import_module('reproduce')
else:
    import reproduce


class SummaryComparisonTests(unittest.TestCase):
    def compare(self, old_summary, new_summary, old_bytes=b'{}', new_bytes=b'{}'):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old, new = root / 'old', root / 'new'
            old.mkdir()
            new.mkdir()
            for target, summary, frozen in [(old, old_summary, old_bytes),
                                             (new, new_summary, new_bytes)]:
                (target / 'summary.json').write_bytes(summary)
                (target / 'query.json').write_bytes(frozen)
            return reproduce.compare_tree(old, new)

    def test_report_key_order_and_whitespace(self):
        self.assertEqual(2, self.compare(b'{"accepted":12,"unknown":3}',
                                        b'{ "unknown": 3, "accepted": 12 }'))

    def test_changed_count_rejects(self):
        with self.assertRaises(ValueError):
            self.compare(b'{"accepted":12}', b'{"accepted":11}')

    def test_boolean_is_not_integer(self):
        with self.assertRaises(ValueError):
            self.compare(b'{"accepted":1}', b'{"accepted":true}')

    def test_duplicate_summary_key_rejects(self):
        with self.assertRaises(ValueError):
            self.compare(b'{"accepted":12}', b'{"accepted":12,"accepted":12}')

    def test_frozen_query_bytes_still_rejects(self):
        with self.assertRaises(ValueError):
            self.compare(b'{"accepted":12}', b'{"accepted":12}', b'{}', b'{ }')


if __name__ == '__main__':
    unittest.main()
