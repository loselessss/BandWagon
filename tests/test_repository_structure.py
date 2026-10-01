"""Keep documentation links and package-local imports valid after cleanup."""
import ast
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]


class RepositoryStructureTests(unittest.TestCase):
    def test_local_document_links_exist(self):
        documents = list(ROOT.glob("*.md")) + list((ROOT / "docs").rglob("*.md"))
        # Local backups are user files, not repository documentation.
        documents = [doc for doc in documents if doc.name != "AGENTS.local.backup.md"]
        for document in documents:
            for target in re.findall(r"\[[^\]]*\]\(([^\s)]+)\)",
                                     document.read_text(encoding="utf-8")):
                url = urlsplit(target)
                if url.scheme or url.netloc or not url.path:
                    continue
                with self.subTest(document=document.name, target=target):
                    self.assertTrue((document.parent / unquote(url.path)).exists())

    def test_package_relative_imports_exist(self):
        for source in (ROOT / "bandwagon").glob("*.py"):
            tree = ast.parse(source.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or node.level != 1 or not node.module:
                    continue
                module = source.parent.joinpath(*node.module.split("."))
                with self.subTest(source=source.name, module=node.module):
                    self.assertTrue(module.with_suffix(".py").is_file()
                                    or (module / "__init__.py").is_file())


if __name__ == "__main__":
    unittest.main()
