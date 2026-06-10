from __future__ import annotations

import unittest

from resume_mcp_server.models import (
    AchievementCreate,
    BadgeSkillCreate,
    EducationCreate,
    ResumeCreate,
    WorkExperienceCreate,
)
from resume_mcp_server.repository import ResumeRepository


def _make_resume(
    first: str = "Jane",
    last: str = "Doe",
    skills: list[str] | None = None,
    companies: list[str] | None = None,
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
        badge_skills=[],
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
        self.assertEqual(len(self.repo.list_resumes()), 2)


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
        self.assertEqual([s.title for s in self.repo.list_badge_skills(resume_id=resp_a.id)], ["Python", "Rust", "Go"])
        self.assertEqual([s.title for s in self.repo.list_badge_skills(resume_id=resp_b.id)], ["Go", "Python"])

    def test_list_unknown_resume_returns_empty(self):
        self.assertEqual(self.repo.list_badge_skills(resume_id="bad-id"), [])


# ── work experience ordering ──────────────────────────────────────────────────

class TestWorkExperienceOrdering(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_order_preserved(self):
        resp = self.repo.add_resume(_make_resume(companies=["Acme", "Globex", "Initech"]))
        self.assertEqual([w.company_name for w in resp.work_experiences], ["Acme", "Globex", "Initech"])

    def test_list_filtered_preserves_order(self):
        resp = self.repo.add_resume(_make_resume(companies=["Acme", "Globex", "Initech"]))
        wes = self.repo.list_work_experiences(resume_id=resp.id)
        self.assertEqual([w.company_name for w in wes], ["Acme", "Globex", "Initech"])

    def test_list_unknown_resume_returns_empty(self):
        self.assertEqual(self.repo.list_work_experiences(resume_id="bad-id"), [])


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
            education="", work_experiences=[we], badge_skills=[],
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
        self.assertEqual(len(self.repo.list_achievements()), 4)

    def test_list_filtered_by_resume(self):
        resp_a = self.repo.add_resume(_make_resume(companies=["Acme"]))
        self.repo.add_resume(_make_resume(companies=["Globex"]))
        achs = self.repo.list_achievements(resume_id=resp_a.id)
        self.assertEqual(len(achs), 2)
        self.assertTrue(all("Acme" in a.desc for a in achs))

    def test_list_unknown_resume_returns_empty(self):
        self.assertEqual(self.repo.list_achievements(resume_id="bad-id"), [])


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
        results = self.repo.search_badge_skills("python")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Python")

    def test_case_insensitive(self):
        self.repo.add_resume(_make_resume(skills=["TypeScript"]))
        self.assertEqual(len(self.repo.search_badge_skills("typescript")), 1)
        self.assertEqual(len(self.repo.search_badge_skills("TYPESCRIPT")), 1)

    def test_no_match(self):
        self.assertEqual(self.repo.search_badge_skills("Java"), [])

    def test_partial_match(self):
        repo = ResumeRepository()
        repo.add_resume(_make_resume(skills=["JavaScript", "TypeScript", "Go"]))
        results = repo.search_badge_skills("script")
        self.assertEqual({s.title for s in results}, {"JavaScript", "TypeScript"})


# ── search_work_experiences ───────────────────────────────────────────────────

class TestSearchWorkExperiences(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_by_company(self):
        resp = self.repo.add_resume(_make_resume(companies=["Acme", "Globex"]))
        results = self.repo.search_work_experiences("Acme")
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
            education="", work_experiences=[we], badge_skills=[],
        )
        resp = self.repo.add_resume(resume)
        results = self.repo.search_work_experiences("Senior")
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
            education="", work_experiences=[we], badge_skills=[],
        )
        resp = self.repo.add_resume(resume)
        results = self.repo.search_work_experiences("latency")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["resume_id"], resp.id)
        self.assertTrue(any(a["desc"] == "Reduced latency by 40%" for a in results[0]["achievements"]))

    def test_no_match(self):
        self.repo.add_resume(_make_resume(companies=["Acme"]))
        self.assertEqual(self.repo.search_work_experiences("Nonexistent Corp"), [])

    def test_resume_id_present(self):
        resp_a = self.repo.add_resume(_make_resume("Alice", "A", companies=["Alpha Corp"]))
        resp_b = self.repo.add_resume(_make_resume("Bob", "B", companies=["Beta Corp"]))
        results = self.repo.search_work_experiences("Corp")
        resume_ids = {r["resume_id"] for r in results}
        self.assertEqual(resume_ids, {resp_a.id, resp_b.id})

    def test_does_not_mix_jobs(self):
        resp_a = self.repo.add_resume(_make_resume("Alice", "A", companies=["Acme"]))
        resp_b = self.repo.add_resume(_make_resume("Bob", "B", companies=["Acme"]))
        results = self.repo.search_work_experiences("Acme")
        self.assertEqual(len(results), 2)
        self.assertNotEqual(results[0]["resume_id"], results[1]["resume_id"])
        self.assertEqual({r["resume_id"] for r in results}, {resp_a.id, resp_b.id})

    def test_search_work_experiences_includes_resume_id_in_each_result(self):
        self.repo.add_resume(_make_resume(companies=["Acme", "Globex"]))
        results = self.repo.search_work_experiences("Engineer")
        self.assertTrue(all("resume_id" in r for r in results))


# ── list_resume_summaries ─────────────────────────────────────────────────────

class TestListResumeSummaries(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_returns_identity_fields_only(self):
        self.repo.add_resume(_make_resume("Alice", "Adams", companies=["Acme"], skills=["Python"]))
        summaries = self.repo.list_resume_summaries()
        self.assertEqual(len(summaries), 1)
        s = summaries[0]
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
        self.assertEqual(len(self.repo.list_resume_summaries()), 2)

    def test_empty(self):
        self.assertEqual(self.repo.list_resume_summaries(), [])


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
        results = self.repo.list_work_experiences(current_only=True)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].company_name, "CurrentCo")

    def test_false_returns_all(self):
        self.repo.add_resume(_make_resume_mixed_dates())
        self.assertEqual(len(self.repo.list_work_experiences(current_only=False)), 2)

    def test_with_resume_id(self):
        resp_a = self.repo.add_resume(_make_resume_mixed_dates("Alice", "A"))
        self.repo.add_resume(_make_resume_mixed_dates("Bob", "B"))
        results = self.repo.list_work_experiences(resume_id=resp_a.id, current_only=True)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].company_name, "CurrentCo")

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
            badge_skills=[],
        ))
        results = self.repo.list_work_experiences(current_only=True)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].company_name, "NowCo")

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
            badge_skills=[],
        ))
        self.assertEqual(self.repo.list_work_experiences(current_only=True), [])


# ── search_achievements ───────────────────────────────────────────────────────

class TestSearchAchievements(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_returns_match(self):
        resp = self.repo.add_resume(_make_resume(companies=["Acme"]))
        results = self.repo.search_achievements("great")
        self.assertEqual(len(results), 1)
        self.assertIn("great", results[0]["desc"])
        self.assertEqual(results[0]["company_name"], "Acme")
        self.assertEqual(results[0]["resume_id"], resp.id)

    def test_includes_parent_context(self):
        resp = self.repo.add_resume(_make_resume(companies=["Globex"]))
        results = self.repo.search_achievements("Globex")
        self.assertTrue(results)
        r = results[0]
        self.assertIn("company_name", r)
        self.assertIn("position_title", r)
        self.assertIn("work_experience_id", r)
        self.assertIn("resume_id", r)
        self.assertEqual(r["resume_id"], resp.id)

    def test_case_insensitive(self):
        self.repo.add_resume(_make_resume(companies=["Acme"]))
        self.assertEqual(len(self.repo.search_achievements("GREAT")), 1)
        self.assertEqual(len(self.repo.search_achievements("Great")), 1)

    def test_no_match(self):
        self.repo.add_resume(_make_resume(companies=["Acme"]))
        self.assertEqual(self.repo.search_achievements("quantum entanglement"), [])

    def test_scoped_by_resume_id(self):
        resp_a = self.repo.add_resume(_make_resume("Alice", "A", companies=["Alpha"]))
        self.repo.add_resume(_make_resume("Bob", "B", companies=["Beta"]))
        results = self.repo.search_achievements("great", resume_id=resp_a.id)
        self.assertTrue(all(r["resume_id"] == resp_a.id for r in results))
        self.assertTrue(all(r["company_name"] == "Alpha" for r in results))

    def test_scope_wrong_resume_returns_empty(self):
        resp_a = self.repo.add_resume(_make_resume("Alice", "A", companies=["Alpha"]))
        resp_b = self.repo.add_resume(_make_resume("Bob", "B", companies=["Beta"]))
        results = self.repo.search_achievements("Alpha", resume_id=resp_b.id)
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
            badge_skills=[],
        ))
        results = self.repo.search_achievements("latency")
        self.assertEqual(len(results), 1)
        self.assertIn("latency", results[0]["desc"])


# ── search_resumes_by_name ────────────────────────────────────────────────────

class TestSearchResumesByName(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_first_name(self):
        resp = self.repo.add_resume(_make_resume("Hannah", "Hill"))
        results = self.repo.search_resumes_by_name("Hannah")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], resp.id)

    def test_last_name(self):
        resp = self.repo.add_resume(_make_resume("Hannah", "Hill"))
        results = self.repo.search_resumes_by_name("Hill")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], resp.id)

    def test_case_insensitive(self):
        self.repo.add_resume(_make_resume("Ivan", "Ivanov"))
        self.assertEqual(len(self.repo.search_resumes_by_name("ivan")), 1)
        self.assertEqual(len(self.repo.search_resumes_by_name("IVANOV")), 1)

    def test_partial_match(self):
        self.repo.add_resume(_make_resume("Julia", "Jones"))
        self.assertEqual(len(self.repo.search_resumes_by_name("Jul")), 1)

    def test_no_match(self):
        self.repo.add_resume(_make_resume("Karl", "King"))
        self.assertEqual(self.repo.search_resumes_by_name("Zephyr"), [])

    def test_returns_identity_fields_only(self):
        self.repo.add_resume(_make_resume("Lena", "Lee", companies=["Acme"], skills=["Python"]))
        results = self.repo.search_resumes_by_name("Lena")
        self.assertEqual(len(results), 1)
        self.assertEqual(set(results[0].keys()), {"id", "first_name", "last_name", "email", "phone_num"})

    def test_multiple_results(self):
        resp_a = self.repo.add_resume(_make_resume("Mary", "Martin"))
        resp_b = self.repo.add_resume(_make_resume("Max", "Morris"))
        results = self.repo.search_resumes_by_name("Ma")
        self.assertEqual({r["id"] for r in results}, {resp_a.id, resp_b.id})


# ── search_resumes_by_skill ───────────────────────────────────────────────────

class TestSearchResumesBySkill(unittest.TestCase):
    def setUp(self):
        self.repo = ResumeRepository()

    def test_returns_match(self):
        resp = self.repo.add_resume(_make_resume("Nina", "Nash", skills=["Python", "Go"]))
        results = self.repo.search_resumes_by_skill("Python")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], resp.id)
        self.assertIn("Python", results[0]["matched_skills"])

    def test_case_insensitive(self):
        self.repo.add_resume(_make_resume(skills=["TypeScript"]))
        self.assertEqual(len(self.repo.search_resumes_by_skill("typescript")), 1)
        self.assertEqual(len(self.repo.search_resumes_by_skill("TYPESCRIPT")), 1)

    def test_partial_match(self):
        resp_a = self.repo.add_resume(_make_resume("Oscar", "O", skills=["JavaScript"]))
        resp_b = self.repo.add_resume(_make_resume("Paula", "P", skills=["TypeScript"]))
        self.repo.add_resume(_make_resume("Quinn", "Q", skills=["Go"]))
        results = self.repo.search_resumes_by_skill("script")
        self.assertEqual({r["id"] for r in results}, {resp_a.id, resp_b.id})

    def test_no_match(self):
        self.repo.add_resume(_make_resume(skills=["Python"]))
        self.assertEqual(self.repo.search_resumes_by_skill("COBOL"), [])

    def test_excludes_non_matching_resumes(self):
        resp_a = self.repo.add_resume(_make_resume("Rose", "R", skills=["Rust"]))
        self.repo.add_resume(_make_resume("Sam", "S", skills=["Python"]))
        results = self.repo.search_resumes_by_skill("Rust")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], resp_a.id)

    def test_returns_minimal_fields(self):
        self.repo.add_resume(_make_resume("Tara", "T", skills=["Java"]))
        results = self.repo.search_resumes_by_skill("Java")
        self.assertEqual(len(results), 1)
        self.assertEqual(set(results[0].keys()), {"id", "first_name", "last_name", "matched_skills"})

    def test_search_skills_alias(self):
        self.repo.add_resume(_make_resume(skills=["Python", "Go", "Rust"]))
        results = self.repo.search_badge_skills("py")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Python")


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
        self.assertEqual(len(results), 2)

    def test_list_education_filtered_by_resume(self):
        resp_a = self.repo.add_resume(_make_resume("Alice", "A", education_entries=[_education(institution="Reed College")]))
        self.repo.add_resume(_make_resume("Bob", "B", education_entries=[_education(institution="Lewis & Clark")]))
        results = self.repo.list_education(resume_id=resp_a.id)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].institution, "Reed College")

    def test_list_education_unknown_resume_returns_empty(self):
        self.assertEqual(self.repo.list_education(resume_id="bad-id"), [])

    def test_search_education_by_institution(self):
        resp = self.repo.add_resume(_make_resume(education_entries=[_education(institution="University of Oregon")]))
        results = self.repo.search_education("Oregon")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["resume_id"], resp.id)

    def test_search_education_by_degree(self):
        self.repo.add_resume(_make_resume(education_entries=[_education(degree="MS Computer Science")]))
        results = self.repo.search_education("Computer Science")
        self.assertEqual(len(results), 1)

    def test_search_education_by_competency(self):
        self.repo.add_resume(_make_resume(education_entries=[_education(competencies=["Algorithms"])]))
        results = self.repo.search_education("Algorithms")
        self.assertEqual(len(results), 1)

    def test_search_education_scoped_by_resume(self):
        resp_a = self.repo.add_resume(_make_resume("Alice", "A", education_entries=[_education(institution="Reed College")]))
        resp_b = self.repo.add_resume(_make_resume("Bob", "B", education_entries=[_education(institution="Reed College")]))
        results = self.repo.search_education("Reed", resume_id=resp_a.id)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["resume_id"], resp_a.id)
        self.assertNotEqual(results[0]["resume_id"], resp_b.id)

    def test_search_education_no_match(self):
        self.repo.add_resume(_make_resume(education_entries=[_education()]))
        self.assertEqual(self.repo.search_education("Nonexistent University"), [])

    def test_search_education_by_competency_match(self):
        resp = self.repo.add_resume(_make_resume(education_entries=[_education(competencies=["Algorithms", "Databases"])]))
        results = self.repo.search_education_by_competency("Algorithms")
        self.assertEqual(len(results), 1)
        self.assertIn("Algorithms", results[0]["matched_competencies"])
        self.assertEqual(results[0]["resume_id"], resp.id)

    def test_search_education_by_competency_partial_match(self):
        self.repo.add_resume(_make_resume(education_entries=[_education(competencies=["Operating Systems"])]))
        results = self.repo.search_education_by_competency("operating")
        self.assertEqual(len(results), 1)

    def test_search_education_by_competency_no_match(self):
        self.repo.add_resume(_make_resume(education_entries=[_education(competencies=["Algorithms"])]))
        self.assertEqual(self.repo.search_education_by_competency("COBOL"), [])


# ── clear ─────────────────────────────────────────────────────────────────────

class TestClear(unittest.TestCase):
    def test_empties_all_stores(self):
        repo = ResumeRepository()
        repo.add_resume(_make_resume(companies=["Acme"], skills=["Python"], education_entries=[_education()]))
        repo.clear()
        self.assertEqual(repo.list_resumes(), [])
        self.assertEqual(repo.list_work_experiences(), [])
        self.assertEqual(repo.list_achievements(), [])
        self.assertEqual(repo.list_badge_skills(), [])
        self.assertEqual(repo.list_education(), [])
        self.assertEqual(repo._resumes, [])
        self.assertEqual(repo._work_experiences, [])
        self.assertEqual(repo._achievements, [])
        self.assertEqual(repo._badge_skills, [])
        self.assertEqual(repo._education, [])


if __name__ == "__main__":
    unittest.main()
