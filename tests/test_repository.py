from __future__ import annotations

import unittest

from resume_mcp_server.models import (
    AchievementCreate,
    BadgeSkillCreate,
    EducationCreate,
    ResumeCreate,
    SideProjectCreate,
    WorkExperienceCreate,
)
from resume_mcp_server.repository import ResumeRepository


def _make_resume(
    first: str = "Jane",
    last: str = "Doe",
    skills: list[str] | None = None,
    companies: list[str] | None = None,
    projects: list[SideProjectCreate] | None = None,
    education_entries: list[EducationCreate] | None = None,
) -> ResumeCreate:
    badge_skills = [BadgeSkillCreate(title=s) for s in (skills or [])]
    work_experiences = [
        WorkExperienceCreate(
            company_name=c,
            position_title="Engineer",
            start_date="Jan 2020",
            end_date="Present",
            achievements=[
                AchievementCreate(desc=f"Did something great at {c}"),
                AchievementCreate(desc=f"Improved performance at {c}"),
            ],
        )
        for c in (companies or [])
    ]
    return ResumeCreate(
        first_name=first,
        last_name=last,
        email=f"{first.lower()}@example.com",
        phone_num="555-555-5555",
        address="Portland, OR",
        professional_statement="Experienced engineer",
        education="BS Computer Science",
        work_experiences=work_experiences,
        badge_skills=badge_skills,
        side_projects=projects or [],
        education_entries=education_entries or [],
    )


def _make_resume_mixed_dates(first: str = "Jane", last: str = "Doe") -> ResumeCreate:
    return ResumeCreate(
        first_name=first, last_name=last,
        email=f"{first.lower()}@example.com", phone_num="555-555-5555",
        address="Portland, OR", professional_statement="", education="",
        work_experiences=[
            WorkExperienceCreate(
                company_name="CurrentCo", position_title="Engineer",
                start_date="Jan 2022", end_date="Present",
                achievements=[AchievementCreate(desc="Current role task")],
            ),
            WorkExperienceCreate(
                company_name="PastCo", position_title="Engineer",
                start_date="Jan 2018", end_date="Dec 2021",
                achievements=[AchievementCreate(desc="Past role task")],
            ),
        ],
        badge_skills=[], side_projects=[],
    )


# ── add + retrieve ────────────────────────────────────────────────────────────

class TestResumeAddAndFind(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_add_resume_returns_response_with_id(self):
        resp = self.repo.add_resume(_make_resume())
        self.assertTrue(resp.id)
        self.assertEqual(resp.first_name, "Jane")
        self.assertEqual(resp.last_name, "Doe")

    def test_find_resume_roundtrip(self):
        resp = self.repo.add_resume(_make_resume())
        found = self.repo.find_resume(resp.id)
        self.assertIsNotNone(found)
        self.assertEqual(found.id, resp.id)
        self.assertEqual(found.email, resp.email)

    def test_find_resume_unknown_returns_none(self):
        self.assertIsNone(self.repo.find_resume("nonexistent"))

    def test_list_resumes_length(self):
        self.repo.add_resume(_make_resume("Alice", "A"))
        self.repo.add_resume(_make_resume("Bob", "B"))
        self.assertEqual(self.repo.list_resumes().total_count, 2)


# ── badge skill ordering ──────────────────────────────────────────────────────

class TestBadgeSkillOrdering(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_order_preserved_per_resume(self):
        resp_a = self.repo.add_resume(_make_resume(skills=["Python", "Rust", "Go"]))
        resp_b = self.repo.add_resume(_make_resume(skills=["Go", "Python"]))
        self.assertEqual([s.title for s in resp_a.badge_skills], ["Python", "Rust", "Go"])
        self.assertEqual([s.title for s in resp_b.badge_skills], ["Go", "Python"])

    def test_deduplication(self):
        self.repo.add_resume(_make_resume(skills=["Python", "Rust", "Go"]))
        self.repo.add_resume(_make_resume(skills=["Go", "Python"]))
        self.assertEqual(len(self.repo._badge_skills), 3)

    def test_list_filtered_by_resume_preserves_order(self):
        resp_a = self.repo.add_resume(_make_resume(skills=["Python", "Rust", "Go"]))
        resp_b = self.repo.add_resume(_make_resume(skills=["Go", "Python"]))
        self.assertEqual([s["title"] for s in self.repo.list_badge_skills(resume_id=resp_a.id).items], ["Python", "Rust", "Go"])
        self.assertEqual([s["title"] for s in self.repo.list_badge_skills(resume_id=resp_b.id).items], ["Go", "Python"])

    def test_list_unknown_resume_raises(self):
        with self.assertRaises(ValueError):
            self.repo.list_badge_skills(resume_id="bad-id")


# ── work experience ordering ──────────────────────────────────────────────────

class TestWorkExperienceOrdering(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_order_preserved(self):
        resp = self.repo.add_resume(_make_resume(companies=["Acme", "Globex", "Initech"]))
        self.assertEqual([w.company_name for w in resp.work_experiences], ["Acme", "Globex", "Initech"])

    def test_list_filtered_preserves_order(self):
        resp = self.repo.add_resume(_make_resume(companies=["Acme", "Globex", "Initech"]))
        wes = self.repo.list_work_experiences(resume_id=resp.id).items
        self.assertEqual([w["company_name"] for w in wes], ["Acme", "Globex", "Initech"])

    def test_list_unknown_resume_raises(self):
        with self.assertRaises(ValueError):
            self.repo.list_work_experiences(resume_id="bad-id")


# ── achievement ordering ──────────────────────────────────────────────────────

class TestAchievementOrdering(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_order_preserved_in_work_experience(self):
        we = WorkExperienceCreate(
            company_name="Acme", position_title="Engineer",
            start_date="Jan 2020", end_date="Present",
            achievements=[
                AchievementCreate(desc="First achievement at Acme"),
                AchievementCreate(desc="Second achievement at Acme"),
                AchievementCreate(desc="Third achievement at Acme"),
            ],
        )
        resume = ResumeCreate(
            first_name="Jane", last_name="Doe",
            email="jane@example.com", phone_num="555-555-5555",
            address="Portland, OR", professional_statement="",
            education="", work_experiences=[we], badge_skills=[], side_projects=[],
        )
        resp = self.repo.add_resume(resume)
        descs = [a.desc for a in resp.work_experiences[0].achievements]
        self.assertEqual(descs, [
            "First achievement at Acme",
            "Second achievement at Acme",
            "Third achievement at Acme",
        ])

    def test_list_all(self):
        self.repo.add_resume(_make_resume(companies=["Acme", "Globex"]))
        self.assertEqual(self.repo.list_achievements().total_count, 4)

    def test_list_filtered_by_resume(self):
        resp_a = self.repo.add_resume(_make_resume(companies=["Acme"]))
        self.repo.add_resume(_make_resume(companies=["Globex"]))
        achs = self.repo.list_achievements(resume_id=resp_a.id).items
        self.assertEqual(len(achs), 2)
        self.assertTrue(all("Acme" in a["desc"] for a in achs))

    def test_list_unknown_resume_raises(self):
        with self.assertRaises(ValueError):
            self.repo.list_achievements(resume_id="bad-id")


# ── find helpers ──────────────────────────────────────────────────────────────

class TestFindHelpers(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_find_work_experience(self):
        resp = self.repo.add_resume(_make_resume(companies=["Acme"]))
        we_id = resp.work_experiences[0].id
        found = self.repo.find_work_experience(we_id)
        self.assertIsNotNone(found)
        self.assertEqual(found.company_name, "Acme")

    def test_find_work_experience_unknown_returns_none(self):
        self.assertIsNone(self.repo.find_work_experience("bad-id"))

    def test_find_achievement(self):
        resp = self.repo.add_resume(_make_resume(companies=["Acme"]))
        ach_id = resp.work_experiences[0].achievements[0].id
        found = self.repo.find_achievement(ach_id)
        self.assertIsNotNone(found)
        self.assertIn("Acme", found.desc)

    def test_find_achievement_unknown_returns_none(self):
        self.assertIsNone(self.repo.find_achievement("bad-id"))

    def test_find_badge_skill(self):
        resp = self.repo.add_resume(_make_resume(skills=["Python"]))
        skill_id = resp.badge_skills[0].id
        found = self.repo.find_badge_skill(skill_id)
        self.assertIsNotNone(found)
        self.assertEqual(found.title, "Python")

    def test_find_badge_skill_unknown_returns_none(self):
        self.assertIsNone(self.repo.find_badge_skill("bad-id"))


# ── search_badge_skills ───────────────────────────────────────────────────────

class TestSearchBadgeSkills(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()
        self.repo.add_resume(_make_resume(skills=["Python", "Go", "Rust"]))

    def test_returns_match(self):
        results = self.repo.list_badge_skills(query="python").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Python")

    def test_case_insensitive(self):
        self.repo.add_resume(_make_resume(skills=["TypeScript"]))
        self.assertEqual(len(self.repo.list_badge_skills(query="typescript").items), 1)
        self.assertEqual(len(self.repo.list_badge_skills(query="TYPESCRIPT").items), 1)

    def test_no_match(self):
        self.assertEqual(self.repo.list_badge_skills(query="Java").items, [])

    def test_partial_match(self):
        repo = ResumeRepository()
        repo.add_resume(_make_resume(skills=["JavaScript", "TypeScript", "Go"]))
        results = repo.list_badge_skills(query="script").items
        self.assertEqual({s["title"] for s in results}, {"JavaScript", "TypeScript"})

    def test_multi_token_and_all_present(self):
        repo = ResumeRepository()
        repo.add_resume(_make_resume(skills=["Machine Learning"]))
        results = repo.list_badge_skills(query="Machine Learning").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Machine Learning")

    def test_multi_token_and_one_missing(self):
        repo = ResumeRepository()
        repo.add_resume(_make_resume(skills=["Machine"]))
        self.assertEqual(repo.list_badge_skills(query="Machine Learning").items, [])

    def test_multi_token_or_any_present(self):
        repo = ResumeRepository()
        repo.add_resume(_make_resume(skills=["Machine", "Learning"]))
        results = repo.list_badge_skills(query="Machine Learning", mode="or").items
        self.assertEqual(len(results), 2)

    def test_resume_id_and_query_combined(self):
        # This scoping was not possible with the old search_badge_skills (it had no
        # resume_id param at all) — new capability introduced by the merge.
        repo = ResumeRepository()
        resp_a = repo.add_resume(_make_resume("Alice", "A", skills=["Python", "Go"]))
        repo.add_resume(_make_resume("Bob", "B", skills=["Python", "Rust"]))
        results = repo.list_badge_skills(resume_id=resp_a.id, query="Python").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Python")
        self.assertEqual(repo.list_badge_skills(resume_id=resp_a.id, query="Rust").items, [])


# ── search_work_experiences ───────────────────────────────────────────────────

class TestSearchWorkExperiences(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_by_company(self):
        resp = self.repo.add_resume(_make_resume(companies=["Acme", "Globex"]))
        results = self.repo.list_work_experiences(query="Acme").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["company_name"], "Acme")
        self.assertEqual(results[0]["resume_id"], resp.id)

    def test_by_position(self):
        we = WorkExperienceCreate(
            company_name="Initech", position_title="Senior Software Engineer",
            start_date="Jan 2022", end_date="Present",
            achievements=[AchievementCreate(desc="Built pipelines")],
        )
        resume = ResumeCreate(
            first_name="Jane", last_name="Doe",
            email="jane@example.com", phone_num="555-555-5555",
            address="Portland, OR", professional_statement="",
            education="", work_experiences=[we], badge_skills=[], side_projects=[],
        )
        resp = self.repo.add_resume(resume)
        results = self.repo.list_work_experiences(query="Senior").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["position_title"], "Senior Software Engineer")
        self.assertEqual(results[0]["resume_id"], resp.id)

    def test_by_achievement(self):
        we = WorkExperienceCreate(
            company_name="Vandelay", position_title="Engineer",
            start_date="Jan 2021", end_date="Dec 2023",
            achievements=[AchievementCreate(desc="Reduced latency by 40%")],
        )
        resume = ResumeCreate(
            first_name="Art", last_name="Vandelay",
            email="art@example.com", phone_num="555-555-5555",
            address="New York, NY", professional_statement="",
            education="", work_experiences=[we], badge_skills=[], side_projects=[],
        )
        resp = self.repo.add_resume(resume)
        results = self.repo.list_work_experiences(query="latency").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["resume_id"], resp.id)
        self.assertTrue(any(a["desc"] == "Reduced latency by 40%" for a in results[0]["achievements"]))

    def test_no_match(self):
        self.repo.add_resume(_make_resume(companies=["Acme"]))
        self.assertEqual(self.repo.list_work_experiences(query="Nonexistent Corp").items, [])

    def test_resume_id_present(self):
        resp_a = self.repo.add_resume(_make_resume("Alice", "A", companies=["Alpha Corp"]))
        resp_b = self.repo.add_resume(_make_resume("Bob", "B", companies=["Beta Corp"]))
        results = self.repo.list_work_experiences(query="Corp").items
        resume_ids = {r["resume_id"] for r in results}
        self.assertEqual(resume_ids, {resp_a.id, resp_b.id})

    def test_does_not_mix_jobs(self):
        resp_a = self.repo.add_resume(_make_resume("Alice", "A", companies=["Acme"]))
        resp_b = self.repo.add_resume(_make_resume("Bob", "B", companies=["Acme"]))
        results = self.repo.list_work_experiences(query="Acme").items
        self.assertEqual(len(results), 2)
        self.assertNotEqual(results[0]["resume_id"], results[1]["resume_id"])
        self.assertEqual({r["resume_id"] for r in results}, {resp_a.id, resp_b.id})

    def test_search_work_experiences_includes_resume_id_in_each_result(self):
        self.repo.add_resume(_make_resume(companies=["Acme", "Globex"]))
        results = self.repo.list_work_experiences(query="Engineer").items
        self.assertTrue(all("resume_id" in r for r in results))

    def test_multi_token_and_both_in_company(self):
        we = WorkExperienceCreate(
            company_name="Acme Corporation", position_title="Dev",
            start_date="Jan 2020", end_date="Present",
            achievements=[AchievementCreate(desc="Built pipelines")],
        )
        resume = ResumeCreate(
            first_name="Test", last_name="User", email="t@example.com", phone_num="555",
            address="", professional_statement="", education="",
            work_experiences=[we], badge_skills=[], side_projects=[],
        )
        self.repo.add_resume(resume)
        results = self.repo.list_work_experiences(query="Acme Corporation").items
        self.assertEqual(len(results), 1)

    def test_multi_token_and_tokens_split_across_fields_no_match(self):
        we = WorkExperienceCreate(
            company_name="Google", position_title="Senior Engineer",
            start_date="Jan 2022", end_date="Present",
            achievements=[AchievementCreate(desc="Built APIs")],
        )
        resume = ResumeCreate(
            first_name="Test", last_name="User", email="t@example.com", phone_num="555",
            address="", professional_statement="", education="",
            work_experiences=[we], badge_skills=[], side_projects=[],
        )
        self.repo.add_resume(resume)
        # AND: "Google" in company_name, "Engineer" in position_title — different fields, no match
        results = self.repo.list_work_experiences(query="Google Engineer").items
        self.assertEqual(results, [])

    def test_multi_token_or_tokens_across_fields_matches(self):
        we = WorkExperienceCreate(
            company_name="Google", position_title="Senior Engineer",
            start_date="Jan 2022", end_date="Present",
            achievements=[AchievementCreate(desc="Built APIs")],
        )
        resume = ResumeCreate(
            first_name="Test", last_name="User", email="t@example.com", phone_num="555",
            address="", professional_statement="", education="",
            work_experiences=[we], badge_skills=[], side_projects=[],
        )
        self.repo.add_resume(resume)
        # OR: "Google" matches company_name field
        results = self.repo.list_work_experiences(query="Google Engineer", mode="or").items
        self.assertEqual(len(results), 1)


# ── list_resume_summaries ─────────────────────────────────────────────────────

class TestListResumeSummaries(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_returns_identity_fields_only(self):
        self.repo.add_resume(_make_resume("Alice", "Adams", companies=["Acme"], skills=["Python"]))
        result = self.repo.list_resume_summaries()
        self.assertEqual(result.total_count, 1)
        s = result.items[0]
        self.assertEqual(s["first_name"], "Alice")
        self.assertEqual(s["last_name"], "Adams")
        self.assertNotIn("work_experiences", s)
        self.assertNotIn("badge_skills", s)
        self.assertNotIn("professional_statement", s)
        self.assertIn("id", s)
        self.assertIn("email", s)
        self.assertIn("phone_num", s)

    def test_multiple_resumes(self):
        self.repo.add_resume(_make_resume("Alice", "A"))
        self.repo.add_resume(_make_resume("Bob", "B"))
        self.assertEqual(self.repo.list_resume_summaries().total_count, 2)

    def test_empty(self):
        result = self.repo.list_resume_summaries()
        self.assertEqual(result.total_count, 0)
        self.assertEqual(result.items, [])


# ── get_resume_profile ────────────────────────────────────────────────────────

class TestGetResumeProfile(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_returns_top_level_fields(self):
        resp = self.repo.add_resume(_make_resume("Carol", "Chen", companies=["Initech"], skills=["Go"]))
        profile = self.repo.get_resume_profile(resp.id)
        self.assertIsNotNone(profile)
        self.assertEqual(profile["first_name"], "Carol")
        self.assertEqual(profile["last_name"], "Chen")
        self.assertEqual(profile["professional_statement"], "Experienced engineer")
        self.assertEqual(profile["education"], "BS Computer Science")
        self.assertNotIn("work_experiences", profile)
        self.assertNotIn("badge_skills", profile)

    def test_unknown_returns_none(self):
        self.assertIsNone(self.repo.get_resume_profile("no-such-id"))

    def test_id_matches_resume(self):
        resp = self.repo.add_resume(_make_resume("Dana", "Davis"))
        profile = self.repo.get_resume_profile(resp.id)
        self.assertEqual(profile["id"], resp.id)


# ── list_work_experiences current_only ────────────────────────────────────────

class TestCurrentOnlyFilter(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_filters_past_jobs(self):
        self.repo.add_resume(_make_resume_mixed_dates())
        results = self.repo.list_work_experiences(current_only=True).items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["company_name"], "CurrentCo")

    def test_false_returns_all(self):
        self.repo.add_resume(_make_resume_mixed_dates())
        self.assertEqual(self.repo.list_work_experiences(current_only=False).total_count, 2)

    def test_with_resume_id(self):
        resp_a = self.repo.add_resume(_make_resume_mixed_dates("Alice", "A"))
        self.repo.add_resume(_make_resume_mixed_dates("Bob", "B"))
        results = self.repo.list_work_experiences(resume_id=resp_a.id, current_only=True).items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["company_name"], "CurrentCo")

    def test_case_insensitive_present(self):
        self.repo.add_resume(ResumeCreate(
            first_name="Eve", last_name="E",
            email="eve@example.com", phone_num="555-555-5555",
            address="Portland, OR", professional_statement="", education="",
            work_experiences=[
                WorkExperienceCreate(
                    company_name="NowCo", position_title="Dev",
                    start_date="Jan 2023", end_date="present",
                    achievements=[AchievementCreate(desc="Doing things")],
                ),
            ],
            badge_skills=[], side_projects=[],
        ))
        results = self.repo.list_work_experiences(current_only=True).items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["company_name"], "NowCo")

    def test_no_current_roles_returns_empty(self):
        self.repo.add_resume(ResumeCreate(
            first_name="Fred", last_name="F",
            email="fred@example.com", phone_num="555-555-5555",
            address="Portland, OR", professional_statement="", education="",
            work_experiences=[
                WorkExperienceCreate(
                    company_name="OldCo", position_title="Dev",
                    start_date="Jan 2015", end_date="Dec 2019",
                    achievements=[AchievementCreate(desc="Old task")],
                ),
            ],
            badge_skills=[], side_projects=[],
        ))
        self.assertEqual(self.repo.list_work_experiences(current_only=True).items, [])


# ── search_achievements ───────────────────────────────────────────────────────

class TestSearchAchievements(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_returns_match(self):
        resp = self.repo.add_resume(_make_resume(companies=["Acme"]))
        results = self.repo.list_achievements(query="great").items
        self.assertEqual(len(results), 1)
        self.assertIn("great", results[0]["desc"])
        self.assertEqual(results[0]["company_name"], "Acme")
        self.assertEqual(results[0]["resume_id"], resp.id)

    def test_includes_parent_context(self):
        resp = self.repo.add_resume(_make_resume(companies=["Globex"]))
        results = self.repo.list_achievements(query="Globex").items
        self.assertTrue(results)
        r = results[0]
        self.assertIn("company_name", r)
        self.assertIn("position_title", r)
        self.assertIn("work_experience_id", r)
        self.assertIn("resume_id", r)
        self.assertEqual(r["resume_id"], resp.id)

    def test_case_insensitive(self):
        self.repo.add_resume(_make_resume(companies=["Acme"]))
        self.assertEqual(len(self.repo.list_achievements(query="GREAT").items), 1)
        self.assertEqual(len(self.repo.list_achievements(query="Great").items), 1)

    def test_no_match(self):
        self.repo.add_resume(_make_resume(companies=["Acme"]))
        self.assertEqual(self.repo.list_achievements(query="quantum entanglement").items, [])

    def test_scoped_by_resume_id(self):
        resp_a = self.repo.add_resume(_make_resume("Alice", "A", companies=["Alpha"]))
        self.repo.add_resume(_make_resume("Bob", "B", companies=["Beta"]))
        results = self.repo.list_achievements(query="great", resume_id=resp_a.id).items
        self.assertTrue(all(r["resume_id"] == resp_a.id for r in results))
        self.assertTrue(all(r["company_name"] == "Alpha" for r in results))

    def test_scope_wrong_resume_returns_empty(self):
        resp_a = self.repo.add_resume(_make_resume("Alice", "A", companies=["Alpha"]))
        resp_b = self.repo.add_resume(_make_resume("Bob", "B", companies=["Beta"]))
        results = self.repo.list_achievements(query="Alpha", resume_id=resp_b.id).items
        self.assertEqual(results, [])

    def test_returns_only_matching_bullets(self):
        self.repo.add_resume(ResumeCreate(
            first_name="Gus", last_name="G",
            email="gus@example.com", phone_num="555-555-5555",
            address="Portland, OR", professional_statement="", education="",
            work_experiences=[
                WorkExperienceCreate(
                    company_name="MixedCo", position_title="Dev",
                    start_date="Jan 2020", end_date="Present",
                    achievements=[
                        AchievementCreate(desc="Reduced latency by 40 percent"),
                        AchievementCreate(desc="Improved reliability metrics"),
                    ],
                ),
            ],
            badge_skills=[], side_projects=[],
        ))
        results = self.repo.list_achievements(query="latency").items
        self.assertEqual(len(results), 1)
        self.assertIn("latency", results[0]["desc"])

    def _make_two_token_resume(self):
        return ResumeCreate(
            first_name="Test", last_name="User",
            email="t@example.com", phone_num="555",
            address="", professional_statement="", education="",
            work_experiences=[
                WorkExperienceCreate(
                    company_name="TestCo", position_title="Dev",
                    start_date="Jan 2020", end_date="Present",
                    achievements=[
                        AchievementCreate(desc="Reduced latency and improved throughput"),
                        AchievementCreate(desc="Reduced latency only"),
                    ],
                ),
            ],
            badge_skills=[], side_projects=[],
        )

    def test_multi_token_and_both_present(self):
        self.repo.add_resume(self._make_two_token_resume())
        results = self.repo.list_achievements(query="latency throughput").items
        self.assertEqual(len(results), 1)
        self.assertIn("throughput", results[0]["desc"])

    def test_multi_token_and_one_missing(self):
        self.repo.add_resume(ResumeCreate(
            first_name="Test", last_name="User",
            email="t@example.com", phone_num="555",
            address="", professional_statement="", education="",
            work_experiences=[WorkExperienceCreate(
                company_name="TestCo", position_title="Dev",
                start_date="Jan 2020", end_date="Present",
                achievements=[AchievementCreate(desc="Reduced latency")],
            )],
            badge_skills=[], side_projects=[],
        ))
        self.assertEqual(self.repo.list_achievements(query="latency throughput").items, [])

    def test_multi_token_and_explicit_mode(self):
        self.repo.add_resume(self._make_two_token_resume())
        results = self.repo.list_achievements(query="latency throughput", mode="and").items
        self.assertEqual(len(results), 1)

    def test_multi_token_or_any_present(self):
        self.repo.add_resume(self._make_two_token_resume())
        results = self.repo.list_achievements(query="latency throughput", mode="or").items
        self.assertEqual(len(results), 2)

    def test_multi_token_or_none_present(self):
        self.repo.add_resume(ResumeCreate(
            first_name="Test", last_name="User",
            email="t@example.com", phone_num="555",
            address="", professional_statement="", education="",
            work_experiences=[WorkExperienceCreate(
                company_name="TestCo", position_title="Dev",
                start_date="Jan 2020", end_date="Present",
                achievements=[AchievementCreate(desc="Fixed a bug")],
            )],
            badge_skills=[], side_projects=[],
        ))
        self.assertEqual(self.repo.list_achievements(query="latency throughput", mode="or").items, [])

    def test_or_returns_superset_of_and(self):
        self.repo.add_resume(self._make_two_token_resume())
        and_results = self.repo.list_achievements(query="latency throughput", mode="and").items
        or_results = self.repo.list_achievements(query="latency throughput", mode="or").items
        self.assertLess(len(and_results), len(or_results))

    def test_leading_trailing_spaces_same_as_trimmed(self):
        self.repo.add_resume(ResumeCreate(
            first_name="Test", last_name="User",
            email="t@example.com", phone_num="555",
            address="", professional_statement="", education="",
            work_experiences=[WorkExperienceCreate(
                company_name="TestCo", position_title="Dev",
                start_date="Jan 2020", end_date="Present",
                achievements=[AchievementCreate(desc="Reduced latency by 40%")],
            )],
            badge_skills=[], side_projects=[],
        ))
        self.assertEqual(
            self.repo.list_achievements(query="  latency  ").items,
            self.repo.list_achievements(query="latency").items,
        )

    def test_multiple_spaces_between_tokens(self):
        self.repo.add_resume(ResumeCreate(
            first_name="Test", last_name="User",
            email="t@example.com", phone_num="555",
            address="", professional_statement="", education="",
            work_experiences=[WorkExperienceCreate(
                company_name="TestCo", position_title="Dev",
                start_date="Jan 2020", end_date="Present",
                achievements=[AchievementCreate(desc="Reduced latency and improved throughput")],
            )],
            badge_skills=[], side_projects=[],
        ))
        self.assertEqual(
            self.repo.list_achievements(query="latency  throughput").items,
            self.repo.list_achievements(query="latency throughput").items,
        )

    def test_token_case_insensitive(self):
        self.repo.add_resume(ResumeCreate(
            first_name="Test", last_name="User",
            email="t@example.com", phone_num="555",
            address="", professional_statement="", education="",
            work_experiences=[WorkExperienceCreate(
                company_name="TestCo", position_title="Dev",
                start_date="Jan 2020", end_date="Present",
                achievements=[AchievementCreate(desc="Reduced latency and improved throughput")],
            )],
            badge_skills=[], side_projects=[],
        ))
        results = self.repo.list_achievements(query="LATENCY THROUGHPUT").items
        self.assertEqual(len(results), 1)

    def test_invalid_mode_falls_back_to_or(self):
        self.repo.add_resume(ResumeCreate(
            first_name="Test", last_name="User",
            email="t@example.com", phone_num="555",
            address="", professional_statement="", education="",
            work_experiences=[WorkExperienceCreate(
                company_name="TestCo", position_title="Dev",
                start_date="Jan 2020", end_date="Present",
                achievements=[
                    AchievementCreate(desc="Reduced latency by 40%"),
                    AchievementCreate(desc="Fixed a bug"),
                ],
            )],
            badge_skills=[], side_projects=[],
        ))
        # unrecognized mode falls to OR branch
        results = self.repo.list_achievements(query="latency throughput", mode="xor").items
        self.assertEqual(len(results), 1)
        self.assertIn("latency", results[0]["desc"])


# ── side projects ────────────────────────────────────────────────────────────

class TestSideProjects(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def _project(self, name="Resume Bot", desc="A bot that writes resumes", techs=None):
        return SideProjectCreate(
            name=name, description=desc,
            technologies=[BadgeSkillCreate(title=t) for t in (techs or [])],
        )

    def test_find_side_project(self):
        resp = self.repo.add_resume(_make_resume(projects=[self._project(techs=["Python"])]))
        project_id = resp.side_projects[0].id
        found = self.repo.find_side_project(project_id)
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "Resume Bot")
        self.assertEqual([t.title for t in found.technologies], ["Python"])

    def test_find_side_project_unknown_returns_none(self):
        self.assertIsNone(self.repo.find_side_project("bad-id"))

    def test_list_side_projects_all(self):
        self.repo.add_resume(_make_resume("Alice", "A", projects=[self._project(name="Project A")]))
        self.repo.add_resume(_make_resume("Bob", "B", projects=[self._project(name="Project B")]))
        results = self.repo.list_side_projects().items
        self.assertEqual({p["name"] for p in results}, {"Project A", "Project B"})

    def test_list_side_projects_scoped_by_resume(self):
        resp_a = self.repo.add_resume(_make_resume("Alice", "A", projects=[self._project(name="Project A")]))
        self.repo.add_resume(_make_resume("Bob", "B", projects=[self._project(name="Project B")]))
        results = self.repo.list_side_projects(resume_id=resp_a.id).items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Project A")

    def test_list_side_projects_unknown_resume_raises(self):
        with self.assertRaises(ValueError):
            self.repo.list_side_projects(resume_id="bad-id")

    def test_search_by_name(self):
        resp = self.repo.add_resume(_make_resume(projects=[self._project(name="Resume Bot")]))
        results = self.repo.list_side_projects(query="resume").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Resume Bot")
        self.assertEqual(results[0]["resume_id"], resp.id)

    def test_search_by_description(self):
        self.repo.add_resume(_make_resume(projects=[self._project(desc="A tool for tracking finances")]))
        results = self.repo.list_side_projects(query="finances").items
        self.assertEqual(len(results), 1)

    def test_search_by_technology(self):
        self.repo.add_resume(_make_resume(projects=[self._project(techs=["Rust", "WebAssembly"])]))
        results = self.repo.list_side_projects(query="wasm").items
        self.assertEqual(results, [])
        results = self.repo.list_side_projects(query="WebAssembly").items
        self.assertEqual(len(results), 1)

    def test_search_scoped_by_resume_id(self):
        resp_a = self.repo.add_resume(_make_resume("Alice", "A", projects=[self._project(name="Alpha Project")]))
        self.repo.add_resume(_make_resume("Bob", "B", projects=[self._project(name="Beta Project")]))
        results = self.repo.list_side_projects(query="Project", resume_id=resp_a.id).items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Alpha Project")

    def test_search_no_match(self):
        self.repo.add_resume(_make_resume(projects=[self._project()]))
        self.assertEqual(self.repo.list_side_projects(query="quantum entanglement").items, [])

    def test_search_by_technology_returns_matched_technologies(self):
        resp = self.repo.add_resume(_make_resume(
            projects=[self._project(name="ML Pipeline", techs=["Python", "TensorFlow"])]
        ))
        results = self.repo.list_side_projects(technology="python").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "ML Pipeline")
        self.assertEqual(results[0]["matched_technologies"], ["Python"])
        self.assertEqual(results[0]["resume_id"], resp.id)

    def test_search_by_technology_no_match(self):
        self.repo.add_resume(_make_resume(projects=[self._project(techs=["Python"])]))
        self.assertEqual(self.repo.list_side_projects(technology="COBOL").items, [])

    def test_search_by_technology_across_resumes(self):
        resp_a = self.repo.add_resume(_make_resume("Alice", "A", projects=[self._project(name="A Project", techs=["Go"])]))
        resp_b = self.repo.add_resume(_make_resume("Bob", "B", projects=[self._project(name="B Project", techs=["Go"])]))
        results = self.repo.list_side_projects(technology="Go").items
        self.assertEqual({r["resume_id"] for r in results}, {resp_a.id, resp_b.id})

    def test_technology_dedup_with_badge_skills(self):
        resp = self.repo.add_resume(_make_resume(
            skills=["Python"],
            projects=[self._project(techs=["Python"])],
        ))
        # The badge skill from the resume's skills list and the project's
        # technology should be deduped to the same BadgeSkill record.
        skill_id = resp.badge_skills[0].id
        project_tech_id = resp.side_projects[0].technologies[0].id
        self.assertEqual(skill_id, project_tech_id)

    def test_search_by_technology_multi_token_and_full_phrase(self):
        self.repo.add_resume(_make_resume(
            projects=[self._project(name="Mobile App", techs=["React Native", "TypeScript"])]
        ))
        results = self.repo.list_side_projects(technology="React Native").items
        self.assertEqual(len(results), 1)
        self.assertIn("React Native", results[0]["matched_technologies"])

    def test_search_by_technology_multi_token_and_no_partial(self):
        self.repo.add_resume(_make_resume(
            projects=[self._project(name="Web App", techs=["React", "TypeScript"])]
        ))
        # AND: both "React" and "Native" must be in the same tech title
        results = self.repo.list_side_projects(technology="React Native", mode="and").items
        self.assertEqual(results, [])

    def test_search_by_technology_multi_token_or_matches_either(self):
        self.repo.add_resume(_make_resume(
            projects=[self._project(name="Web App", techs=["React", "TypeScript"])]
        ))
        # OR: "React" matches
        results = self.repo.list_side_projects(technology="React Native", mode="or").items
        self.assertEqual(len(results), 1)
        self.assertIn("React", results[0]["matched_technologies"])

    def test_search_side_projects_multi_token_and(self):
        self.repo.add_resume(_make_resume(
            projects=[self._project(name="Finance Tracker", desc="Tracks personal finances")]
        ))
        results = self.repo.list_side_projects(query="Finance Tracker").items
        self.assertEqual(len(results), 1)

    def test_search_side_projects_multi_token_and_one_missing(self):
        self.repo.add_resume(_make_resume(
            projects=[self._project(name="Finance App", desc="Tracks expenses")]
        ))
        # "Finance" in name but "Tracker" nowhere
        results = self.repo.list_side_projects(query="Finance Tracker").items
        self.assertEqual(results, [])

    def test_search_side_projects_multi_token_or(self):
        self.repo.add_resume(_make_resume(
            projects=[self._project(name="Finance App", desc="Tracks expenses")]
        ))
        results = self.repo.list_side_projects(query="Finance Tracker", mode="or").items
        self.assertEqual(len(results), 1)


# ── search_resumes_by_name ────────────────────────────────────────────────────

class TestSearchResumesByName(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_first_name(self):
        resp = self.repo.add_resume(_make_resume("Hannah", "Hill"))
        results = self.repo.list_resume_summaries(query="Hannah").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], resp.id)

    def test_last_name(self):
        resp = self.repo.add_resume(_make_resume("Hannah", "Hill"))
        results = self.repo.list_resume_summaries(query="Hill").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], resp.id)

    def test_case_insensitive(self):
        self.repo.add_resume(_make_resume("Ivan", "Ivanov"))
        self.assertEqual(len(self.repo.list_resume_summaries(query="ivan").items), 1)
        self.assertEqual(len(self.repo.list_resume_summaries(query="IVANOV").items), 1)

    def test_partial_match(self):
        self.repo.add_resume(_make_resume("Julia", "Jones"))
        self.assertEqual(len(self.repo.list_resume_summaries(query="Jul").items), 1)

    def test_no_match(self):
        self.repo.add_resume(_make_resume("Karl", "King"))
        self.assertEqual(self.repo.list_resume_summaries(query="Zephyr").items, [])

    def test_returns_identity_fields_only(self):
        self.repo.add_resume(_make_resume("Lena", "Lee", companies=["Acme"], skills=["Python"]))
        results = self.repo.list_resume_summaries(query="Lena").items
        self.assertEqual(len(results), 1)
        self.assertEqual(set(results[0].keys()), {"id", "first_name", "last_name", "email", "phone_num"})

    def test_multiple_results(self):
        resp_a = self.repo.add_resume(_make_resume("Mary", "Martin"))
        resp_b = self.repo.add_resume(_make_resume("Max", "Morris"))
        results = self.repo.list_resume_summaries(query="Ma").items
        self.assertEqual({r["id"] for r in results}, {resp_a.id, resp_b.id})

    def test_multi_token_and_both_in_same_field(self):
        # compound first name — both tokens in one field
        self.repo.add_resume(_make_resume("Mary Jane", "Watson"))
        results = self.repo.list_resume_summaries(query="Mary Jane").items
        self.assertEqual(len(results), 1)

    def test_multi_token_and_split_across_fields_no_match(self):
        # AND: "Hannah" in first_name but "Doe" in last_name — neither field holds both
        self.repo.add_resume(_make_resume("Hannah", "Doe"))
        results = self.repo.list_resume_summaries(query="Hannah Doe").items
        self.assertEqual(results, [])

    def test_multi_token_or_matches_first_name(self):
        self.repo.add_resume(_make_resume("Hannah", "Doe"))
        results = self.repo.list_resume_summaries(query="Hannah Zephyr", mode="or").items
        self.assertEqual(len(results), 1)

    def test_multi_token_or_no_match(self):
        self.repo.add_resume(_make_resume("Hannah", "Doe"))
        results = self.repo.list_resume_summaries(query="Zephyr Quantum", mode="or").items
        self.assertEqual(results, [])


# ── search_resumes_by_skill ───────────────────────────────────────────────────

class TestSearchResumesBySkill(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_returns_match(self):
        resp = self.repo.add_resume(_make_resume("Nina", "Nash", skills=["Python", "Go"]))
        results = self.repo.search_resumes_by_skill("Python").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], resp.id)
        self.assertIn("Python", results[0]["matched_skills"])

    def test_case_insensitive(self):
        self.repo.add_resume(_make_resume(skills=["TypeScript"]))
        self.assertEqual(len(self.repo.search_resumes_by_skill("typescript").items), 1)
        self.assertEqual(len(self.repo.search_resumes_by_skill("TYPESCRIPT").items), 1)

    def test_partial_match(self):
        resp_a = self.repo.add_resume(_make_resume("Oscar", "O", skills=["JavaScript"]))
        resp_b = self.repo.add_resume(_make_resume("Paula", "P", skills=["TypeScript"]))
        self.repo.add_resume(_make_resume("Quinn", "Q", skills=["Go"]))
        results = self.repo.search_resumes_by_skill("script").items
        self.assertEqual({r["id"] for r in results}, {resp_a.id, resp_b.id})

    def test_no_match(self):
        self.repo.add_resume(_make_resume(skills=["Python"]))
        self.assertEqual(self.repo.search_resumes_by_skill("COBOL").items, [])

    def test_excludes_non_matching_resumes(self):
        resp_a = self.repo.add_resume(_make_resume("Rose", "R", skills=["Rust"]))
        self.repo.add_resume(_make_resume("Sam", "S", skills=["Python"]))
        results = self.repo.search_resumes_by_skill("Rust").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], resp_a.id)

    def test_returns_minimal_fields(self):
        self.repo.add_resume(_make_resume("Tara", "T", skills=["Java"]))
        results = self.repo.search_resumes_by_skill("Java").items
        self.assertEqual(len(results), 1)
        self.assertEqual(set(results[0].keys()), {"id", "first_name", "last_name", "matched_skills"})

    def test_search_skills_alias(self):
        self.repo.add_resume(_make_resume(skills=["Python", "Go", "Rust"]))
        results = self.repo.list_badge_skills(query="py").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Python")

    def test_multi_token_and_full_phrase_match(self):
        resp = self.repo.add_resume(_make_resume(skills=["Machine Learning", "Python"]))
        results = self.repo.search_resumes_by_skill("Machine Learning").items
        self.assertEqual(len(results), 1)
        self.assertIn("Machine Learning", results[0]["matched_skills"])

    def test_multi_token_and_no_match_when_words_split(self):
        # "Machine" and "Learning" are separate skills — AND requires both in same skill title
        self.repo.add_resume(_make_resume(skills=["Machine", "Learning", "Python"]))
        results = self.repo.search_resumes_by_skill("Machine Learning", mode="and").items
        self.assertEqual(results, [])

    def test_multi_token_or_matches_either_skill(self):
        resp = self.repo.add_resume(_make_resume(skills=["Machine", "Python"]))
        results = self.repo.search_resumes_by_skill("Machine Learning", mode="or").items
        self.assertEqual(len(results), 1)
        self.assertIn("Machine", results[0]["matched_skills"])


# ── education ─────────────────────────────────────────────────────────────────

def _education(institution="University of Oregon", degree="BS Computer Science", year="2016", competencies=None):
    return EducationCreate(
        institution=institution, degree=degree, year=year,
        competencies=[BadgeSkillCreate(title=c) for c in (competencies or [])],
    )


class TestEducation(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_find_education(self):
        resp = self.repo.add_resume(_make_resume(education_entries=[_education(competencies=["Algorithms"])]))
        edu_id = resp.education_entries[0].id
        found = self.repo.find_education(edu_id)
        self.assertIsNotNone(found)
        self.assertEqual(found.institution, "University of Oregon")
        self.assertEqual([c.title for c in found.competencies], ["Algorithms"])

    def test_find_education_unknown_returns_none(self):
        self.assertIsNone(self.repo.find_education("bad-id"))

    def test_list_education_no_filter(self):
        self.repo.add_resume(_make_resume("Alice", "A", education_entries=[_education(institution="Reed College")]))
        self.repo.add_resume(_make_resume("Bob", "B", education_entries=[_education(institution="Lewis & Clark")]))
        results = self.repo.list_education()
        self.assertEqual(results.total_count, 2)

    def test_list_education_filtered_by_resume(self):
        resp_a = self.repo.add_resume(_make_resume("Alice", "A", education_entries=[_education(institution="Reed College")]))
        self.repo.add_resume(_make_resume("Bob", "B", education_entries=[_education(institution="Lewis & Clark")]))
        results = self.repo.list_education(resume_id=resp_a.id).items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["institution"], "Reed College")

    def test_list_education_unknown_resume_raises(self):
        with self.assertRaises(ValueError):
            self.repo.list_education(resume_id="bad-id")

    def test_search_education_by_institution(self):
        resp = self.repo.add_resume(_make_resume(education_entries=[_education(institution="University of Oregon")]))
        results = self.repo.list_education(query="Oregon").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["resume_id"], resp.id)

    def test_search_education_by_degree(self):
        self.repo.add_resume(_make_resume(education_entries=[_education(degree="MS Computer Science")]))
        results = self.repo.list_education(query="Computer Science").items
        self.assertEqual(len(results), 1)

    def test_search_education_by_competency(self):
        self.repo.add_resume(_make_resume(education_entries=[_education(competencies=["Algorithms"])]))
        results = self.repo.list_education(query="Algorithms").items
        self.assertEqual(len(results), 1)

    def test_search_education_scoped_by_resume(self):
        resp_a = self.repo.add_resume(_make_resume("Alice", "A", education_entries=[_education(institution="Reed College")]))
        resp_b = self.repo.add_resume(_make_resume("Bob", "B", education_entries=[_education(institution="Reed College")]))
        results = self.repo.list_education(query="Reed", resume_id=resp_a.id).items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["resume_id"], resp_a.id)
        self.assertNotEqual(results[0]["resume_id"], resp_b.id)

    def test_search_education_no_match(self):
        self.repo.add_resume(_make_resume(education_entries=[_education()]))
        self.assertEqual(self.repo.list_education(query="Nonexistent University").items, [])

    def test_search_education_by_competency_match(self):
        resp = self.repo.add_resume(_make_resume(education_entries=[_education(competencies=["Algorithms", "Databases"])]))
        results = self.repo.list_education(competency="Algorithms").items
        self.assertEqual(len(results), 1)
        self.assertIn("Algorithms", results[0]["matched_competencies"])
        self.assertEqual(results[0]["resume_id"], resp.id)

    def test_search_education_by_competency_partial_match(self):
        self.repo.add_resume(_make_resume(education_entries=[_education(competencies=["Operating Systems"])]))
        results = self.repo.list_education(competency="operating").items
        self.assertEqual(len(results), 1)

    def test_search_education_by_competency_no_match(self):
        self.repo.add_resume(_make_resume(education_entries=[_education(competencies=["Algorithms"])]))
        self.assertEqual(self.repo.list_education(competency="COBOL").items, [])

    def test_search_education_multi_token_and_in_degree(self):
        self.repo.add_resume(_make_resume(education_entries=[_education(degree="MS Computer Science")]))
        results = self.repo.list_education(query="Computer Science").items
        self.assertEqual(len(results), 1)

    def test_search_education_multi_token_and_one_missing(self):
        self.repo.add_resume(_make_resume(education_entries=[_education(institution="Portland State University")]))
        # "Portland" is there but "Community" is not
        results = self.repo.list_education(query="Portland Community").items
        self.assertEqual(results, [])

    def test_search_education_multi_token_or(self):
        self.repo.add_resume(_make_resume(education_entries=[_education(institution="Portland State University")]))
        results = self.repo.list_education(query="Portland Community", mode="or").items
        self.assertEqual(len(results), 1)

    def test_search_education_by_competency_multi_token_and_full_phrase(self):
        self.repo.add_resume(_make_resume(education_entries=[_education(competencies=["Machine Learning", "Databases"])]))
        results = self.repo.list_education(competency="Machine Learning").items
        self.assertEqual(len(results), 1)
        self.assertIn("Machine Learning", results[0]["matched_competencies"])

    def test_search_education_by_competency_multi_token_and_no_partial(self):
        # "Machine" and "Learning" are separate competencies — AND requires both in same title
        self.repo.add_resume(_make_resume(education_entries=[_education(competencies=["Machine", "Learning"])]))
        results = self.repo.list_education(competency="Machine Learning", mode="and").items
        self.assertEqual(results, [])

    def test_search_education_by_competency_multi_token_or(self):
        self.repo.add_resume(_make_resume(education_entries=[_education(competencies=["Machine", "Databases"])]))
        results = self.repo.list_education(competency="Machine Learning", mode="or").items
        self.assertEqual(len(results), 1)
        self.assertIn("Machine", results[0]["matched_competencies"])


# ── clear ─────────────────────────────────────────────────────────────────────

class TestClear(unittest.TestCase):
    def test_empties_all_stores(self):
        repo = ResumeRepository()
        repo.add_resume(_make_resume(
            companies=["Acme"], skills=["Python"], education_entries=[_education()],
            projects=[SideProjectCreate(name="Side Project", description="desc", technologies=[])],
        ))
        repo.clear()
        self.assertEqual(repo.list_resumes().items, [])
        self.assertEqual(repo.list_work_experiences().items, [])
        self.assertEqual(repo.list_achievements().items, [])
        self.assertEqual(repo.list_badge_skills().items, [])
        self.assertEqual(repo.list_side_projects().items, [])
        self.assertEqual(repo.list_education().items, [])
        self.assertEqual(repo._resumes, [])
        self.assertEqual(repo._work_experiences, [])
        self.assertEqual(repo._achievements, [])
        self.assertEqual(repo._badge_skills, [])
        self.assertEqual(repo._side_projects, [])
        self.assertEqual(repo._education, [])


# ── get_collection_stats ──────────────────────────────────────────────────────

class TestCollectionStats(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_empty_repo_returns_zeros(self):
        stats = self.repo.get_collection_stats()
        self.assertEqual(stats.total_resumes, 0)
        self.assertEqual(stats.total_work_experiences, 0)
        self.assertEqual(stats.total_unique_skills, 0)
        self.assertEqual(stats.total_side_projects, 0)
        self.assertEqual(stats.total_education_entries, 0)
        self.assertEqual(stats.total_achievements, 0)
        self.assertEqual(stats.avg_skills_per_resume, 0.0)
        self.assertEqual(stats.avg_work_experiences_per_resume, 0.0)

    def test_no_division_error_with_zero_resumes(self):
        # Must not raise
        stats = self.repo.get_collection_stats()
        self.assertIsInstance(stats.avg_skills_per_resume, float)

    def test_one_resume_no_skills(self):
        self.repo.add_resume(_make_resume())
        stats = self.repo.get_collection_stats()
        self.assertEqual(stats.total_resumes, 1)
        self.assertEqual(stats.avg_skills_per_resume, 0.0)
        self.assertEqual(stats.avg_work_experiences_per_resume, 0.0)

    def test_one_resume_with_three_skills(self):
        self.repo.add_resume(_make_resume(skills=["Python", "Go", "Rust"]))
        stats = self.repo.get_collection_stats()
        self.assertEqual(stats.total_unique_skills, 3)
        self.assertEqual(stats.avg_skills_per_resume, 3.0)

    def test_two_resumes_different_skill_counts(self):
        self.repo.add_resume(_make_resume("Alice", "A", skills=["Python", "Go"]))
        self.repo.add_resume(_make_resume("Bob", "B", skills=["Python", "Go", "Rust", "Java"]))
        stats = self.repo.get_collection_stats()
        self.assertEqual(stats.total_resumes, 2)
        self.assertEqual(stats.avg_skills_per_resume, 3.0)

    def test_fractional_average_rounds_to_two_dp(self):
        # 1 skill total across 3 resumes → avg = 0.33
        self.repo.add_resume(_make_resume("A", "A", skills=["Python"]))
        self.repo.add_resume(_make_resume("B", "B"))
        self.repo.add_resume(_make_resume("C", "C"))
        stats = self.repo.get_collection_stats()
        self.assertEqual(stats.avg_skills_per_resume, 0.33)

    def test_total_unique_skills_deduplicates(self):
        self.repo.add_resume(_make_resume("Alice", "A", skills=["Python", "Go"]))
        self.repo.add_resume(_make_resume("Bob", "B", skills=["Python", "Rust"]))
        stats = self.repo.get_collection_stats()
        self.assertEqual(stats.total_unique_skills, 3)  # Python, Go, Rust

    def test_total_work_experiences_is_global(self):
        self.repo.add_resume(_make_resume(companies=["Acme", "Globex"]))
        self.repo.add_resume(_make_resume(companies=["Initech"]))
        stats = self.repo.get_collection_stats()
        self.assertEqual(stats.total_work_experiences, 3)

    def test_total_achievements_is_global(self):
        # _make_resume adds 2 achievements per company
        self.repo.add_resume(_make_resume(companies=["Acme", "Globex"]))
        stats = self.repo.get_collection_stats()
        self.assertEqual(stats.total_achievements, 4)

    def test_all_eight_keys_present(self):
        stats = self.repo.get_collection_stats()
        d = stats.model_dump()
        expected_keys = {
            "total_resumes", "total_work_experiences", "total_unique_skills",
            "total_side_projects", "total_education_entries", "total_achievements",
            "avg_skills_per_resume", "avg_work_experiences_per_resume",
        }
        self.assertEqual(set(d.keys()), expected_keys)

    def test_avg_work_experiences_per_resume(self):
        self.repo.add_resume(_make_resume(companies=["Acme", "Globex"]))
        self.repo.add_resume(_make_resume(companies=["Initech"]))
        stats = self.repo.get_collection_stats()
        self.assertEqual(stats.avg_work_experiences_per_resume, 1.5)


# ── get_skill_frequency ───────────────────────────────────────────────────────

class TestSkillFrequency(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_empty_repo_returns_empty_list(self):
        self.assertEqual(self.repo.get_skill_frequency(), [])

    def test_single_resume_single_skill(self):
        self.repo.add_resume(_make_resume(skills=["Python"]))
        results = self.repo.get_skill_frequency()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].skill_title, "Python")
        self.assertEqual(results[0].resume_count, 1)

    def test_shared_skill_counts_correctly(self):
        self.repo.add_resume(_make_resume("Alice", "A", skills=["Python"]))
        self.repo.add_resume(_make_resume("Bob", "B", skills=["Python"]))
        results = self.repo.get_skill_frequency()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].resume_count, 2)

    def test_two_resumes_different_skills_each_count_one(self):
        self.repo.add_resume(_make_resume("Alice", "A", skills=["Python"]))
        self.repo.add_resume(_make_resume("Bob", "B", skills=["Go"]))
        results = self.repo.get_skill_frequency()
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.resume_count == 1 for r in results))

    def test_sorted_descending_by_count(self):
        self.repo.add_resume(_make_resume("Alice", "A", skills=["Python", "Go"]))
        self.repo.add_resume(_make_resume("Bob", "B", skills=["Python"]))
        self.repo.add_resume(_make_resume("Carol", "C", skills=["Python"]))
        results = self.repo.get_skill_frequency()
        self.assertEqual(results[0].skill_title, "Python")
        self.assertEqual(results[0].resume_count, 3)

    def test_limit_truncates_results(self):
        self.repo.add_resume(_make_resume(skills=["Python", "Go", "Rust", "Java"]))
        results = self.repo.get_skill_frequency(limit=2)
        self.assertEqual(len(results), 2)

    def test_limit_zero_returns_empty(self):
        self.repo.add_resume(_make_resume(skills=["Python"]))
        self.assertEqual(self.repo.get_skill_frequency(limit=0), [])

    def test_limit_larger_than_total_returns_all(self):
        self.repo.add_resume(_make_resume(skills=["Python", "Go"]))
        results = self.repo.get_skill_frequency(limit=100)
        self.assertEqual(len(results), 2)

    def test_result_items_have_required_fields(self):
        self.repo.add_resume(_make_resume(skills=["Python"]))
        item = self.repo.get_skill_frequency()[0]
        self.assertTrue(item.skill_id)
        self.assertEqual(item.skill_title, "Python")
        self.assertEqual(item.resume_count, 1)

    def test_skill_title_preserves_original_case(self):
        self.repo.add_resume(_make_resume(skills=["TypeScript"]))
        results = self.repo.get_skill_frequency()
        self.assertEqual(results[0].skill_title, "TypeScript")

    def test_three_resumes_two_share_top_skill(self):
        self.repo.add_resume(_make_resume("A", "A", skills=["Python", "Docker"]))
        self.repo.add_resume(_make_resume("B", "B", skills=["Python", "Kubernetes"]))
        self.repo.add_resume(_make_resume("C", "C", skills=["Rust"]))
        results = self.repo.get_skill_frequency()
        counts = {r.skill_title: r.resume_count for r in results}
        self.assertEqual(counts["Python"], 2)
        self.assertEqual(counts["Docker"], 1)
        self.assertEqual(counts["Kubernetes"], 1)
        self.assertEqual(counts["Rust"], 1)
        # Python must come first
        self.assertEqual(results[0].skill_title, "Python")


# ── search_resumes_by_skill (list form) ────────────────────────────────────────

class TestSearchResumesBySkillList(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_empty_skills_list_raises(self):
        self.repo.add_resume(_make_resume(skills=["Python"]))
        with self.assertRaises(ValueError):
            self.repo.search_resumes_by_skill([])

    def test_single_skill_same_as_string_form(self):
        resp = self.repo.add_resume(_make_resume("Nina", "Nash", skills=["Python", "Go"]))
        single = self.repo.search_resumes_by_skill("Python").items
        multi = self.repo.search_resumes_by_skill(["Python"]).items
        self.assertEqual({r["id"] for r in single}, {r["id"] for r in multi})

    def test_and_mode_requires_all_skills(self):
        resp_a = self.repo.add_resume(_make_resume("Alice", "A", skills=["Python", "Docker"]))
        self.repo.add_resume(_make_resume("Bob", "B", skills=["Python"]))
        results = self.repo.search_resumes_by_skill(["Python", "Docker"], mode="and").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], resp_a.id)

    def test_or_mode_requires_any_skill(self):
        resp_a = self.repo.add_resume(_make_resume("Alice", "A", skills=["Python"]))
        resp_b = self.repo.add_resume(_make_resume("Bob", "B", skills=["Docker"]))
        self.repo.add_resume(_make_resume("Carol", "C", skills=["Rust"]))
        results = self.repo.search_resumes_by_skill(["Python", "Docker"], mode="or").items
        self.assertEqual({r["id"] for r in results}, {resp_a.id, resp_b.id})

    def test_unknown_skill_returns_empty(self):
        self.repo.add_resume(_make_resume(skills=["Python"]))
        self.assertEqual(self.repo.search_resumes_by_skill(["COBOL"]).items, [])

    def test_and_mode_one_unknown_one_known_returns_empty(self):
        self.repo.add_resume(_make_resume(skills=["Python"]))
        self.assertEqual(self.repo.search_resumes_by_skill(["Python", "COBOL"], mode="and").items, [])

    def test_or_mode_one_unknown_one_known_returns_match(self):
        resp = self.repo.add_resume(_make_resume(skills=["Python"]))
        results = self.repo.search_resumes_by_skill(["Python", "COBOL"], mode="or").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], resp.id)

    def test_case_insensitive_match(self):
        resp = self.repo.add_resume(_make_resume(skills=["Python"]))
        results = self.repo.search_resumes_by_skill(["python"]).items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], resp.id)

    def test_partial_token_match(self):
        resp = self.repo.add_resume(_make_resume(skills=["Machine Learning"]))
        results = self.repo.search_resumes_by_skill(["machine learning"]).items
        self.assertEqual(len(results), 1)

    def test_partial_token_does_not_match_wrong_phrase(self):
        self.repo.add_resume(_make_resume(skills=["Machine Translation"]))
        # "machine learning" with AND requires both "machine" and "learning" in the skill title
        results = self.repo.search_resumes_by_skill(["machine learning"]).items
        self.assertEqual(results, [])

    def test_matched_skills_only_includes_matched(self):
        resp = self.repo.add_resume(_make_resume("Alice", "A", skills=["Python", "Docker", "Rust"]))
        results = self.repo.search_resumes_by_skill(["Python"], mode="and").items
        self.assertEqual(len(results), 1)
        self.assertIn("Python", results[0]["matched_skills"])
        self.assertNotIn("Docker", results[0]["matched_skills"])
        self.assertNotIn("Rust", results[0]["matched_skills"])

    def test_result_shape_matches_search_resumes_by_skill(self):
        self.repo.add_resume(_make_resume("Tara", "T", skills=["Java"]))
        results = self.repo.search_resumes_by_skill(["Java"]).items
        self.assertEqual(len(results), 1)
        self.assertEqual(set(results[0].keys()), {"id", "first_name", "last_name", "matched_skills"})

    def test_three_skills_and_all_required(self):
        resp = self.repo.add_resume(_make_resume(skills=["Python", "Docker", "Kubernetes"]))
        self.repo.add_resume(_make_resume(skills=["Python", "Docker"]))
        results = self.repo.search_resumes_by_skill(["Python", "Docker", "Kubernetes"], mode="and").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], resp.id)

    def test_and_mode_both_have_all_skills_both_returned(self):
        resp_a = self.repo.add_resume(_make_resume("Alice", "A", skills=["Python", "Docker"]))
        resp_b = self.repo.add_resume(_make_resume("Bob", "B", skills=["Python", "Docker"]))
        results = self.repo.search_resumes_by_skill(["Python", "Docker"], mode="and").items
        self.assertEqual({r["id"] for r in results}, {resp_a.id, resp_b.id})


# ── ranked resumes (ATS-style job-match scoring) ────────────────────────────────

class TestListRankedResumes(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_empty_job_description_raises(self):
        self.repo.add_resume(_make_resume(skills=["Python"]))
        with self.assertRaises(ValueError):
            self.repo.list_ranked_resumes("")

    def test_whitespace_job_description_raises(self):
        self.repo.add_resume(_make_resume(skills=["Python"]))
        with self.assertRaises(ValueError):
            self.repo.list_ranked_resumes("   \n\t  ")

    def test_out_of_range_threshold_raises(self):
        self.repo.add_resume(_make_resume(skills=["Python"]))
        with self.assertRaises(ValueError):
            self.repo.list_ranked_resumes("Python developer", skill_match_threshold=150)
        with self.assertRaises(ValueError):
            self.repo.list_ranked_resumes("Python developer", skill_match_threshold=-1)

    def test_negative_weights_raise(self):
        self.repo.add_resume(_make_resume(skills=["Python"]))
        with self.assertRaises(ValueError):
            self.repo.list_ranked_resumes("Python developer", skills_weight=-0.1)
        with self.assertRaises(ValueError):
            self.repo.list_ranked_resumes("Python developer", keyword_weight=-0.1)

    def test_zero_weight_sum_raises(self):
        self.repo.add_resume(_make_resume(skills=["Python"]))
        with self.assertRaises(ValueError):
            self.repo.list_ranked_resumes("Python developer", skills_weight=0, keyword_weight=0)

    def test_empty_collection_returns_empty_not_error(self):
        result = self.repo.list_ranked_resumes("Python developer")
        self.assertEqual(result.items, [])
        self.assertEqual(result.total_count, 0)

    def test_better_match_ranks_first(self):
        weak = self.repo.add_resume(_make_resume("Weak", "Match", skills=["Photoshop"]))
        strong = self.repo.add_resume(_make_resume(
            "Strong", "Match", skills=["Python", "Kubernetes", "Docker"],
        ))
        jd = "Looking for a backend engineer with Python, Kubernetes, and Docker experience."
        results = self.repo.list_ranked_resumes(jd).items
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], strong.id)
        self.assertEqual(results[1]["id"], weak.id)
        self.assertGreater(results[0]["overall_score"], results[1]["overall_score"])

    def test_result_shape(self):
        self.repo.add_resume(_make_resume(skills=["Python"]))
        results = self.repo.list_ranked_resumes("Python developer").items
        self.assertEqual(len(results), 1)
        self.assertEqual(
            set(results[0].keys()),
            {"id", "first_name", "last_name", "overall_score", "skills_score",
             "keyword_score", "matched_skills", "missing_skills"},
        )

    def test_matched_skills_reflects_job_description(self):
        self.repo.add_resume(_make_resume(skills=["Python", "Rust"]))
        results = self.repo.list_ranked_resumes("Seeking a Python expert").items
        self.assertIn("Python", results[0]["matched_skills"])
        self.assertNotIn("Rust", results[0]["matched_skills"])

    def test_missing_skills_reflects_uncovered_jd_terms(self):
        self.repo.add_resume(_make_resume(skills=["Python"]))
        results = self.repo.list_ranked_resumes(
            "Seeking a Python expert with strong Terraform experience"
        ).items
        self.assertTrue(any("terraform" in m for m in results[0]["missing_skills"]))

    def test_explicit_threshold_changes_fuzzy_match_outcome(self):
        # A near-miss typo (not an alias pair, so canonicalization doesn't force
        # an exact match) — loose threshold catches it, strict threshold doesn't.
        self.repo.add_resume(_make_resume(skills=["Snowflake"]))
        jd = "We use Snowflaek for our data warehouse."
        loose = self.repo.list_ranked_resumes(jd, skill_match_threshold=50).items
        strict = self.repo.list_ranked_resumes(jd, skill_match_threshold=95).items
        self.assertIn("Snowflake", loose[0]["matched_skills"])
        self.assertNotIn("Snowflake", strict[0]["matched_skills"])

    def test_explicit_weights_change_overall_score(self):
        self.repo.add_resume(_make_resume(skills=["Python"]))
        jd = "Python developer needed for an unrelated codebase full of other jargon."
        all_skills = self.repo.list_ranked_resumes(
            jd, skills_weight=1.0, keyword_weight=0.0,
        ).items[0]
        all_keywords = self.repo.list_ranked_resumes(
            jd, skills_weight=0.0, keyword_weight=1.0,
        ).items[0]
        self.assertEqual(all_skills["overall_score"], all_skills["skills_score"])
        self.assertEqual(all_keywords["overall_score"], all_keywords["keyword_score"])

    def test_pagination_applies_after_ranking(self):
        for i in range(5):
            self.repo.add_resume(_make_resume(f"Person{i}", "X", skills=["Python"]))
        page = self.repo.list_ranked_resumes("Python developer", limit=2, offset=0)
        self.assertEqual(len(page.items), 2)
        self.assertEqual(page.total_count, 5)
        self.assertTrue(page.has_more)


# ── pagination ────────────────────────────────────────────────────────────────

class TestPagination(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()
        # Add 3 resumes with work experiences, skills, side projects, education
        for name in ["Alice", "Bob", "Carol"]:
            self.repo.add_resume(_make_resume(
                first=name, last="X",
                skills=["Python"],
                companies=["Acme"],
                education_entries=[_education(institution=f"{name} University")],
                projects=[SideProjectCreate(name=f"{name} Project", description="desc", technologies=[])],
            ))

    def test_list_resumes_default_returns_all(self):
        result = self.repo.list_resumes()
        self.assertEqual(result.total_count, 3)
        self.assertEqual(len(result.items), 3)

    def test_list_resumes_limit_two(self):
        result = self.repo.list_resumes(limit=2)
        self.assertEqual(result.total_count, 3)
        self.assertEqual(len(result.items), 2)

    def test_list_resumes_offset_one(self):
        result = self.repo.list_resumes(limit=100, offset=1)
        self.assertEqual(result.total_count, 3)
        self.assertEqual(len(result.items), 2)

    def test_list_resumes_offset_beyond_end(self):
        result = self.repo.list_resumes(limit=100, offset=10)
        self.assertEqual(result.total_count, 3)
        self.assertEqual(result.items, [])

    def test_list_resumes_limit_zero_raises(self):
        with self.assertRaises(ValueError):
            self.repo.list_resumes(limit=0)

    def test_list_resumes_negative_limit_raises(self):
        with self.assertRaises(ValueError):
            self.repo.list_resumes(limit=-1)

    def test_list_resumes_negative_offset_raises(self):
        with self.assertRaises(ValueError):
            self.repo.list_resumes(offset=-1)

    def test_huge_limit_is_capped_at_max_page_limit(self):
        result = self.repo.list_resumes(limit=10_000)
        self.assertEqual(result.total_count, 3)
        self.assertLessEqual(len(result.items), 200)
        self.assertIn("capped to 200", result.message)

    def test_limit_at_cap_not_flagged_as_capped(self):
        result = self.repo.list_resumes(limit=200)
        self.assertNotIn("capped", result.message)

    def test_total_count_reflects_full_collection_not_slice(self):
        result = self.repo.list_resumes(limit=1, offset=0)
        self.assertEqual(result.total_count, 3)
        self.assertEqual(len(result.items), 1)

    def test_list_resume_summaries_pagination(self):
        result = self.repo.list_resume_summaries(limit=2, offset=1)
        self.assertEqual(result.total_count, 3)
        self.assertEqual(len(result.items), 2)

    def test_list_badge_skills_pagination(self):
        result = self.repo.list_badge_skills(limit=1, offset=0)
        self.assertEqual(result.total_count, 1)  # Python deduped across 3 resumes
        self.assertEqual(len(result.items), 1)

    def test_list_work_experiences_pagination(self):
        result = self.repo.list_work_experiences(limit=2)
        self.assertEqual(result.total_count, 3)
        self.assertEqual(len(result.items), 2)

    def test_list_work_experiences_with_resume_id_filter_and_pagination(self):
        resumes = self.repo.list_resume_summaries().items
        first_id = resumes[0]["id"]
        result = self.repo.list_work_experiences(resume_id=first_id, limit=10)
        self.assertEqual(result.total_count, 1)
        self.assertEqual(len(result.items), 1)

    def test_list_achievements_pagination(self):
        result = self.repo.list_achievements(limit=2)
        self.assertEqual(result.total_count, 6)  # 3 resumes × 2 achievements per company
        self.assertEqual(len(result.items), 2)

    def test_list_achievements_with_resume_id_filter_and_pagination(self):
        resumes = self.repo.list_resume_summaries().items
        first_id = resumes[0]["id"]
        result = self.repo.list_achievements(resume_id=first_id, limit=10)
        self.assertEqual(result.total_count, 2)

    def test_list_side_projects_pagination(self):
        result = self.repo.list_side_projects(limit=1)
        self.assertEqual(result.total_count, 3)
        self.assertEqual(len(result.items), 1)

    def test_list_education_pagination(self):
        result = self.repo.list_education(limit=2, offset=1)
        self.assertEqual(result.total_count, 3)
        self.assertEqual(len(result.items), 2)

    def test_response_has_expected_keys(self):
        result = self.repo.list_resumes()
        self.assertEqual(
            set(result.model_dump().keys()),
            {"total_count", "items", "has_more", "next_offset", "message"},
        )

    def test_empty_repo_pagination(self):
        repo = ResumeRepository()
        result = repo.list_resumes(limit=10, offset=0)
        self.assertEqual(result.total_count, 0)
        self.assertEqual(result.items, [])

    def test_limit_2_offset_2_with_3_items_returns_one(self):
        result = self.repo.list_resumes(limit=2, offset=2)
        self.assertEqual(result.total_count, 3)
        self.assertEqual(len(result.items), 1)

    def test_has_more_true_on_middle_page(self):
        result = self.repo.list_resumes(limit=2, offset=0)
        self.assertTrue(result.has_more)
        self.assertEqual(result.next_offset, 2)
        self.assertIn("Call again with offset=2", result.message)

    def test_has_more_false_on_last_page(self):
        result = self.repo.list_resumes(limit=100, offset=0)
        self.assertFalse(result.has_more)
        self.assertIsNone(result.next_offset)
        self.assertEqual(result.message, "All 3 results shown.")

    def test_has_more_false_when_offset_beyond_end(self):
        result = self.repo.list_resumes(limit=100, offset=10)
        self.assertFalse(result.has_more)
        self.assertIsNone(result.next_offset)


# ── _make_matcher regex mode ──────────────────────────────────────────────────

class TestMakeMatcherRegexMode(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_regex_mode_matches_alternation(self):
        self.repo.add_resume(_make_resume(skills=["Eng", "Rust"]))
        results = self.repo.list_badge_skills(query=r"^eng(ineer)?$", mode="regex").items
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Eng")

    def test_regex_mode_is_case_insensitive(self):
        self.repo.add_resume(_make_resume(skills=["Python"]))
        results = self.repo.list_badge_skills(query=r"PY.*ON", mode="regex").items
        self.assertEqual(len(results), 1)

    def test_regex_mode_no_match_returns_empty(self):
        self.repo.add_resume(_make_resume(skills=["Python"]))
        results = self.repo.list_badge_skills(query=r"^cobol$", mode="regex").items
        self.assertEqual(results, [])

    def test_invalid_regex_raises_value_error(self):
        self.repo.add_resume(_make_resume(skills=["Python"]))
        with self.assertRaises(ValueError):
            self.repo.list_badge_skills(query="(", mode="regex")

    def test_and_or_mode_still_tokenizes_and_escapes(self):
        # Regex-special characters in an "and"/"or" query are treated literally
        self.repo.add_resume(_make_resume(skills=["C++"]))
        results = self.repo.list_badge_skills(query="C++").items
        self.assertEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main()
