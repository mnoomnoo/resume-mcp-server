from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from resume_mcp_server.extractor import extract_text

_MD_CONTENT = """\
# Jane Doe

jane@example.com | 503-555-1234

## Summary

Experienced software engineer.

## Skills

Python, Go, Rust
"""

_TXT_CONTENT = "Jane Doe\njane@example.com\n503-555-1234\n\nSkills\nPython, Go"


class TestExtractMarkdown(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self._tmpdir.name) / "resume.md"
        self.path.write_text(_MD_CONTENT, encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_returns_string(self):
        result = extract_text(self.path)
        self.assertIsInstance(result, str)

    def test_not_empty(self):
        result = extract_text(self.path)
        self.assertGreater(len(result), 0)

    def test_preserves_content(self):
        result = extract_text(self.path)
        self.assertIn("Jane Doe", result)
        self.assertIn("Python", result)

    def test_preserves_markdown_headers(self):
        result = extract_text(self.path)
        self.assertIn("##", result)


class TestExtractTxt(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self._tmpdir.name) / "resume.txt"
        self.path.write_text(_TXT_CONTENT, encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_returns_string(self):
        result = extract_text(self.path)
        self.assertIsInstance(result, str)

    def test_preserves_content(self):
        result = extract_text(self.path)
        self.assertIn("Jane Doe", result)
        self.assertIn("Python", result)


class TestExtractUnsupportedExtension(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self._tmpdir.name) / "data.csv"
        self.path.write_text("col1,col2\nval1,val2")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_unsupported_returns_empty_string(self):
        result = extract_text(self.path)
        self.assertEqual(result, "")


class TestExtractUnicodeContent(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self._tmpdir.name) / "resume.txt"
        self.path.write_text("Résumé: María García\nSkills: Python", encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_unicode_roundtrip(self):
        result = extract_text(self.path)
        self.assertIn("María", result)
        self.assertIn("García", result)


class TestExtractEmptyFile(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.md_path = Path(self._tmpdir.name) / "empty.md"
        self.md_path.write_text("")
        self.txt_path = Path(self._tmpdir.name) / "empty.txt"
        self.txt_path.write_text("")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_empty_md_returns_empty_string(self):
        self.assertEqual(extract_text(self.md_path), "")

    def test_empty_txt_returns_empty_string(self):
        self.assertEqual(extract_text(self.txt_path), "")


if __name__ == "__main__":
    unittest.main()
