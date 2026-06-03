from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import resume_mcp_server.server as _srv
from resume_mcp_server.collection import ResumeCollection
from resume_mcp_server.server import (
    get_achievement,
    get_badge_skill,
    get_resume,
    get_resume_profile,
    get_work_experience,
    list_achievements,
    list_badge_skills,
    list_resume_summaries,
    list_resumes,
    list_work_experiences,
    search_achievements,
    search_resumes,
    search_resumes_by_name,
    search_resumes_by_skill,
    search_skills,
    search_work_experiences,
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
            search_resumes("query")


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
        self.assertEqual(list_resumes(), [])

    def test_list_resumes_resume_filter_empty(self):
        self.assertEqual(list_resumes(doc_type="resume"), [])

    def test_get_resume_unknown_path_returns_error(self):
        result = get_resume("nonexistent.txt")
        self.assertIsInstance(result, str)
        self.assertIn("Error", result)

    def test_search_resumes_empty(self):
        self.assertEqual(search_resumes("python"), [])

    # ── repository-layer tools ─────────────────────────────────────────────────

    def test_list_resume_summaries_empty(self):
        self.assertEqual(list_resume_summaries(), [])

    def test_get_resume_profile_unknown_returns_error(self):
        result = get_resume_profile("nonexistent-id")
        self.assertIsInstance(result, str)
        self.assertIn("Error", result)

    def test_search_skills_empty(self):
        self.assertEqual(search_skills("python"), [])

    def test_search_work_experiences_empty(self):
        self.assertEqual(search_work_experiences("engineer"), [])

    def test_search_achievements_empty(self):
        self.assertEqual(search_achievements("led"), [])

    def test_search_resumes_by_name_empty(self):
        self.assertEqual(search_resumes_by_name("Jane"), [])

    def test_search_resumes_by_skill_empty(self):
        self.assertEqual(search_resumes_by_skill("Docker"), [])

    def test_list_work_experiences_empty(self):
        self.assertEqual(list_work_experiences(), [])

    def test_get_work_experience_unknown_returns_error(self):
        result = get_work_experience("nonexistent-id")
        self.assertIsInstance(result, str)
        self.assertIn("Error", result)

    def test_list_achievements_empty(self):
        self.assertEqual(list_achievements(), [])

    def test_get_achievement_unknown_returns_error(self):
        result = get_achievement("nonexistent-id")
        self.assertIsInstance(result, str)
        self.assertIn("Error", result)

    def test_list_badge_skills_empty(self):
        self.assertEqual(list_badge_skills(), [])

    def test_get_badge_skill_unknown_returns_error(self):
        result = get_badge_skill("nonexistent-id")
        self.assertIsInstance(result, str)
        self.assertIn("Error", result)


# ── Collection-layer tools ────────────────────────────────────────────────────


class TestListResumes(_ServerFixture):
    def test_no_filter_returns_structured_data_for_parsed_resumes(self):
        results = list_resumes()
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        # Structured resume dicts have 'first_name' from Pydantic model_dump
        self.assertTrue(any("first_name" in r for r in results))

    def test_resume_filter_returns_structured_data(self):
        results = list_resumes(doc_type="resume")
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    def test_cover_letter_filter_returns_flat_metadata(self):
        results = list_resumes(doc_type="cover_letter")
        self.assertEqual(len(results), 1)
        self.assertIn("path", results[0])
        self.assertIn("filename", results[0])
        self.assertIn("doc_type", results[0])
        self.assertEqual(results[0]["doc_type"], "cover_letter")

    def test_unknown_doc_type_returns_empty(self):
        results = list_resumes(doc_type="other")
        self.assertIsInstance(results, list)

    def test_result_is_serialisable(self):
        import json
        results = list_resumes()
        json.dumps(results)  # must not raise

    def test_cover_letter_flat_has_size_bytes(self):
        results = list_resumes(doc_type="cover_letter")
        self.assertIn("size_bytes", results[0])

    def test_cover_letter_flat_has_modified(self):
        results = list_resumes(doc_type="cover_letter")
        self.assertIn("modified", results[0])


class TestGetResume(_ServerFixture):
    def _first_resume_path(self):
        return list_resumes(doc_type="resume")[0].get("path") or \
               self._collection.list_all(doc_type="resume")[0].path

    def test_known_path_returns_text(self):
        path = self._collection.list_all(doc_type="resume")[0].path
        text = get_resume(path)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 50)

    def test_unknown_path_returns_error_string(self):
        result = get_resume("does_not_exist.txt")
        self.assertIsInstance(result, str)
        self.assertIn("Error", result)

    def test_cover_letter_path_returns_text(self):
        path = self._collection.list_all(doc_type="cover_letter")[0].path
        text = get_resume(path)
        self.assertIsInstance(text, str)
        self.assertIn("Hiring Manager", text)


class TestSearchResumes(_ServerFixture):
    def test_match_returns_results(self):
        results = search_resumes("Kubernetes")
        self.assertGreater(len(results), 0)

    def test_result_has_required_fields(self):
        results = search_resumes("Python")
        for r in results:
            self.assertIn("path", r)
            self.assertIn("filename", r)
            self.assertIn("doc_type", r)
            self.assertIn("match_count", r)
            self.assertIn("snippet", r)

    def test_match_count_is_positive(self):
        results = search_resumes("Python")
        self.assertTrue(all(r["match_count"] > 0 for r in results))

    def test_no_match_returns_empty(self):
        results = search_resumes("xyzzy_impossible_9999")
        self.assertEqual(results, [])

    def test_doc_type_filter_limits_results(self):
        all_results = search_resumes("the")
        resume_results = search_resumes("the", doc_type="resume")
        self.assertLessEqual(len(resume_results), len(all_results))
        self.assertTrue(all(r["doc_type"] == "resume" for r in resume_results))

    def test_snippet_contains_query_context(self):
        results = search_resumes("pipeline")
        self.assertTrue(all(isinstance(r["snippet"], str) for r in results))

    def test_case_insensitive_match(self):
        lower = search_resumes("kubernetes")
        upper = search_resumes("KUBERNETES")
        self.assertEqual(len(lower), len(upper))


# ── Repository list/get tools ─────────────────────────────────────────────────


class TestListResumeSummaries(_ServerFixture):
    def test_returns_two_resumes(self):
        summaries = list_resume_summaries()
        self.assertEqual(len(summaries), 2)

    def test_has_identity_fields(self):
        for s in list_resume_summaries():
            self.assertIn("id", s)
            self.assertIn("first_name", s)
            self.assertIn("last_name", s)
            self.assertIn("email", s)
            self.assertIn("phone_num", s)

    def test_does_not_include_work_experiences(self):
        for s in list_resume_summaries():
            self.assertNotIn("work_experiences", s)
            self.assertNotIn("badge_skills", s)

    def test_known_names_present(self):
        names = {s["first_name"] for s in list_resume_summaries()}
        self.assertEqual(names, {"Jane", "John"})

    def test_result_is_serialisable(self):
        import json
        json.dumps(list_resume_summaries())


class TestGetResumeProfile(_ServerFixture):
    def _jane_id(self):
        return next(s["id"] for s in list_resume_summaries() if s["first_name"] == "Jane")

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

    def test_unknown_id_returns_error_string(self):
        result = get_resume_profile("no-such-id")
        self.assertIsInstance(result, str)
        self.assertIn("Error", result)
        self.assertIn("no-such-id", result)


class TestListWorkExperiences(_ServerFixture):
    def test_all_returns_at_least_four(self):
        wes = list_work_experiences()
        self.assertGreaterEqual(len(wes), 4)

    def test_results_are_dicts(self):
        wes = list_work_experiences()
        self.assertTrue(all(isinstance(w, dict) for w in wes))

    def test_result_has_company_and_position(self):
        wes = list_work_experiences()
        for w in wes:
            self.assertIn("company_name", w)
            self.assertIn("position_title", w)

    def test_current_only_filter(self):
        current = list_work_experiences(current_only=True)
        self.assertGreaterEqual(len(current), 2)
        self.assertTrue(all("present" in w["end_date"].lower() for w in current))

    def test_resume_id_filter(self):
        jane_id = next(s["id"] for s in list_resume_summaries() if s["first_name"] == "Jane")
        wes = list_work_experiences(resume_id=jane_id)
        companies = {w["company_name"] for w in wes}
        self.assertIn("Acme Corp", companies)
        self.assertNotIn("CloudCo", companies)

    def test_unknown_resume_id_returns_empty(self):
        self.assertEqual(list_work_experiences(resume_id="bad-id"), [])

    def test_result_is_serialisable(self):
        import json
        json.dumps(list_work_experiences())


class TestGetWorkExperience(_ServerFixture):
    def test_known_id_returns_dict(self):
        we_id = list_work_experiences()[0]["id"]
        result = get_work_experience(we_id)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["id"], we_id)

    def test_result_includes_achievements(self):
        we_id = list_work_experiences()[0]["id"]
        result = get_work_experience(we_id)
        self.assertIn("achievements", result)
        self.assertIsInstance(result["achievements"], list)

    def test_unknown_id_returns_error_string(self):
        result = get_work_experience("no-such-id")
        self.assertIsInstance(result, str)
        self.assertIn("Error", result)
        self.assertIn("no-such-id", result)


class TestListAchievements(_ServerFixture):
    def test_all_returns_results(self):
        achs = list_achievements()
        self.assertGreater(len(achs), 0)

    def test_results_are_dicts_with_desc(self):
        achs = list_achievements()
        for a in achs:
            self.assertIn("id", a)
            self.assertIn("desc", a)

    def test_resume_id_filter(self):
        jane_id = next(s["id"] for s in list_resume_summaries() if s["first_name"] == "Jane")
        john_id = next(s["id"] for s in list_resume_summaries() if s["first_name"] == "John")
        jane_achs = {a["desc"] for a in list_achievements(resume_id=jane_id)}
        john_achs = {a["desc"] for a in list_achievements(resume_id=john_id)}
        self.assertEqual(jane_achs & john_achs, set())

    def test_unknown_resume_id_returns_empty(self):
        self.assertEqual(list_achievements(resume_id="bad-id"), [])

    def test_result_is_serialisable(self):
        import json
        json.dumps(list_achievements())


class TestGetAchievement(_ServerFixture):
    def test_known_id_returns_dict(self):
        ach_id = list_achievements()[0]["id"]
        result = get_achievement(ach_id)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["id"], ach_id)

    def test_result_has_desc(self):
        ach_id = list_achievements()[0]["id"]
        result = get_achievement(ach_id)
        self.assertIn("desc", result)
        self.assertIsInstance(result["desc"], str)
        self.assertGreater(len(result["desc"]), 0)

    def test_unknown_id_returns_error_string(self):
        result = get_achievement("no-such-id")
        self.assertIsInstance(result, str)
        self.assertIn("Error", result)
        self.assertIn("no-such-id", result)


class TestListBadgeSkills(_ServerFixture):
    def test_all_returns_skills(self):
        skills = list_badge_skills()
        titles = {s["title"] for s in skills}
        self.assertIn("Python", titles)
        self.assertIn("Docker", titles)

    def test_results_are_dicts_with_title(self):
        skills = list_badge_skills()
        for s in skills:
            self.assertIn("id", s)
            self.assertIn("title", s)

    def test_resume_id_filter(self):
        jane_id = next(s["id"] for s in list_resume_summaries() if s["first_name"] == "Jane")
        skills = list_badge_skills(resume_id=jane_id)
        titles = {s["title"] for s in skills}
        self.assertIn("Go", titles)
        self.assertNotIn("Terraform", titles)

    def test_unknown_resume_id_returns_empty(self):
        self.assertEqual(list_badge_skills(resume_id="bad-id"), [])

    def test_result_is_serialisable(self):
        import json
        json.dumps(list_badge_skills())


class TestGetBadgeSkill(_ServerFixture):
    def test_known_id_returns_dict(self):
        skill_id = list_badge_skills()[0]["id"]
        result = get_badge_skill(skill_id)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["id"], skill_id)

    def test_result_has_title(self):
        skill_id = list_badge_skills()[0]["id"]
        result = get_badge_skill(skill_id)
        self.assertIn("title", result)
        self.assertIsInstance(result["title"], str)

    def test_unknown_id_returns_error_string(self):
        result = get_badge_skill("no-such-id")
        self.assertIsInstance(result, str)
        self.assertIn("Error", result)
        self.assertIn("no-such-id", result)


# ── Search tools ──────────────────────────────────────────────────────────────


class TestSearchSkills(_ServerFixture):
    def test_exact_match(self):
        results = search_skills("Python")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Python")

    def test_partial_match(self):
        results = search_skills("kube")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Kubernetes")

    def test_case_insensitive(self):
        lower = search_skills("python")
        upper = search_skills("PYTHON")
        self.assertEqual(len(lower), len(upper))
        self.assertEqual(lower[0]["title"], upper[0]["title"])

    def test_no_match_returns_empty(self):
        self.assertEqual(search_skills("COBOL"), [])

    def test_results_are_serialisable(self):
        import json
        json.dumps(search_skills("Docker"))

    def test_result_has_id_and_title(self):
        results = search_skills("Docker")
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIn("id", r)
            self.assertIn("title", r)


class TestSearchWorkExperiences(_ServerFixture):
    def test_by_company_name(self):
        results = search_work_experiences("Acme")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["company_name"], "Acme Corp")

    def test_by_position_title(self):
        results = search_work_experiences("DevOps")
        self.assertGreater(len(results), 0)
        self.assertTrue(any(r["position_title"] == "DevOps Engineer" for r in results))

    def test_by_achievement_description(self):
        results = search_work_experiences("pipeline")
        self.assertGreater(len(results), 0)

    def test_result_includes_resume_id(self):
        results = search_work_experiences("Engineer")
        self.assertTrue(all("resume_id" in r for r in results))

    def test_no_match_returns_empty(self):
        self.assertEqual(search_work_experiences("xyzzy_impossible"), [])

    def test_results_are_dicts_with_required_fields(self):
        results = search_work_experiences("Engineer")
        for r in results:
            self.assertIn("id", r)
            self.assertIn("company_name", r)
            self.assertIn("position_title", r)

    def test_results_are_serialisable(self):
        import json
        json.dumps(search_work_experiences("Engineer"))


class TestSearchAchievements(_ServerFixture):
    def test_match_returns_results(self):
        results = search_achievements("pipeline")
        self.assertGreater(len(results), 0)

    def test_matching_text_in_desc(self):
        results = search_achievements("pipeline")
        self.assertTrue(all("pipeline" in r["desc"].lower() for r in results))

    def test_result_includes_parent_context(self):
        results = search_achievements("pipeline")
        for r in results:
            self.assertIn("company_name", r)
            self.assertIn("position_title", r)
            self.assertIn("work_experience_id", r)
            self.assertIn("resume_id", r)

    def test_scoped_by_resume_id(self):
        jane_id = next(s["id"] for s in list_resume_summaries() if s["first_name"] == "Jane")
        results = search_achievements("engineers", resume_id=jane_id)
        self.assertTrue(all(r["resume_id"] == jane_id for r in results))

    def test_wrong_scope_returns_empty(self):
        john_id = next(s["id"] for s in list_resume_summaries() if s["first_name"] == "John")
        # Jane has "Mentored...engineers" but John does not
        results = search_achievements("mentored", resume_id=john_id)
        self.assertEqual(results, [])

    def test_no_match_returns_empty(self):
        self.assertEqual(search_achievements("xyzzy_impossible_9999"), [])

    def test_case_insensitive(self):
        lower = search_achievements("pipeline")
        upper = search_achievements("PIPELINE")
        self.assertEqual(len(lower), len(upper))

    def test_results_are_serialisable(self):
        import json
        json.dumps(search_achievements("pipeline"))


class TestSearchResumesByName(_ServerFixture):
    def test_first_name_match(self):
        results = search_resumes_by_name("Jane")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["first_name"], "Jane")

    def test_last_name_match(self):
        results = search_resumes_by_name("Smith")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["last_name"], "Smith")

    def test_partial_match(self):
        results = search_resumes_by_name("Jo")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["first_name"], "John")

    def test_case_insensitive(self):
        self.assertEqual(len(search_resumes_by_name("jane")), 1)
        self.assertEqual(len(search_resumes_by_name("SMITH")), 1)

    def test_no_match_returns_empty(self):
        self.assertEqual(search_resumes_by_name("Zephyr"), [])

    def test_result_has_identity_fields(self):
        results = search_resumes_by_name("Jane")
        r = results[0]
        self.assertIn("id", r)
        self.assertIn("first_name", r)
        self.assertIn("last_name", r)
        self.assertIn("email", r)
        self.assertIn("phone_num", r)

    def test_results_are_serialisable(self):
        import json
        json.dumps(search_resumes_by_name("Jane"))


class TestSearchResumesBySkill(_ServerFixture):
    def test_shared_skill_returns_both(self):
        results = search_resumes_by_skill("Python")
        self.assertGreaterEqual(len(results), 2)

    def test_result_has_matched_skills(self):
        results = search_resumes_by_skill("Python")
        for r in results:
            self.assertIn("matched_skills", r)
            self.assertIn("Python", r["matched_skills"])

    def test_exclusive_skill_returns_one(self):
        results = search_resumes_by_skill("Terraform")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["first_name"], "John")

    def test_no_match_returns_empty(self):
        self.assertEqual(search_resumes_by_skill("COBOL"), [])

    def test_partial_skill_match(self):
        results = search_resumes_by_skill("kube")
        self.assertGreater(len(results), 0)

    def test_case_insensitive(self):
        lower = search_resumes_by_skill("python")
        upper = search_resumes_by_skill("PYTHON")
        self.assertEqual(len(lower), len(upper))

    def test_result_has_identity_fields(self):
        results = search_resumes_by_skill("Python")
        for r in results:
            self.assertIn("id", r)
            self.assertIn("first_name", r)
            self.assertIn("last_name", r)

    def test_results_are_serialisable(self):
        import json
        json.dumps(search_resumes_by_skill("Docker"))


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


if __name__ == "__main__":
    unittest.main()
