from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from resume_mcp_server.collection import ResumeCollection

# Two plain-text resumes the parser can fully structure (no markdown ## headers)
_JANE_RESUME = """\
Jane Doe
Portland, OR
jane.doe@example.com
503-555-1234

Summary
Experienced software engineer with 8+ years building distributed systems and
leading cross-functional teams. Passionate about observability and open-source.

Experience
Acme Corp | Staff Software Engineer  March 2021 – Present
• Architected a distributed job scheduling system processing 2M tasks per day
• Led a team of 6 engineers to rewrite the core ingestion pipeline in Go
• Mentored 4 junior engineers through promotion to mid-level over 2 years

Widgets Inc | Senior Software Engineer  Jan 2018 – Feb 2021
• Designed a multi-tenant API gateway handling 50k requests per second
• Migrated monolithic Rails application to microservices architecture

Skills
Languages: Python, Go, TypeScript
Tools: Docker, Kubernetes, PostgreSQL, Redis

Education
BS Computer Science, University of Oregon, 2016
"""

_JOHN_RESUME = """\
John Smith
Seattle, WA
john.smith@example.com
206-555-9876

Summary
Senior DevOps engineer with expertise in cloud infrastructure and automation.

Experience
CloudCo | DevOps Engineer  January 2021 – Present
• Designed Kubernetes cluster serving 50M requests per day at peak load
• Automated deployment pipeline reducing release time from 2 hours to 10 minutes

OldPlace Inc | Systems Administrator  June 2017 – December 2020
• Managed on-premises infrastructure for 200 employee organization
• Reduced infrastructure costs by 35 percent via cloud migration strategy

Skills
Kubernetes, Terraform, AWS, Docker, Python, Bash, Linux, Ansible

Education
BS Computer Engineering, University of Washington, 2017
"""


class TestIntegration(unittest.TestCase):
    """End-to-end tests: load plain-text resumes → exercise all repo query methods."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmpdir.name)
        (tmp / "jane_resume.txt").write_text(_JANE_RESUME)
        (tmp / "john_resume.txt").write_text(_JOHN_RESUME)
        (tmp / "acme_cover_letter.txt").write_text("Dear Hiring Manager, I am excited to apply.")
        cls.collection = ResumeCollection(tmp)
        cls.collection.load()
        cls.repo = cls.collection._repo

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    # ── Collection-level tools ────────────────────────────────────────────────

    def test_list_resumes_returns_all_documents(self):
        items = self.collection.list_all()
        self.assertEqual(len(items), 3)

    def test_list_resumes_filtered_by_resume_type(self):
        resumes = self.collection.list_all(doc_type="resume")
        self.assertEqual(len(resumes), 2)

    def test_list_resumes_filtered_by_cover_letter_type(self):
        cover_letters = self.collection.list_all(doc_type="cover_letter")
        self.assertEqual(len(cover_letters), 1)
        self.assertIn("cover_letter", cover_letters[0].filename)

    def test_get_resume_returns_full_text(self):
        items = self.collection.list_all(doc_type="resume")
        text = self.collection.get_text(items[0].path)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 100)

    def test_search_resumes_full_text_match(self):
        results = self.collection.search("Kubernetes").items
        self.assertGreater(len(results), 0)
        paths = {r["path"] for r in results}
        # Only john_resume.txt mentions Kubernetes
        self.assertTrue(any("john" in p for p in paths))

    def test_search_resumes_no_match(self):
        results = self.collection.search("xyzzy_impossible_term_9999").items
        self.assertEqual(results, [])

    def test_search_resumes_doc_type_filter(self):
        all_results = self.collection.search("Python").items
        resume_results = self.collection.search("Python", doc_type="resume").items
        self.assertLessEqual(len(resume_results), len(all_results))
        self.assertTrue(all(r["doc_type"] == "resume" for r in resume_results))

    # ── List tools (repo) ─────────────────────────────────────────────────────

    def test_list_work_experiences_all(self):
        result = self.repo.list_work_experiences()
        self.assertGreaterEqual(result.total_count, 4)  # 2 jobs per resume
        companies = {w["company_name"] for w in result.items}
        self.assertIn("Acme Corp", companies)
        self.assertIn("CloudCo", companies)

    def test_list_work_experiences_current_only(self):
        result = self.repo.list_work_experiences(current_only=True)
        self.assertGreaterEqual(result.total_count, 2)
        self.assertTrue(all(
            "present" in w["end_date"].lower() for w in result.items
        ))

    def test_list_work_experiences_filtered_by_resume(self):
        summaries = self.repo.list_resume_summaries()
        jane = next(s for s in summaries.items if s["first_name"] == "Jane")
        result = self.repo.list_work_experiences(resume_id=jane["id"])
        companies = {w["company_name"] for w in result.items}
        self.assertIn("Acme Corp", companies)
        self.assertIn("Widgets Inc", companies)
        self.assertNotIn("CloudCo", companies)

    def test_list_achievements_all(self):
        result = self.repo.list_achievements()
        self.assertGreater(result.total_count, 0)

    def test_list_achievements_filtered_by_resume(self):
        summaries = self.repo.list_resume_summaries()
        john = next(s for s in summaries.items if s["first_name"] == "John")
        john_achs = self.repo.list_achievements(resume_id=john["id"])
        self.assertGreater(john_achs.total_count, 0)
        # Jane's achievements should not appear
        jane_id = next(s["id"] for s in summaries.items if s["first_name"] == "Jane")
        jane_achs = self.repo.list_achievements(resume_id=jane_id)
        jane_descs = {a["desc"] for a in jane_achs.items}
        john_descs = {a["desc"] for a in john_achs.items}
        self.assertEqual(jane_descs & john_descs, set())

    def test_list_badge_skills_all(self):
        result = self.repo.list_badge_skills()
        titles = {s["title"] for s in result.items}
        self.assertIn("Python", titles)
        self.assertIn("Docker", titles)

    def test_list_badge_skills_filtered_by_resume(self):
        summaries = self.repo.list_resume_summaries()
        jane = next(s for s in summaries.items if s["first_name"] == "Jane")
        result = self.repo.list_badge_skills(resume_id=jane["id"])
        titles = {s["title"] for s in result.items}
        self.assertIn("Go", titles)
        self.assertNotIn("Terraform", titles)  # John's skill

    def test_list_resume_summaries(self):
        result = self.repo.list_resume_summaries()
        self.assertEqual(result.total_count, 2)
        names = {s["first_name"] for s in result.items}
        self.assertEqual(names, {"Jane", "John"})
        for s in result.items:
            self.assertIn("id", s)
            self.assertIn("email", s)
            self.assertNotIn("work_experiences", s)

    # ── Get tools (repo) ──────────────────────────────────────────────────────

    def test_get_work_experience_by_id(self):
        result = self.repo.list_work_experiences()
        we_id = result.items[0]["id"]
        we = self.repo.find_work_experience(we_id)
        self.assertIsNotNone(we)
        self.assertEqual(we.id, we_id)

    def test_get_work_experience_unknown_returns_none(self):
        self.assertIsNone(self.repo.find_work_experience("bad-id"))

    def test_get_achievement_by_id(self):
        result = self.repo.list_achievements()
        ach_id = result.items[0]["id"]
        ach = self.repo.find_achievement(ach_id)
        self.assertIsNotNone(ach)
        self.assertEqual(ach.id, ach_id)

    def test_get_achievement_unknown_returns_none(self):
        self.assertIsNone(self.repo.find_achievement("bad-id"))

    def test_get_badge_skill_by_id(self):
        result = self.repo.list_badge_skills()
        skill_id = result.items[0]["id"]
        skill = self.repo.find_badge_skill(skill_id)
        self.assertIsNotNone(skill)
        self.assertEqual(skill.id, skill_id)

    def test_get_badge_skill_unknown_returns_none(self):
        self.assertIsNone(self.repo.find_badge_skill("bad-id"))

    def test_get_resume_profile(self):
        result = self.repo.list_resume_summaries()
        for s in result.items:
            profile = self.repo.get_resume_profile(s["id"])
            self.assertIsNotNone(profile)
            self.assertEqual(profile["id"], s["id"])
            self.assertIn("professional_statement", profile)
            self.assertIn("education", profile)
            self.assertNotIn("work_experiences", profile)

    def test_get_resume_profile_unknown_returns_none(self):
        self.assertIsNone(self.repo.get_resume_profile("no-such-id"))

    # ── Search tools (repo) ───────────────────────────────────────────────────

    def test_search_resumes_by_name_first_name(self):
        results = self.repo.list_resume_summaries(query="Jane").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["first_name"], "Jane")

    def test_search_resumes_by_name_partial(self):
        results = self.repo.list_resume_summaries(query="Jo").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["first_name"], "John")

    def test_search_resumes_by_name_case_insensitive(self):
        self.assertEqual(len(self.repo.list_resume_summaries(query="jane").items), 1)
        self.assertEqual(len(self.repo.list_resume_summaries(query="SMITH").items), 1)

    def test_search_resumes_by_name_no_match(self):
        self.assertEqual(self.repo.list_resume_summaries(query="Zephyr").items, [])

    def test_search_resumes_by_skill_returns_match(self):
        results = self.repo.search_resumes_by_skill("Python").items
        self.assertGreaterEqual(len(results), 2)
        for r in results:
            self.assertIn("Python", r["matched_skills"])

    def test_search_resumes_by_skill_exclusive(self):
        results = self.repo.search_resumes_by_skill("Terraform").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["first_name"], "John")

    def test_search_resumes_by_skill_no_match(self):
        self.assertEqual(self.repo.search_resumes_by_skill("COBOL").items, [])

    def test_search_skills_partial_match(self):
        results = self.repo.list_badge_skills(query="kube").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Kubernetes")

    def test_search_skills_case_insensitive(self):
        results = self.repo.list_badge_skills(query="PYTHON").items
        self.assertEqual(len(results), 1)

    def test_search_work_experiences_by_company(self):
        results = self.repo.list_work_experiences(query="Acme").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["company_name"], "Acme Corp")

    def test_search_work_experiences_by_position(self):
        results = self.repo.list_work_experiences(query="DevOps").items
        self.assertGreater(len(results), 0)
        self.assertTrue(any(r["position_title"] == "DevOps Engineer" for r in results))

    def test_search_work_experiences_includes_resume_id(self):
        results = self.repo.list_work_experiences(query="Engineer").items
        self.assertTrue(all("resume_id" in r for r in results))

    def test_search_achievements_returns_match(self):
        results = self.repo.list_achievements(query="pipeline").items
        self.assertGreater(len(results), 0)
        self.assertTrue(all("pipeline" in r["desc"].lower() for r in results))

    def test_search_achievements_includes_parent_context(self):
        results = self.repo.list_achievements(query="pipeline").items
        for r in results:
            self.assertIn("company_name", r)
            self.assertIn("position_title", r)
            self.assertIn("work_experience_id", r)
            self.assertIn("resume_id", r)

    def test_search_achievements_scoped_by_resume_id(self):
        summaries = self.repo.list_resume_summaries()
        jane_id = next(s["id"] for s in summaries.items if s["first_name"] == "Jane")
        results = self.repo.list_achievements(query="engineers", resume_id=jane_id).items
        self.assertTrue(all(r["resume_id"] == jane_id for r in results))

    def test_search_achievements_no_match(self):
        self.assertEqual(self.repo.list_achievements(query="xyzzy_impossible_9999").items, [])

    def test_search_achievements_case_insensitive(self):
        r_lower = self.repo.list_achievements(query="pipeline").items
        r_upper = self.repo.list_achievements(query="PIPELINE").items
        self.assertEqual(len(r_lower), len(r_upper))


if __name__ == "__main__":
    unittest.main()
