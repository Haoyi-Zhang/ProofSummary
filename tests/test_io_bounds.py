"""Verify bounded reads before JSON parsing; no large input allocation is needed."""
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import checker
import interval_checker
import model

class BoundedReadTests(unittest.TestCase):
    def exercise(self, function):
        manager = MagicMock()
        stream = manager.__enter__.return_value
        stream.read.return_value = b"{}"
        with patch("pathlib.Path.open", return_value=manager):
            self.assertEqual(function("unused.json"), {})
        stream.read.assert_called_once_with(8 * 1024 * 1024 + 1)
    def test_dense_decoder_bounds_read(self):
        self.exercise(checker.decode)
    def test_interval_decoder_bounds_read(self):
        self.exercise(interval_checker.decode)
    def test_producer_loader_bounds_read(self):
        self.exercise(model.load)

if __name__ == "__main__":
    unittest.main()
