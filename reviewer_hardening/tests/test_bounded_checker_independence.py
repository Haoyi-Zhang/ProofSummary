from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path
import unittest


class BoundedCheckerIndependenceTests(unittest.TestCase):
    def test_consumer_import_does_not_initialize_producer(self) -> None:
        root = Path(__file__).resolve().parents[1]
        code = "import sys; import pcrh.bounded_checker; import pcrh.refinement_checker; assert 'pcrh.core' not in sys.modules"
        subprocess.run([sys.executable, "-B", "-c", code], cwd=root,
                       env={**os.environ, "PYTHONPATH": str(root), "PYTHONDONTWRITEBYTECODE": "1"},
                       timeout=10, check=True, capture_output=True, text=True)

    def test_no_producer_import(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for name in ("bounded_checker.py", "bounded_checker_cli.py", "checker.py", "refinement_checker.py"):
            tree = ast.parse((root / "pcrh" / name).read_text())
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imported.add(node.module or "")
            forbidden = {item for item in imported if item.endswith("core") or "producer" in item or "search" in item}
            self.assertEqual(forbidden, set(), (name, forbidden))


if __name__ == "__main__":
    unittest.main()
