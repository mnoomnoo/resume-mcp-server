from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from resume_mcp_server.collection import ResumeCollection, _infer_doc_type

# Absolute path to the sample_resumes directory shipped with the project
_SAMPLE_DIR = Path(__file__).parent.parent / "sample_resumes"

# Plain-text resume that the parser can fully structure (no markdown headers)
_PLAIN_RESUME = """\
Jane Doe
Portland, OR
jane@example.com
503-555-1234

Summary
Experienced software engineer with 5+ years building distributed systems.

Experience
Acme Corp | Software Engineer  March 2022 – Present
• Built a distributed system that handles large traffic volumes efficiently
• Reduced latency by 40% through targeted caching improvements

Globex | Junior Engineer  January 2020 – February 2022
• Developed RESTful APIs consumed by mobile and web clients daily
• Wrote comprehensive unit and integration tests using pytest framework

Skills
Languages: Python, Go, Rust
Tools: Docker, Kubernetes, PostgreSQL

Education
BS Computer Science, University of Oregon, 2019
"""

_PLAIN_RESUME_2 = """\
John Smith
Seattle, WA
john.smith@example.com
206-555-9876

Summary
Senior DevOps engineer with expertise in cloud infrastructure.

Experience
CloudCo | DevOps Engineer  January 2021 – Present
• Designed Kubernetes cluster serving 50M requests per day at peak load
• Automated deployment pipeline reducing release time from 2 hours to 10 minutes

Skills
Kubernetes, Terraform, AWS, Docker, Python, Bash

Education
BS Computer Engineering, University of Washington, 2018
"""


# ── doc-type inference ────────────────────────────────────────────────────────

class TestDocTypeInference(unittest.TestCase):
    def test_resume_filename(self):
        self.assertEqual(_infer_doc_type("jane_doe_resume.docx"), "resume")
        self.assertEqual(_infer_doc_type("resume_jane.pdf"), "resume")
        self.assertEqual(_infer_doc_type("My_Resume_2024.md"), "resume")

    def test_cover_letter_filename(self):
        self.assertEqual(_infer_doc_type("jane_cover_letter.docx"), "cover_letter")
        self.assertEqual(_infer_doc_type("jane_cl.pdf"), "cover_letter")
        self.assertEqual(_infer_doc_type("coverletter_acme.docx"), "cover_letter")

    def test_application_material_filename(self):
        self.assertEqual(_infer_doc_type("acme_interview_prep.md"), "application_material")
        self.assertEqual(_infer_doc_type("why_acme.docx"), "application_material")
        self.assertEqual(_infer_doc_type("application_questions_google.txt"), "application_material")

    def test_unknown_filename(self):
        self.assertEqual(_infer_doc_type("random_notes.txt"), "other")
        self.assertEqual(_infer_doc_type("portfolio.pdf"), "other")
        self.assertEqual(_infer_doc_type("references.docx"), "other")


class TestDocTypeInferenceEnvOverrides(unittest.TestCase):
    def test_custom_pattern_overrides_default(self):
        with patch.dict(os.environ, {"DOC_TYPE_PATTERN_RESUME": "lebenslauf"}):
            self.assertEqual(_infer_doc_type("lebenslauf_jane.docx"), "resume")
            self.assertEqual(_infer_doc_type("jane_resume.docx"), "other")

    def test_custom_cover_letter_pattern(self):
        with patch.dict(os.environ, {"DOC_TYPE_PATTERN_COVER_LETTER": "anschreiben"}):
            self.assertEqual(_infer_doc_type("jane_anschreiben.docx"), "cover_letter")

    def test_custom_application_material_pattern(self):
        with patch.dict(os.environ, {"DOC_TYPE_PATTERN_APPLICATION_MATERIAL": "bewerbung"}):
            self.assertEqual(_infer_doc_type("acme_bewerbung.txt"), "application_material")

    def test_unset_env_vars_use_default_behavior(self):
        self.assertEqual(_infer_doc_type("jane_doe_resume.docx"), "resume")
        self.assertEqual(_infer_doc_type("jane_cover_letter.docx"), "cover_letter")
        self.assertEqual(_infer_doc_type("why_acme.docx"), "application_material")
        self.assertEqual(_infer_doc_type("random_notes.txt"), "other")

    def test_invalid_regex_falls_back_to_default(self):
        with patch.dict(os.environ, {"DOC_TYPE_PATTERN_RESUME": "resume("}):
            self.assertEqual(_infer_doc_type("jane_resume.docx"), "resume")
            self.assertEqual(_infer_doc_type("random_notes.txt"), "other")


class TestCollectionLoadWithEnvOverride(unittest.TestCase):
    """Confirms DOC_TYPE_PATTERN_* env vars flow through ResumeCollection.load()."""

    def test_load_respects_application_material_override(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            (tmp / "acme_bewerbung.txt").write_text("Bewerbung fuer Acme Corp.")
            with patch.dict(os.environ, {"DOC_TYPE_PATTERN_APPLICATION_MATERIAL": "bewerbung"}):
                collection = ResumeCollection(tmp)
                collection.load()
            items = collection.list_all(doc_type="application_material")
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].filename, "acme_bewerbung.txt")


# ── collection loading with empty directory ───────────────────────────────────

class TestCollectionLoadEmptyDir(unittest.TestCase):
    """Collection loaded from an empty directory must report zero documents."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.collection = ResumeCollection(Path(cls._tmpdir.name))
        cls.count = cls.collection.load()

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def test_load_returns_zero(self):
        self.assertEqual(self.count, 0)

    def test_list_all_returns_empty(self):
        self.assertEqual(self.collection.list_all(), [])

    def test_list_all_with_doc_type_returns_empty(self):
        self.assertEqual(self.collection.list_all(doc_type="resume"), [])

    def test_search_returns_empty(self):
        self.assertEqual(self.collection.search("anything").items, [])

    def test_get_text_raises_key_error(self):
        with self.assertRaises(KeyError):
            self.collection.get_text("nonexistent.txt")


# ── collection loading with sample markdown files ─────────────────────────────

class TestCollectionLoadSampleDir(unittest.TestCase):
    """Tests against the real sample_resumes/ directory (markdown files)."""

    @classmethod
    def setUpClass(cls):
        cls.collection = ResumeCollection(_SAMPLE_DIR)
        cls.count = cls.collection.load()

    def test_loads_expected_file_count(self):
        self.assertGreaterEqual(self.count, 2)

    def test_list_all_returns_metadata(self):
        items = self.collection.list_all()
        self.assertGreaterEqual(len(items), 2)
        filenames = {m.filename for m in items}
        self.assertIn("jane_doe_resume.md", filenames)
        self.assertIn("john_smith_resume.md", filenames)

    def test_doc_type_inferred_as_resume(self):
        items = self.collection.list_all()
        for m in items:
            self.assertEqual(m.doc_type, "resume", f"Unexpected doc_type for {m.filename}")

    def test_list_all_doc_type_filter(self):
        # All sample files are resumes; filtering by cover_letter returns empty
        self.assertEqual(self.collection.list_all(doc_type="cover_letter"), [])
        self.assertGreaterEqual(len(self.collection.list_all(doc_type="resume")), 2)

    def test_get_text_returns_content(self):
        items = self.collection.list_all()
        path = items[0].path
        text = self.collection.get_text(path)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)

    def test_get_text_unknown_path_raises(self):
        with self.assertRaises(KeyError):
            self.collection.get_text("nonexistent/file.md")

    def test_full_text_search_returns_result(self):
        results = self.collection.search("Engineer").items
        self.assertGreater(len(results), 0)

    def test_full_text_search_no_match_returns_empty(self):
        results = self.collection.search("xyzzy_no_such_term_12345").items
        self.assertEqual(results, [])

    def test_search_result_has_snippet(self):
        results = self.collection.search("Engineer").items
        for r in results:
            self.assertIsInstance(r["snippet"], str)
            self.assertGreater(len(r["snippet"]), 0)

    def test_search_result_has_match_count(self):
        results = self.collection.search("Engineer").items
        for r in results:
            self.assertGreater(r["match_count"], 0)

    def test_reload_is_idempotent(self):
        count_first = self.collection.load()
        count_second = self.collection.load()
        self.assertEqual(count_first, count_second)
        self.assertEqual(len(self.collection.list_all()), count_first)

    def test_repo_populated_with_resumes(self):
        # Markdown headers cause partial parsing; at minimum emails are extracted
        result = self.collection._repo.list_resume_summaries()
        self.assertGreaterEqual(result.total_count, 2)
        emails = {s["email"] for s in result.items}
        self.assertIn("jane.doe@email.com", emails)
        self.assertIn("john.smith@email.com", emails)

    def test_markdown_files_parse_work_experience(self):
        result = self.collection._repo.list_work_experiences()
        self.assertGreater(result.total_count, 0)
        companies = {w["company_name"] for w in result.items}
        self.assertIn("Acme Corp", companies)

    def test_markdown_files_parse_skills(self):
        result = self.collection._repo.list_badge_skills()
        titles = {s["title"] for s in result.items}
        self.assertIn("Python", titles)

    def test_markdown_files_parse_last_name(self):
        result = self.collection._repo.list_resume_summaries()
        last_names = {s["last_name"] for s in result.items}
        self.assertIn("Doe", last_names)


# ── collection loading with plain-text files (fully parseable) ────────────────

class TestCollectionLoadPlainText(unittest.TestCase):
    """Tests against a temp dir with plain-text resumes the parser can fully handle."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmpdir.name)
        (tmp / "jane_resume.txt").write_text(_PLAIN_RESUME)
        (tmp / "john_resume.txt").write_text(_PLAIN_RESUME_2)
        (tmp / "cover_letter.txt").write_text("A cover letter for Acme Corp.")
        cls.collection = ResumeCollection(tmp)
        cls.collection.load()

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def test_list_all_returns_all_files(self):
        self.assertEqual(len(self.collection.list_all()), 3)

    def test_list_resumes_only(self):
        resumes = self.collection.list_all(doc_type="resume")
        self.assertEqual(len(resumes), 2)

    def test_list_cover_letter_doc_type(self):
        cover_letters = self.collection.list_all(doc_type="cover_letter")
        self.assertEqual(len(cover_letters), 1)
        self.assertEqual(cover_letters[0].filename, "cover_letter.txt")

    def test_repo_has_structured_data(self):
        result = self.collection._repo.list_resume_summaries()
        self.assertEqual(result.total_count, 2)
        names = {s["first_name"] for s in result.items}
        self.assertIn("Jane", names)
        self.assertIn("John", names)

    def test_repo_work_experiences_parsed(self):
        result = self.collection._repo.list_work_experiences()
        self.assertGreater(result.total_count, 0)
        companies = {w["company_name"] for w in result.items}
        self.assertIn("Acme Corp", companies)

    def test_repo_skills_parsed(self):
        result = self.collection._repo.list_badge_skills()
        titles = {s["title"] for s in result.items}
        self.assertIn("Python", titles)

    def test_search_text_across_cover_letter(self):
        results = self.collection.search("Acme Corp").items
        paths = {r["path"] for r in results}
        # cover_letter.txt also mentions Acme Corp
        self.assertTrue(any("cover_letter" in p for p in paths))

    def test_search_filtered_to_doc_type(self):
        # "Acme Corp" appears in both a resume and the cover letter
        all_results = self.collection.search("Acme Corp").items
        resume_only = self.collection.search("Acme Corp", doc_type="resume").items
        self.assertLessEqual(len(resume_only), len(all_results))
        self.assertTrue(all(r["doc_type"] == "resume" for r in resume_only))

    def test_non_resume_files_not_parsed_into_repo(self):
        # cover_letter.txt should appear in the index but NOT be added to repo
        count = self.collection._repo.list_resumes().total_count
        self.assertEqual(count, 2)


# ── resume de-duplication across file-format variants ─────────────────────────

class TestCollectionResumeDedup(unittest.TestCase):
    """Two files that resolve to the same person should collapse to one record."""

    def test_identical_content_dedups_by_email(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            (tmp / "jane_resume_a.txt").write_text(_PLAIN_RESUME)
            (tmp / "jane_resume_b.txt").write_text(_PLAIN_RESUME)
            collection = ResumeCollection(tmp)
            collection.load()
            result = collection._repo.list_resume_summaries()
            self.assertEqual(result.total_count, 1)
            self.assertEqual(result.items[0]["email"], "jane@example.com")

    def test_richer_copy_is_kept_over_sparser_copy(self):
        sparse = "Jane Doe\njane@example.com\n\nSkills\nPython\n"
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            # Alphabetically first so it's parsed before the richer copy,
            # proving the richer one wins rather than "first file loaded".
            (tmp / "a_sparse_resume.txt").write_text(sparse)
            (tmp / "b_full_resume.txt").write_text(_PLAIN_RESUME)
            collection = ResumeCollection(tmp)
            collection.load()
            result = collection._repo.list_resume_summaries()
            self.assertEqual(result.total_count, 1)
            work_experiences = collection._repo.list_work_experiences()
            self.assertEqual(work_experiences.total_count, 2)

    def test_no_email_dedups_by_name(self):
        text = "Jane Doe\n\nExperience\nAcme Corp | Engineer  Jan 2020 – Present\n" \
               "• Built systems and infrastructure improvements across the org\n"
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            (tmp / "jane_resume_a.txt").write_text(text)
            (tmp / "jane_resume_b.txt").write_text(text)
            collection = ResumeCollection(tmp)
            collection.load()
            result = collection._repo.list_resume_summaries()
            self.assertEqual(result.total_count, 1)

    def test_distinct_people_are_not_deduped(self):
        # Sanity check: jane and john have different emails and must both survive.
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            (tmp / "jane_resume.txt").write_text(_PLAIN_RESUME)
            (tmp / "john_resume.txt").write_text(_PLAIN_RESUME_2)
            collection = ResumeCollection(tmp)
            collection.load()
            result = collection._repo.list_resume_summaries()
            self.assertEqual(result.total_count, 2)


if __name__ == "__main__":
    unittest.main()
