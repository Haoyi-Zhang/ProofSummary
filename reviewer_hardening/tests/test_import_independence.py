from __future__ import annotations

import ast
import unittest
from pathlib import Path


class IndependenceTests(unittest.TestCase):
    def test_checker_does_not_import_generator(self) -> None:
        path = Path(__file__).resolve().parents[1] / "pcrh" / "checker.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        self.assertFalse(any(name.endswith("core") or "generator" in name or "search" in name for name in imports), imports)


if __name__ == "__main__":
    unittest.main()
