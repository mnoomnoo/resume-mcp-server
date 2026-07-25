from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import resume_mcp_server.server as _srv
from resume_mcp_server.collection import ResumeCollection
from resume_mcp_server.server import (
    get_achievement,
    get_badge_skill,
    get_collection_stats,
    get_education,
    get_resume,
    get_resume_full,
    get_resume_profile,
    get_side_project,
    get_skill_frequency,
    get_work_experience,
    list_achievements,
    list_education,
    list_resume_summaries,
    list_resumes,
    list_side_projects,
    list_skills,
    list_work_experiences,
    search_resumes,
    search_resumes_by_skill,
)

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

Projects
Resume Bot | Python, FastMCP
A side project that serves resume data over the Model Context Protocol.

Education
BS Computer Science, University of Oregon, 2016
Relevant Coursework: Algorithms, Operating Systems, Databases
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
Relevant Coursework: Networking, Operating Systems
"""


class _ServerFixture(unittest.TestCase):
    """Base: inject a real ResumeCollection into server._collection."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmpdir.name)
        (tmp / "jane_resume.txt").write_text(_JANE_RESUME)
        (tmp / "john_resume.txt").write_text(_JOHN_RESUME)
        (tmp / "acme_cover_letter.txt").write_text(
            "Dear Hiring Manager, I am excited to apply to Acme Corp."
        )
        cls._collection = ResumeCollection(tmp)
        cls._collection.load()
        cls._orig = _srv._collection
        _srv._collection = cls._collection

    @classmethod
    def tearDownClass(cls):
        _srv._collection = cls._orig
        cls._tmpdir.cleanup()


# ── Uninitialised guard ───────────────────────────────────────────────────────


class TestServerUninitialised(unittest.TestCase):
    """_get_collection() must raise RuntimeError when _collection is None."""

    def setUp(self):
        self._orig = _srv._collection
        _srv._collection = None

    def tearDown(self):
        _srv._collection = self._orig

    def test_list_resume_summaries_raises(self):
        with self.assertRaises(RuntimeError):
            list_resume_summaries()

    def test_list_resumes_raises(self):
        with self.assertRaises(RuntimeError):
            list_resumes()

    def test_get_resume_raises(self):
        with self.assertRaises(RuntimeError):
            get_resume("any.txt")

    def test_search_resumes_raises(self):
        with self.assertRaises(RuntimeError):
            search_resumes("query")["items"]


# ── Empty directory ───────────────────────────────────────────────────────────


class TestServerEmptyDir(unittest.TestCase):
    """All server tools must return safe empty results when the resume directory is empty."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        collection = ResumeCollection(Path(cls._tmpdir.name))
        collection.load()
        cls._orig = _srv._collection
        _srv._collection = collection

    @classmethod
    def tearDownClass(cls):
        _srv._collection = cls._orig
        cls._tmpdir.cleanup()

    # ── collection-layer tools ─────────────────────────────────────────────────

    def test_list_resumes_empty(self):
        self.assertEqual(list_resumes()["items"], [])

    def test_list_resumes_resume_filter_empty(self):
        self.assertEqual(list_resumes(doc_type="resume")["items"], [])

    def test_get_resume_unknown_path_returns_error(self):
        result = get_resume("nonexistent.txt")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)

    def test_search_resumes_empty(self):
        self.assertEqual(search_resumes("python")["items"], [])

    # ── repository-layer tools ─────────────────────────────────────────────────

    def test_list_resume_summaries_empty(self):
        self.assertEqual(list_resume_summaries()["items"], [])

    def test_get_resume_profile_unknown_returns_error(self):
        result = get_resume_profile("nonexistent-id")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)

    def test_search_skills_empty(self):
        self.assertEqual(list_skills(query="python")["items"], [])

    def test_search_work_experiences_empty(self):
        self.assertEqual(list_work_experiences(query="engineer")["items"], [])

    def test_search_achievements_empty(self):
        self.assertEqual(list_achievements(query="led")["items"], [])

    def test_search_resumes_by_name_empty(self):
        self.assertEqual(list_resume_summaries(query="Jane")["items"], [])

    def test_search_resumes_by_skill_empty(self):
        self.assertEqual(search_resumes_by_skill("Docker")["items"], [])

    def test_list_work_experiences_empty(self):
        self.assertEqual(list_work_experiences()["items"], [])

    def test_get_work_experience_unknown_returns_error(self):
        result = get_work_experience("nonexistent-id")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)

    def test_list_achievements_empty(self):
        self.assertEqual(list_achievements()["items"], [])

    def test_get_achievement_unknown_returns_error(self):
        result = get_achievement("nonexistent-id")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)

    def test_list_badge_skills_empty(self):
        self.assertEqual(list_skills()["items"], [])

    def test_get_badge_skill_unknown_returns_error(self):
        result = get_badge_skill("nonexistent-id")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)

    def test_list_side_projects_empty(self):
        self.assertEqual(list_side_projects()["items"], [])

    def test_get_side_project_unknown_returns_error(self):
        result = get_side_project("nonexistent-id")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)

    def test_search_side_projects_empty(self):
        self.assertEqual(list_side_projects(query="python")["items"], [])

    def test_search_side_projects_by_technology_empty(self):
        self.assertEqual(list_side_projects(technology="python")["items"], [])


# ── Collection-layer tools ────────────────────────────────────────────────────


class TestListResumes(_ServerFixture):
    def test_no_filter_returns_structured_data_for_parsed_resumes(self):
        result = list_resumes()
        self.assertIsInstance(result, dict)
        self.assertIn("total_count", result)
        self.assertIn("items", result)
        self.assertGreater(result["total_count"], 0)
        # Structured resume dicts have 'first_name' from Pydantic model_dump
        self.assertTrue(any("first_name" in r for r in result["items"]))

    def test_resume_filter_returns_structured_data(self):
        result = list_resumes(doc_type="resume")
        self.assertIsInstance(result, dict)
        self.assertGreater(result["total_count"], 0)

    def test_cover_letter_filter_returns_flat_metadata(self):
        result = list_resumes(doc_type="cover_letter")
        self.assertEqual(result["total_count"], 1)
        self.assertIn("path", result["items"][0])
        self.assertIn("filename", result["items"][0])
        self.assertIn("doc_type", result["items"][0])
        self.assertEqual(result["items"][0]["doc_type"], "cover_letter")

    def test_unknown_doc_type_returns_empty(self):
        result = list_resumes(doc_type="other")
        self.assertIsInstance(result, dict)
        self.assertIn("items", result)

    def test_result_is_serialisable(self):
        import json
        json.dumps(list_resumes())  # must not raise

    def test_cover_letter_flat_has_size_bytes(self):
        result = list_resumes(doc_type="cover_letter")
        self.assertIn("size_bytes", result["items"][0])

    def test_cover_letter_flat_has_modified(self):
        result = list_resumes(doc_type="cover_letter")
        self.assertIn("modified", result["items"][0])


class TestGetResume(_ServerFixture):
    def _first_resume_path(self):
        items = list_resumes(doc_type="resume")["items"]
        return items[0].get("path") if items else \
               self._collection.list_all(doc_type="resume")[0].path

    def test_known_path_returns_text(self):
        path = self._collection.list_all(doc_type="resume")[0].path
        text = get_resume(path)["text"]
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 50)

    def test_unknown_path_returns_error(self):
        result = get_resume("does_not_exist.txt")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)

    def test_cover_letter_path_returns_text(self):
        path = self._collection.list_all(doc_type="cover_letter")[0].path
        text = get_resume(path)["text"]
        self.assertIsInstance(text, str)
        self.assertIn("Hiring Manager", text)


class TestSearchResumes(_ServerFixture):
    def test_match_returns_results(self):
        results = search_resumes("Kubernetes")["items"]
        self.assertGreater(len(results), 0)

    def test_result_has_required_fields(self):
        results = search_resumes("Python")["items"]
        for r in results:
            self.assertIn("path", r)
            self.assertIn("filename", r)
            self.assertIn("doc_type", r)
            self.assertIn("match_count", r)
            self.assertIn("snippet", r)

    def test_match_count_is_positive(self):
        results = search_resumes("Python")["items"]
        self.assertTrue(all(r["match_count"] > 0 for r in results))

    def test_no_match_returns_empty(self):
        results = search_resumes("xyzzy_impossible_9999")["items"]
        self.assertEqual(results, [])

    def test_doc_type_filter_limits_results(self):
        all_results = search_resumes("the")["items"]
        resume_results = search_resumes("the", doc_type="resume")["items"]
        self.assertLessEqual(len(resume_results), len(all_results))
        self.assertTrue(all(r["doc_type"] == "resume" for r in resume_results))

    def test_snippet_contains_query_context(self):
        results = search_resumes("pipeline")["items"]
        self.assertTrue(all(isinstance(r["snippet"], str) for r in results))

    def test_case_insensitive_match(self):
        lower = search_resumes("kubernetes")["items"]
        upper = search_resumes("KUBERNETES")["items"]
        self.assertEqual(len(lower), len(upper))


# ── Repository list/get tools ─────────────────────────────────────────────────


class TestListResumeSummaries(_ServerFixture):
    def test_returns_two_resumes(self):
        result = list_resume_summaries()
        self.assertEqual(result["total_count"], 2)

    def test_has_identity_fields(self):
        for s in list_resume_summaries()["items"]:
            self.assertIn("id", s)
            self.assertIn("first_name", s)
            self.assertIn("last_name", s)
            self.assertIn("email", s)
            self.assertIn("phone_num", s)

    def test_does_not_include_work_experiences(self):
        for s in list_resume_summaries()["items"]:
            self.assertNotIn("work_experiences", s)
            self.assertNotIn("badge_skills", s)

    def test_known_names_present(self):
        names = {s["first_name"] for s in list_resume_summaries()["items"]}
        self.assertEqual(names, {"Jane", "John"})

    def test_result_is_serialisable(self):
        import json
        json.dumps(list_resume_summaries())


class TestGetResumeProfile(_ServerFixture):
    def _jane_id(self):
        return next(s["id"] for s in list_resume_summaries()["items"] if s["first_name"] == "Jane")

    def test_known_id_returns_profile(self):
        profile = get_resume_profile(self._jane_id())
        self.assertIsInstance(profile, dict)

    def test_profile_has_top_level_fields(self):
        profile = get_resume_profile(self._jane_id())
        self.assertIn("id", profile)
        self.assertIn("professional_statement", profile)
        self.assertIn("education", profile)

    def test_profile_excludes_nested_lists(self):
        profile = get_resume_profile(self._jane_id())
        self.assertNotIn("work_experiences", profile)
        self.assertNotIn("badge_skills", profile)

    def test_unknown_id_returns_error(self):
        result = get_resume_profile("no-such-id")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("no-such-id", result["error"])


class TestGetResumeFull(_ServerFixture):
    def _jane_id(self):
        return next(s["id"] for s in list_resume_summaries()["items"] if s["first_name"] == "Jane")

    def test_known_id_returns_full_nested_structure(self):
        resume = get_resume_full(self._jane_id())
        self.assertIsInstance(resume, dict)
        self.assertIn("professional_statement", resume)
        self.assertIn("work_experiences", resume)
        self.assertIn("badge_skills", resume)
        self.assertIn("side_projects", resume)
        self.assertIn("education_entries", resume)
        self.assertGreater(len(resume["work_experiences"]), 0)
        self.assertIn("achievements", resume["work_experiences"][0])

    def test_no_created_at_anywhere(self):
        import json
        self.assertNotIn("created_at", json.dumps(get_resume_full(self._jane_id())))

    def test_unknown_id_returns_error(self):
        result = get_resume_full("no-such-id")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("no-such-id", result["error"])


class TestListWorkExperiences(_ServerFixture):
    def test_all_returns_at_least_four(self):
        result = list_work_experiences()
        self.assertGreaterEqual(result["total_count"], 4)

    def test_results_are_dicts(self):
        wes = list_work_experiences()["items"]
        self.assertTrue(all(isinstance(w, dict) for w in wes))

    def test_result_has_company_and_position(self):
        wes = list_work_experiences()["items"]
        for w in wes:
            self.assertIn("company_name", w)
            self.assertIn("position_title", w)

    def test_current_only_filter(self):
        current = list_work_experiences(current_only=True)["items"]
        self.assertGreaterEqual(len(current), 2)
        self.assertTrue(all("present" in w["end_date"].lower() for w in current))

    def test_resume_id_filter(self):
        jane_id = next(s["id"] for s in list_resume_summaries()["items"] if s["first_name"] == "Jane")
        wes = list_work_experiences(resume_id=jane_id)["items"]
        companies = {w["company_name"] for w in wes}
        self.assertIn("Acme Corp", companies)
        self.assertNotIn("CloudCo", companies)

    def test_unknown_resume_id_returns_error(self):
        result = list_work_experiences(resume_id="bad-id")
        self.assertIn("error", result)

    def test_result_is_serialisable(self):
        import json
        json.dumps(list_work_experiences())

    def test_unscoped_items_include_resume_id(self):
        wes = list_work_experiences()["items"]
        self.assertTrue(all("resume_id" in w and w["resume_id"] for w in wes))

    def test_query_matches_company_position_or_achievement(self):
        results = list_work_experiences(query="Acme")["items"]
        self.assertTrue(any(w["company_name"] == "Acme Corp" for w in results))

    def test_query_no_match_returns_empty(self):
        self.assertEqual(list_work_experiences(query="xyzzy_impossible_9999")["items"], [])


class TestGetWorkExperience(_ServerFixture):
    def test_known_id_returns_dict(self):
        we_id = list_work_experiences()["items"][0]["id"]
        result = get_work_experience(we_id)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["id"], we_id)

    def test_result_includes_achievements(self):
        we_id = list_work_experiences()["items"][0]["id"]
        result = get_work_experience(we_id)
        self.assertIn("achievements", result)
        self.assertIsInstance(result["achievements"], list)

    def test_unknown_id_returns_error(self):
        result = get_work_experience("no-such-id")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("no-such-id", result["error"])


class TestListAchievements(_ServerFixture):
    def test_all_returns_results(self):
        result = list_achievements()
        self.assertGreater(result["total_count"], 0)

    def test_results_are_dicts_with_desc(self):
        achs = list_achievements()["items"]
        for a in achs:
            self.assertIn("id", a)
            self.assertIn("desc", a)

    def test_resume_id_filter(self):
        jane_id = next(s["id"] for s in list_resume_summaries()["items"] if s["first_name"] == "Jane")
        john_id = next(s["id"] for s in list_resume_summaries()["items"] if s["first_name"] == "John")
        jane_achs = {a["desc"] for a in list_achievements(resume_id=jane_id)["items"]}
        john_achs = {a["desc"] for a in list_achievements(resume_id=john_id)["items"]}
        self.assertEqual(jane_achs & john_achs, set())

    def test_unknown_resume_id_returns_error(self):
        result = list_achievements(resume_id="bad-id")
        self.assertIn("error", result)

    def test_result_is_serialisable(self):
        import json
        json.dumps(list_achievements())

    def test_bare_shape_when_scoped_and_no_query(self):
        jane_id = next(s["id"] for s in list_resume_summaries()["items"] if s["first_name"] == "Jane")
        achs = list_achievements(resume_id=jane_id)["items"]
        self.assertTrue(achs)
        for a in achs:
            self.assertEqual(set(a.keys()), {"id", "desc"})

    def test_rich_shape_when_unscoped(self):
        achs = list_achievements()["items"]
        self.assertTrue(achs)
        for a in achs:
            self.assertIn("company_name", a)
            self.assertIn("position_title", a)
            self.assertIn("work_experience_id", a)
            self.assertIn("resume_id", a)

    def test_rich_shape_when_query_given_even_if_scoped(self):
        jane_id = next(s["id"] for s in list_resume_summaries()["items"] if s["first_name"] == "Jane")
        achs = list_achievements(resume_id=jane_id, query="e")["items"]
        self.assertTrue(achs)
        for a in achs:
            self.assertIn("company_name", a)
            self.assertIn("resume_id", a)


class TestGetAchievement(_ServerFixture):
    def test_known_id_returns_dict(self):
        ach_id = list_achievements()["items"][0]["id"]
        result = get_achievement(ach_id)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["id"], ach_id)

    def test_result_has_desc(self):
        ach_id = list_achievements()["items"][0]["id"]
        result = get_achievement(ach_id)
        self.assertIn("desc", result)
        self.assertIsInstance(result["desc"], str)
        self.assertGreater(len(result["desc"]), 0)

    def test_unknown_id_returns_error(self):
        result = get_achievement("no-such-id")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("no-such-id", result["error"])


class TestListBadgeSkills(_ServerFixture):
    def test_all_returns_skills(self):
        titles = {s["title"] for s in list_skills()["items"]}
        self.assertIn("Python", titles)
        self.assertIn("Docker", titles)

    def test_results_are_dicts_with_title(self):
        skills = list_skills()["items"]
        for s in skills:
            self.assertIn("id", s)
            self.assertIn("title", s)

    def test_resume_id_filter(self):
        jane_id = next(s["id"] for s in list_resume_summaries()["items"] if s["first_name"] == "Jane")
        titles = {s["title"] for s in list_skills(resume_id=jane_id)["items"]}
        self.assertIn("Go", titles)
        self.assertNotIn("Terraform", titles)

    def test_unknown_resume_id_returns_error(self):
        result = list_skills(resume_id="bad-id")
        self.assertIn("error", result)

    def test_result_is_serialisable(self):
        import json
        json.dumps(list_skills())

    def test_resume_id_and_query_combined(self):
        jane_id = next(s["id"] for s in list_resume_summaries()["items"] if s["first_name"] == "Jane")
        titles = {s["title"] for s in list_skills(resume_id=jane_id, query="Go")["items"]}
        self.assertIn("Go", titles)
        self.assertNotIn("Python", titles)


class TestGetBadgeSkill(_ServerFixture):
    def test_known_id_returns_dict(self):
        skill_id = list_skills()["items"][0]["id"]
        result = get_badge_skill(skill_id)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["id"], skill_id)

    def test_result_has_title(self):
        skill_id = list_skills()["items"][0]["id"]
        result = get_badge_skill(skill_id)
        self.assertIn("title", result)
        self.assertIsInstance(result["title"], str)

    def test_unknown_id_returns_error(self):
        result = get_badge_skill("no-such-id")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("no-such-id", result["error"])


class TestListSideProjects(_ServerFixture):
    def test_returns_results(self):
        result = list_side_projects()
        self.assertGreater(result["total_count"], 0)
        self.assertTrue(any(p["name"] == "Resume Bot" for p in result["items"]))

    def test_resume_id_filter(self):
        all_count = list_side_projects()["total_count"]
        resume_id = next(p for p in list_resume_summaries(query="Jane")["items"])["id"]
        results = list_side_projects(resume_id=resume_id)["items"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Resume Bot")
        self.assertGreaterEqual(all_count, len(results))

    def test_results_are_serialisable(self):
        import json
        json.dumps(list_side_projects())


class TestGetSideProject(_ServerFixture):
    def test_known_id_returns_dict(self):
        project_id = list_side_projects()["items"][0]["id"]
        result = get_side_project(project_id)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["id"], project_id)
        self.assertIn("technologies", result)

    def test_unknown_id_returns_error(self):
        result = get_side_project("no-such-id")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("no-such-id", result["error"])


class TestSearchSideProjects(_ServerFixture):
    def test_match_by_name(self):
        results = list_side_projects(query="Resume Bot")["items"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Resume Bot")
        self.assertIn("resume_id", results[0])

    def test_match_by_description(self):
        results = list_side_projects(query="Model Context Protocol")["items"]
        self.assertEqual(len(results), 1)

    def test_no_match_returns_empty(self):
        self.assertEqual(list_side_projects(query="quantum entanglement")["items"], [])

    def test_results_are_serialisable(self):
        import json
        json.dumps(list_side_projects(query="Resume")["items"])


class TestSearchSideProjectsByTechnology(_ServerFixture):
    def test_match_returns_results(self):
        results = list_side_projects(technology="Python")["items"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Resume Bot")
        self.assertIn("Python", results[0]["matched_technologies"])

    def test_partial_match(self):
        results = list_side_projects(technology="fastmcp")["items"]
        self.assertEqual(len(results), 1)

    def test_no_match_returns_empty(self):
        self.assertEqual(list_side_projects(technology="COBOL")["items"], [])

    def test_results_are_serialisable(self):
        import json
        json.dumps(list_side_projects(technology="Python")["items"])

    def test_technology_takes_precedence_over_query(self):
        # "quantum entanglement" would match no name/description; technology="Python"
        # should still win and return the lighter matched_technologies shape.
        results = list_side_projects(query="quantum entanglement", technology="Python")["items"]
        self.assertEqual(len(results), 1)
        self.assertIn("matched_technologies", results[0])
        self.assertNotIn("technologies", results[0])


# ── Search tools ──────────────────────────────────────────────────────────────


class TestSearchSkills(_ServerFixture):
    def test_exact_match(self):
        results = list_skills(query="Python")["items"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Python")

    def test_partial_match(self):
        results = list_skills(query="kube")["items"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Kubernetes")

    def test_case_insensitive(self):
        lower = list_skills(query="python")["items"]
        upper = list_skills(query="PYTHON")["items"]
        self.assertEqual(len(lower), len(upper))
        self.assertEqual(lower[0]["title"], upper[0]["title"])

    def test_no_match_returns_empty(self):
        self.assertEqual(list_skills(query="COBOL")["items"], [])

    def test_results_are_serialisable(self):
        import json
        json.dumps(list_skills(query="Docker")["items"])

    def test_result_has_id_and_title(self):
        results = list_skills(query="Docker")["items"]
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIn("id", r)
            self.assertIn("title", r)


class TestSearchWorkExperiences(_ServerFixture):
    def test_by_company_name(self):
        results = list_work_experiences(query="Acme")["items"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["company_name"], "Acme Corp")

    def test_by_position_title(self):
        results = list_work_experiences(query="DevOps")["items"]
        self.assertGreater(len(results), 0)
        self.assertTrue(any(r["position_title"] == "DevOps Engineer" for r in results))

    def test_by_achievement_description(self):
        results = list_work_experiences(query="pipeline")["items"]
        self.assertGreater(len(results), 0)

    def test_result_includes_resume_id(self):
        results = list_work_experiences(query="Engineer")["items"]
        self.assertTrue(all("resume_id" in r for r in results))

    def test_no_match_returns_empty(self):
        self.assertEqual(list_work_experiences(query="xyzzy_impossible")["items"], [])

    def test_results_are_dicts_with_required_fields(self):
        results = list_work_experiences(query="Engineer")["items"]
        for r in results:
            self.assertIn("id", r)
            self.assertIn("company_name", r)
            self.assertIn("position_title", r)

    def test_results_are_serialisable(self):
        import json
        json.dumps(list_work_experiences(query="Engineer")["items"])


class TestSearchAchievements(_ServerFixture):
    def test_match_returns_results(self):
        results = list_achievements(query="pipeline")["items"]
        self.assertGreater(len(results), 0)

    def test_matching_text_in_desc(self):
        results = list_achievements(query="pipeline")["items"]
        self.assertTrue(all("pipeline" in r["desc"].lower() for r in results))

    def test_result_includes_parent_context(self):
        results = list_achievements(query="pipeline")["items"]
        for r in results:
            self.assertIn("company_name", r)
            self.assertIn("position_title", r)
            self.assertIn("work_experience_id", r)
            self.assertIn("resume_id", r)

    def test_scoped_by_resume_id(self):
        jane_id = next(s["id"] for s in list_resume_summaries()["items"] if s["first_name"] == "Jane")
        results = list_achievements(query="engineers", resume_id=jane_id)["items"]
        self.assertTrue(all(r["resume_id"] == jane_id for r in results))

    def test_wrong_scope_returns_empty(self):
        john_id = next(s["id"] for s in list_resume_summaries()["items"] if s["first_name"] == "John")
        # Jane has "Mentored...engineers" but John does not
        results = list_achievements(query="mentored", resume_id=john_id)["items"]
        self.assertEqual(results, [])

    def test_no_match_returns_empty(self):
        self.assertEqual(list_achievements(query="xyzzy_impossible_9999")["items"], [])

    def test_case_insensitive(self):
        lower = list_achievements(query="pipeline")["items"]
        upper = list_achievements(query="PIPELINE")["items"]
        self.assertEqual(len(lower), len(upper))

    def test_results_are_serialisable(self):
        import json
        json.dumps(list_achievements(query="pipeline")["items"])


class TestSearchResumesByName(_ServerFixture):
    def test_first_name_match(self):
        results = list_resume_summaries(query="Jane")["items"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["first_name"], "Jane")

    def test_last_name_match(self):
        results = list_resume_summaries(query="Smith")["items"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["last_name"], "Smith")

    def test_partial_match(self):
        results = list_resume_summaries(query="Jo")["items"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["first_name"], "John")

    def test_case_insensitive(self):
        self.assertEqual(len(list_resume_summaries(query="jane")["items"]), 1)
        self.assertEqual(len(list_resume_summaries(query="SMITH")["items"]), 1)

    def test_no_match_returns_empty(self):
        self.assertEqual(list_resume_summaries(query="Zephyr")["items"], [])

    def test_result_has_identity_fields(self):
        results = list_resume_summaries(query="Jane")["items"]
        r = results[0]
        self.assertIn("id", r)
        self.assertIn("first_name", r)
        self.assertIn("last_name", r)
        self.assertIn("email", r)
        self.assertIn("phone_num", r)

    def test_results_are_serialisable(self):
        import json
        json.dumps(list_resume_summaries(query="Jane")["items"])


class TestSearchResumesBySkill(_ServerFixture):
    def test_shared_skill_returns_both(self):
        results = search_resumes_by_skill("Python")["items"]
        self.assertGreaterEqual(len(results), 2)

    def test_result_has_matched_skills(self):
        results = search_resumes_by_skill("Python")["items"]
        for r in results:
            self.assertIn("matched_skills", r)
            self.assertIn("Python", r["matched_skills"])

    def test_exclusive_skill_returns_one(self):
        results = search_resumes_by_skill("Terraform")["items"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["first_name"], "John")

    def test_no_match_returns_empty(self):
        self.assertEqual(search_resumes_by_skill("COBOL")["items"], [])

    def test_partial_skill_match(self):
        results = search_resumes_by_skill("kube")["items"]
        self.assertGreater(len(results), 0)

    def test_case_insensitive(self):
        lower = search_resumes_by_skill("python")["items"]
        upper = search_resumes_by_skill("PYTHON")["items"]
        self.assertEqual(len(lower), len(upper))

    def test_result_has_identity_fields(self):
        results = search_resumes_by_skill("Python")["items"]
        for r in results:
            self.assertIn("id", r)
            self.assertIn("first_name", r)
            self.assertIn("last_name", r)

    def test_results_are_serialisable(self):
        import json
        json.dumps(search_resumes_by_skill("Docker")["items"])


# ── Education tools ───────────────────────────────────────────────────────────


class TestListEducation(_ServerFixture):
    def test_returns_results(self):
        result = list_education()
        self.assertGreaterEqual(result["total_count"], 2)
        self.assertTrue(any(e["institution"] == "University of Oregon" for e in result["items"]))

    def test_resume_id_filter(self):
        jane_id = next(s["id"] for s in list_resume_summaries()["items"] if s["first_name"] == "Jane")
        results = list_education(resume_id=jane_id)["items"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["institution"], "University of Oregon")

    def test_unknown_resume_id_returns_error(self):
        result = list_education(resume_id="bad-id")
        self.assertIn("error", result)

    def test_includes_competencies(self):
        jane_id = next(s["id"] for s in list_resume_summaries()["items"] if s["first_name"] == "Jane")
        results = list_education(resume_id=jane_id)["items"]
        titles = {c["title"] for c in results[0]["competencies"]}
        self.assertIn("Algorithms", titles)

    def test_results_are_serialisable(self):
        import json
        json.dumps(list_education())


class TestGetEducation(_ServerFixture):
    def test_known_id_returns_dict(self):
        edu_id = list_education()["items"][0]["id"]
        result = get_education(edu_id)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["id"], edu_id)

    def test_result_has_expected_fields(self):
        edu_id = list_education()["items"][0]["id"]
        result = get_education(edu_id)
        self.assertIn("institution", result)
        self.assertIn("degree", result)
        self.assertIn("year", result)
        self.assertIn("competencies", result)

    def test_unknown_id_returns_error(self):
        result = get_education("no-such-id")
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("no-such-id", result["error"])


class TestSearchEducation(_ServerFixture):
    def test_by_institution(self):
        results = list_education(query="Oregon")["items"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["institution"], "University of Oregon")

    def test_by_degree(self):
        results = list_education(query="Computer Engineering")["items"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["degree"], "BS Computer Engineering")

    def test_by_competency(self):
        results = list_education(query="Operating Systems")["items"]
        self.assertEqual(len(results), 2)

    def test_resume_id_scope(self):
        jane_id = next(s["id"] for s in list_resume_summaries()["items"] if s["first_name"] == "Jane")
        results = list_education(query="Operating Systems", resume_id=jane_id)["items"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["resume_id"], jane_id)

    def test_no_match_returns_empty(self):
        self.assertEqual(list_education(query="Nonexistent University")["items"], [])

    def test_results_include_resume_id(self):
        results = list_education(query="Oregon")["items"]
        self.assertTrue(all("resume_id" in r for r in results))

    def test_results_are_serialisable(self):
        import json
        json.dumps(list_education(query="Oregon")["items"])


class TestSearchEducationByCompetency(_ServerFixture):
    def test_match_returns_results(self):
        results = list_education(competency="Algorithms")["items"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["institution"], "University of Oregon")
        self.assertIn("Algorithms", results[0]["matched_competencies"])

    def test_shared_competency_returns_both(self):
        results = list_education(competency="Operating Systems")["items"]
        self.assertEqual(len(results), 2)

    def test_partial_match(self):
        results = list_education(competency="operating")["items"]
        self.assertEqual(len(results), 2)

    def test_no_match_returns_empty(self):
        self.assertEqual(list_education(competency="COBOL")["items"], [])

    def test_results_include_resume_id(self):
        results = list_education(competency="Algorithms")["items"]
        self.assertTrue(all("resume_id" in r for r in results))

    def test_results_are_serialisable(self):
        import json
        json.dumps(list_education(competency="Algorithms")["items"])

    def test_competency_takes_precedence_over_query(self):
        results = list_education(query="quantum entanglement", competency="Algorithms")["items"]
        self.assertEqual(len(results), 1)
        self.assertIn("matched_competencies", results[0])
        self.assertNotIn("competencies", results[0])


# ── Analytics tools ───────────────────────────────────────────────────────────


class TestGetCollectionStats(_ServerFixture):
    def test_returns_dict(self):
        result = get_collection_stats()
        self.assertIsInstance(result, dict)

    def test_has_all_expected_keys(self):
        result = get_collection_stats()
        expected = {
            "total_resumes", "total_work_experiences", "total_unique_skills",
            "total_side_projects", "total_education_entries", "total_achievements",
            "avg_skills_per_resume", "avg_work_experiences_per_resume",
        }
        self.assertEqual(set(result.keys()), expected)

    def test_total_resumes_is_two(self):
        result = get_collection_stats()
        self.assertEqual(result["total_resumes"], 2)

    def test_total_unique_skills_is_positive(self):
        result = get_collection_stats()
        self.assertGreater(result["total_unique_skills"], 0)

    def test_avg_skills_per_resume_is_positive(self):
        result = get_collection_stats()
        self.assertGreater(result["avg_skills_per_resume"], 0)

    def test_avg_work_experiences_per_resume_is_positive(self):
        result = get_collection_stats()
        self.assertGreater(result["avg_work_experiences_per_resume"], 0)

    def test_result_is_serialisable(self):
        import json
        json.dumps(get_collection_stats())


class TestGetSkillFrequency(_ServerFixture):
    def test_returns_list(self):
        result = get_skill_frequency()
        self.assertIsInstance(result, list)

    def test_each_item_has_required_fields(self):
        for item in get_skill_frequency():
            self.assertIn("skill_id", item)
            self.assertIn("skill_title", item)
            self.assertIn("resume_count", item)

    def test_limit_one_returns_one_item(self):
        result = get_skill_frequency(limit=1)
        self.assertEqual(len(result), 1)

    def test_top_item_has_positive_count(self):
        result = get_skill_frequency(limit=1)
        self.assertGreater(result[0]["resume_count"], 0)

    def test_shared_skill_has_count_two(self):
        # Python and Docker appear in both fixtures
        results = get_skill_frequency()
        shared = [r for r in results if r["skill_title"] in ("Python", "Docker")]
        self.assertTrue(any(r["resume_count"] == 2 for r in shared))

    def test_result_is_serialisable(self):
        import json
        json.dumps(get_skill_frequency())


class TestSearchResumesBySkillList(_ServerFixture):
    """search_resumes_by_skill also accepts a list of skills (merged from the former
    search_resumes_by_skills tool)."""

    def test_single_skill_matches_both(self):
        results = search_resumes_by_skill(["Python"])["items"]
        self.assertGreaterEqual(len(results), 2)

    def test_list_of_one_same_ids_as_string_form(self):
        single = {r["id"] for r in search_resumes_by_skill("Python")["items"]}
        multi = {r["id"] for r in search_resumes_by_skill(["Python"])["items"]}
        self.assertEqual(single, multi)

    def test_and_mode_returns_subset(self):
        python_only = {r["id"] for r in search_resumes_by_skill(["Python"])["items"]}
        both = {r["id"] for r in search_resumes_by_skill(["Python", "Terraform"], mode="and")["items"]}
        self.assertTrue(both.issubset(python_only))

    def test_and_mode_exclusive_skill_returns_one(self):
        results = search_resumes_by_skill(["Python", "Terraform"], mode="and")["items"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["first_name"], "John")

    def test_or_mode_returns_superset_of_and(self):
        and_ids = {r["id"] for r in search_resumes_by_skill(["Python", "Terraform"], mode="and")["items"]}
        or_ids = {r["id"] for r in search_resumes_by_skill(["Python", "Terraform"], mode="or")["items"]}
        self.assertTrue(and_ids.issubset(or_ids))

    def test_unknown_skill_returns_empty(self):
        self.assertEqual(search_resumes_by_skill(["COBOL"])["items"], [])

    def test_and_with_one_unknown_returns_empty(self):
        self.assertEqual(search_resumes_by_skill(["Python", "COBOL"], mode="and")["items"], [])

    def test_or_with_one_unknown_returns_match(self):
        results = search_resumes_by_skill(["Python", "COBOL"], mode="or")["items"]
        self.assertGreaterEqual(len(results), 2)

    def test_case_insensitive(self):
        lower = search_resumes_by_skill(["python"])["items"]
        upper = search_resumes_by_skill(["Python"])["items"]
        self.assertEqual({r["id"] for r in lower}, {r["id"] for r in upper})

    def test_each_result_has_matched_skills(self):
        for r in search_resumes_by_skill(["Python"])["items"]:
            self.assertIn("matched_skills", r)
            self.assertIsInstance(r["matched_skills"], list)
            self.assertIn("Python", r["matched_skills"])

    def test_result_is_serialisable(self):
        import json
        json.dumps(search_resumes_by_skill(["Python", "Docker"])["items"])

    def test_empty_list_returns_error(self):
        result = search_resumes_by_skill([])
        self.assertIn("error", result)

    def test_list_of_blank_strings_returns_error(self):
        result = search_resumes_by_skill(["  ", ""])
        self.assertIn("error", result)

    def test_regex_mode_respects_inner_match(self):
        # Regression test: the pre-merge search_resumes_by_skills ignored `mode` for the
        # per-skill match and always used substring "and" semantics internally.
        results = search_resumes_by_skill(["^Python$"], mode="regex")["items"]
        self.assertGreaterEqual(len(results), 2)
        no_match = search_resumes_by_skill(["^Pytho$"], mode="regex")["items"]
        self.assertEqual(no_match, [])


# ── regex search mode ──────────────────────────────────────────────────────────


class TestRegexSearchMode(_ServerFixture):
    def test_search_skills_regex_alternation(self):
        results = list_skills(query=r"kubernetes|terraform", mode="regex")["items"]
        titles = {r["title"].lower() for r in results}
        self.assertTrue(titles & {"kubernetes", "terraform"})

    def test_search_skills_invalid_regex_returns_error(self):
        result = list_skills(query="(", mode="regex")
        self.assertIn("error", result)

    def test_search_resumes_invalid_regex_returns_error(self):
        result = search_resumes("(", mode="regex")
        self.assertIn("error", result)

    def test_search_resumes_regex_mode_matches(self):
        result = search_resumes(r"K[a-z]+netes", mode="regex")
        self.assertGreater(result["total_count"], 0)

    def test_search_resumes_and_mode_requires_all_tokens(self):
        results = search_resumes("Kubernetes xyzzy_impossible_9999", mode="and")["items"]
        self.assertEqual(results, [])

    def test_search_resumes_or_mode_matches_any_token(self):
        results = search_resumes("Kubernetes xyzzy_impossible_9999", mode="or")["items"]
        self.assertGreater(len(results), 0)


# ── pagination validation ──────────────────────────────────────────────────────


class TestPaginationValidation(_ServerFixture):
    def test_zero_limit_returns_error(self):
        result = list_skills(query="Python", limit=0)
        self.assertIn("error", result)

    def test_negative_limit_returns_error(self):
        result = list_skills(query="Python", limit=-1)
        self.assertIn("error", result)

    def test_negative_offset_returns_error(self):
        result = list_skills(query="Python", offset=-1)
        self.assertIn("error", result)

    def test_offset_past_end_returns_empty_not_error(self):
        result = list_resume_summaries(offset=10_000)
        self.assertNotIn("error", result)
        self.assertEqual(result["items"], [])
        self.assertFalse(result["has_more"])

    def test_list_tool_also_validates(self):
        result = list_work_experiences(limit=0)
        self.assertIn("error", result)

    def test_list_resumes_also_validates(self):
        result = list_resumes(limit=-5)
        self.assertIn("error", result)

    def test_huge_limit_is_capped(self):
        result = list_skills(limit=10_000)
        self.assertNotIn("error", result)
        self.assertLessEqual(len(result["items"]), 200)
        self.assertIn("capped to 200", result["message"])

    def test_limit_at_cap_is_not_flagged(self):
        result = list_skills(limit=200)
        self.assertNotIn("error", result)
        self.assertNotIn("capped", result["message"])


# ── Tool registration ────────────────────────────────────────────────────────


class TestToolRegistration(unittest.TestCase):
    """Guards against tool-count/annotation drift (the README's tool count has
    gone stale before — see docs/TOOLS.md and README.md, which must be kept in
    sync with this set by hand)."""

    EXPECTED_TOOL_NAMES = {
        "list_resume_summaries", "get_resume_profile", "get_resume_full",
        "list_resumes", "get_resume", "search_resumes",
        "list_skills", "get_badge_skill", "search_resumes_by_skill", "get_skill_frequency",
        "list_work_experiences", "get_work_experience", "list_achievements", "get_achievement",
        "list_side_projects", "get_side_project",
        "list_education", "get_education",
        "get_collection_stats",
    }

    def test_exact_tool_set(self):
        import asyncio
        tools = asyncio.run(_srv.mcp.list_tools())
        names = {t.name for t in tools}
        self.assertEqual(names, self.EXPECTED_TOOL_NAMES)

    def test_all_tools_are_readonly(self):
        import asyncio
        tools = asyncio.run(_srv.mcp.list_tools())
        for t in tools:
            with self.subTest(tool=t.name):
                self.assertIsNotNone(t.annotations)
                self.assertTrue(t.annotations.readOnlyHint)
                self.assertTrue(t.annotations.idempotentHint)
                self.assertFalse(t.annotations.openWorldHint)


# ── ReloadHandler unit tests ──────────────────────────────────────────────────


class TestReloadHandler(unittest.TestCase):
    def setUp(self):
        from resume_mcp_server.server import _ReloadHandler, SUPPORTED_EXTENSIONS
        self.handler = _ReloadHandler()
        self.extensions = SUPPORTED_EXTENSIONS

    def tearDown(self):
        self.handler.cancel()

    def test_relevant_supported_extension(self):
        for ext in self.extensions:
            with self.subTest(ext=ext):
                self.assertTrue(self.handler._is_relevant(f"file{ext}"))

    def test_relevant_unsupported_extension(self):
        self.assertFalse(self.handler._is_relevant("file.exe"))
        self.assertFalse(self.handler._is_relevant("file.zip"))

    def test_cancel_with_no_timer_is_safe(self):
        self.handler.cancel()  # should not raise

    def test_cancel_clears_pending_timer(self):
        self.handler._schedule()
        self.assertIsNotNone(self.handler._timer)
        self.handler.cancel()
        self.assertIsNone(self.handler._timer)

    def test_schedule_replaces_existing_timer(self):
        self.handler._schedule()
        first_timer = self.handler._timer
        self.handler._schedule()
        second_timer = self.handler._timer
        self.assertIsNot(first_timer, second_timer)

    def _make_event(self, path, is_directory=False):
        class _Ev:
            src_path = path
        _Ev.is_directory = is_directory
        return _Ev()

    def test_on_modified_relevant_schedules(self):
        self.handler.on_modified(self._make_event("resume.txt"))
        self.assertIsNotNone(self.handler._timer)

    def test_on_modified_directory_ignored(self):
        self.handler.on_modified(self._make_event("somedir", is_directory=True))
        self.assertIsNone(self.handler._timer)

    def test_on_created_relevant_schedules(self):
        self.handler.on_created(self._make_event("new_resume.docx"))
        self.assertIsNotNone(self.handler._timer)

    def test_on_deleted_relevant_schedules(self):
        self.handler.on_deleted(self._make_event("old_resume.pdf"))
        self.assertIsNotNone(self.handler._timer)

    def test_on_moved_dst_relevant_schedules(self):
        class _MovedEv:
            src_path = "file.xyz"
            dest_path = "renamed.txt"
            is_directory = False
        self.handler.on_moved(_MovedEv())
        self.assertIsNotNone(self.handler._timer)

    def test_on_moved_src_relevant_schedules(self):
        class _MovedEv:
            src_path = "old.docx"
            dest_path = "new.xyz"
            is_directory = False
        self.handler.on_moved(_MovedEv())
        self.assertIsNotNone(self.handler._timer)

    def test_on_moved_neither_relevant_no_schedule(self):
        class _MovedEv:
            src_path = "a.exe"
            dest_path = "b.zip"
            is_directory = False
        self.handler.on_moved(_MovedEv())
        self.assertIsNone(self.handler._timer)

    def test_reload_calls_collection_load_and_clears_timer(self):
        mock_collection = MagicMock()
        mock_collection.load.return_value = 7
        self.handler._timer = MagicMock()  # simulate a pending timer
        with patch("resume_mcp_server.server._collection", mock_collection):
            self.handler._reload()
        mock_collection.load.assert_called_once_with()
        self.assertIsNone(self.handler._timer)

    def test_reload_with_no_collection_is_safe(self):
        self.handler._timer = MagicMock()
        with patch("resume_mcp_server.server._collection", None):
            self.handler._reload()  # should not raise
        self.assertIsNone(self.handler._timer)


if __name__ == "__main__":
    unittest.main()
