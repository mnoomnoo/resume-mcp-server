from __future__ import annotations

import pytest
from resume_mcp_server.models import (
    AchievementCreate,
    BadgeSkillCreate,
    ResumeCreate,
    WorkExperienceCreate,
)
from resume_mcp_server.repository import ResumeRepository


def _make_resume(
    first: str = "Jane",
    last: str = "Doe",
    skills: list[str] | None = None,
    companies: list[str] | None = None,
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
    )


# ── add + retrieve ────────────────────────────────────────────────────────────

def test_add_resume_returns_response_with_id():
    repo = ResumeRepository()
    resp = repo.add_resume(_make_resume())
    assert resp.id
    assert resp.first_name == "Jane"
    assert resp.last_name == "Doe"


def test_find_resume_roundtrip():
    repo = ResumeRepository()
    resp = repo.add_resume(_make_resume())
    found = repo.find_resume(resp.id)
    assert found is not None
    assert found.id == resp.id
    assert found.email == resp.email


def test_find_resume_unknown_returns_none():
    repo = ResumeRepository()
    assert repo.find_resume("nonexistent") is None


def test_list_resumes_length():
    repo = ResumeRepository()
    repo.add_resume(_make_resume("Alice", "A"))
    repo.add_resume(_make_resume("Bob", "B"))
    assert len(repo.list_resumes()) == 2


# ── badge skill ordering (the shared-skill bug) ───────────────────────────────

def test_badge_skill_order_preserved_per_resume():
    repo = ResumeRepository()
    resp_a = repo.add_resume(_make_resume(skills=["Python", "Rust", "Go"]))
    resp_b = repo.add_resume(_make_resume(skills=["Go", "Python"]))

    # Resume A: Python first, then Rust, then Go
    assert [s.title for s in resp_a.badge_skills] == ["Python", "Rust", "Go"]

    # Resume B: Go first, then Python — NOT the global insertion order
    assert [s.title for s in resp_b.badge_skills] == ["Go", "Python"]


def test_badge_skill_deduplication():
    repo = ResumeRepository()
    repo.add_resume(_make_resume(skills=["Python", "Rust", "Go"]))
    repo.add_resume(_make_resume(skills=["Go", "Python"]))
    # Only 3 unique skills stored
    assert len(repo._badge_skills) == 3


def test_list_badge_skills_filtered_by_resume_preserves_order():
    repo = ResumeRepository()
    resp_a = repo.add_resume(_make_resume(skills=["Python", "Rust", "Go"]))
    resp_b = repo.add_resume(_make_resume(skills=["Go", "Python"]))

    skills_a = repo.list_badge_skills(resume_id=resp_a.id)
    assert [s.title for s in skills_a] == ["Python", "Rust", "Go"]

    skills_b = repo.list_badge_skills(resume_id=resp_b.id)
    assert [s.title for s in skills_b] == ["Go", "Python"]


def test_list_badge_skills_unknown_resume_returns_empty():
    repo = ResumeRepository()
    assert repo.list_badge_skills(resume_id="bad-id") == []


# ── work experience ordering ──────────────────────────────────────────────────

def test_work_experience_order_preserved():
    repo = ResumeRepository()
    resp = repo.add_resume(_make_resume(companies=["Acme", "Globex", "Initech"]))
    names = [w.company_name for w in resp.work_experiences]
    assert names == ["Acme", "Globex", "Initech"]


def test_list_work_experiences_filtered_preserves_order():
    repo = ResumeRepository()
    resp = repo.add_resume(_make_resume(companies=["Acme", "Globex", "Initech"]))
    wes = repo.list_work_experiences(resume_id=resp.id)
    assert [w.company_name for w in wes] == ["Acme", "Globex", "Initech"]


def test_list_work_experiences_unknown_resume_returns_empty():
    repo = ResumeRepository()
    assert repo.list_work_experiences(resume_id="bad-id") == []


# ── achievement ordering ──────────────────────────────────────────────────────

def test_achievement_order_preserved_in_work_experience():
    repo = ResumeRepository()
    we = WorkExperienceCreate(
        company_name="Acme",
        position_title="Engineer",
        start_date="Jan 2020",
        end_date="Present",
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
    resp = repo.add_resume(resume)
    descs = [a.desc for a in resp.work_experiences[0].achievements]
    assert descs == [
        "First achievement at Acme",
        "Second achievement at Acme",
        "Third achievement at Acme",
    ]


# ── list_achievements ─────────────────────────────────────────────────────────

def test_list_achievements_all():
    repo = ResumeRepository()
    repo.add_resume(_make_resume(companies=["Acme", "Globex"]))
    # 2 companies × 2 achievements each = 4
    assert len(repo.list_achievements()) == 4


def test_list_achievements_filtered_by_resume():
    repo = ResumeRepository()
    resp_a = repo.add_resume(_make_resume(companies=["Acme"]))
    repo.add_resume(_make_resume(companies=["Globex"]))
    achs = repo.list_achievements(resume_id=resp_a.id)
    assert len(achs) == 2
    assert all("Acme" in a.desc for a in achs)


def test_list_achievements_unknown_resume_returns_empty():
    repo = ResumeRepository()
    assert repo.list_achievements(resume_id="bad-id") == []


# ── find helpers ──────────────────────────────────────────────────────────────

def test_find_work_experience():
    repo = ResumeRepository()
    resp = repo.add_resume(_make_resume(companies=["Acme"]))
    we_id = resp.work_experiences[0].id
    found = repo.find_work_experience(we_id)
    assert found is not None
    assert found.company_name == "Acme"


def test_find_work_experience_unknown_returns_none():
    repo = ResumeRepository()
    assert repo.find_work_experience("bad-id") is None


def test_find_achievement():
    repo = ResumeRepository()
    resp = repo.add_resume(_make_resume(companies=["Acme"]))
    ach_id = resp.work_experiences[0].achievements[0].id
    found = repo.find_achievement(ach_id)
    assert found is not None
    assert "Acme" in found.desc


def test_find_achievement_unknown_returns_none():
    repo = ResumeRepository()
    assert repo.find_achievement("bad-id") is None


def test_find_badge_skill():
    repo = ResumeRepository()
    resp = repo.add_resume(_make_resume(skills=["Python"]))
    skill_id = resp.badge_skills[0].id
    found = repo.find_badge_skill(skill_id)
    assert found is not None
    assert found.title == "Python"


def test_find_badge_skill_unknown_returns_none():
    repo = ResumeRepository()
    assert repo.find_badge_skill("bad-id") is None


# ── search_badge_skills ───────────────────────────────────────────────────────

def test_search_badge_skills_returns_match():
    repo = ResumeRepository()
    repo.add_resume(_make_resume(skills=["Python", "Go", "Rust"]))
    results = repo.search_badge_skills("python")
    assert len(results) == 1
    assert results[0].title == "Python"


def test_search_badge_skills_case_insensitive():
    repo = ResumeRepository()
    repo.add_resume(_make_resume(skills=["TypeScript"]))
    assert len(repo.search_badge_skills("typescript")) == 1
    assert len(repo.search_badge_skills("TYPESCRIPT")) == 1


def test_search_badge_skills_no_match():
    repo = ResumeRepository()
    repo.add_resume(_make_resume(skills=["Python"]))
    assert repo.search_badge_skills("Java") == []


def test_search_badge_skills_partial_match():
    repo = ResumeRepository()
    repo.add_resume(_make_resume(skills=["JavaScript", "TypeScript", "Go"]))
    results = repo.search_badge_skills("script")
    assert {s.title for s in results} == {"JavaScript", "TypeScript"}


# ── search_work_experiences ───────────────────────────────────────────────────

def test_search_work_experiences_by_company():
    repo = ResumeRepository()
    resp = repo.add_resume(_make_resume(companies=["Acme", "Globex"]))
    results = repo.search_work_experiences("Acme")
    assert len(results) == 1
    assert results[0]["company_name"] == "Acme"
    assert results[0]["resume_id"] == resp.id


def test_search_work_experiences_by_position():
    repo = ResumeRepository()
    we = WorkExperienceCreate(
        company_name="Initech",
        position_title="Senior Software Engineer",
        start_date="Jan 2022",
        end_date="Present",
        achievements=[AchievementCreate(desc="Built pipelines")],
    )
    resume = ResumeCreate(
        first_name="Jane", last_name="Doe",
        email="jane@example.com", phone_num="555-555-5555",
        address="Portland, OR", professional_statement="",
        education="", work_experiences=[we], badge_skills=[],
    )
    resp = repo.add_resume(resume)
    results = repo.search_work_experiences("Senior")
    assert len(results) == 1
    assert results[0]["position_title"] == "Senior Software Engineer"
    assert results[0]["resume_id"] == resp.id


def test_search_work_experiences_by_achievement():
    repo = ResumeRepository()
    we = WorkExperienceCreate(
        company_name="Vandelay",
        position_title="Engineer",
        start_date="Jan 2021",
        end_date="Dec 2023",
        achievements=[AchievementCreate(desc="Reduced latency by 40%")],
    )
    resume = ResumeCreate(
        first_name="Art", last_name="Vandelay",
        email="art@example.com", phone_num="555-555-5555",
        address="New York, NY", professional_statement="",
        education="", work_experiences=[we], badge_skills=[],
    )
    resp = repo.add_resume(resume)
    results = repo.search_work_experiences("latency")
    assert len(results) == 1
    assert results[0]["resume_id"] == resp.id
    assert any(a["desc"] == "Reduced latency by 40%" for a in results[0]["achievements"])


def test_search_work_experiences_no_match():
    repo = ResumeRepository()
    repo.add_resume(_make_resume(companies=["Acme"]))
    assert repo.search_work_experiences("Nonexistent Corp") == []


def test_search_work_experiences_resume_id_present():
    repo = ResumeRepository()
    resp_a = repo.add_resume(_make_resume("Alice", "A", companies=["Alpha Corp"]))
    resp_b = repo.add_resume(_make_resume("Bob", "B", companies=["Beta Corp"]))
    results = repo.search_work_experiences("Corp")
    resume_ids = {r["resume_id"] for r in results}
    assert resume_ids == {resp_a.id, resp_b.id}


def test_search_work_experiences_does_not_mix_jobs():
    repo = ResumeRepository()
    resp_a = repo.add_resume(_make_resume("Alice", "A", companies=["Acme"]))
    resp_b = repo.add_resume(_make_resume("Bob", "B", companies=["Acme"]))
    results = repo.search_work_experiences("Acme")
    # Both resumes have an Acme entry — they should appear as separate results
    assert len(results) == 2
    assert results[0]["resume_id"] != results[1]["resume_id"]
    assert {r["resume_id"] for r in results} == {resp_a.id, resp_b.id}


# ── list_resume_summaries ─────────────────────────────────────────────────────

def test_list_resume_summaries_returns_identity_fields_only():
    repo = ResumeRepository()
    repo.add_resume(_make_resume("Alice", "Adams", companies=["Acme"], skills=["Python"]))
    summaries = repo.list_resume_summaries()
    assert len(summaries) == 1
    s = summaries[0]
    assert s["first_name"] == "Alice"
    assert s["last_name"] == "Adams"
    assert "work_experiences" not in s
    assert "badge_skills" not in s
    assert "professional_statement" not in s
    assert "id" in s and "email" in s and "phone_num" in s


def test_list_resume_summaries_multiple():
    repo = ResumeRepository()
    repo.add_resume(_make_resume("Alice", "A"))
    repo.add_resume(_make_resume("Bob", "B"))
    assert len(repo.list_resume_summaries()) == 2


def test_list_resume_summaries_empty():
    repo = ResumeRepository()
    assert repo.list_resume_summaries() == []


# ── get_resume_profile ────────────────────────────────────────────────────────

def test_get_resume_profile_returns_top_level_fields():
    repo = ResumeRepository()
    resp = repo.add_resume(_make_resume("Carol", "Chen", companies=["Initech"], skills=["Go"]))
    profile = repo.get_resume_profile(resp.id)
    assert profile is not None
    assert profile["first_name"] == "Carol"
    assert profile["last_name"] == "Chen"
    assert profile["professional_statement"] == "Experienced engineer"
    assert profile["education"] == "BS Computer Science"
    assert "work_experiences" not in profile
    assert "badge_skills" not in profile


def test_get_resume_profile_unknown_returns_none():
    repo = ResumeRepository()
    assert repo.get_resume_profile("no-such-id") is None


def test_get_resume_profile_id_matches_resume():
    repo = ResumeRepository()
    resp = repo.add_resume(_make_resume("Dana", "Davis"))
    profile = repo.get_resume_profile(resp.id)
    assert profile["id"] == resp.id


# ── list_work_experiences current_only ────────────────────────────────────────

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


def test_list_work_experiences_current_only_filters_past_jobs():
    repo = ResumeRepository()
    repo.add_resume(_make_resume_mixed_dates())
    results = repo.list_work_experiences(current_only=True)
    assert len(results) == 1
    assert results[0].company_name == "CurrentCo"


def test_list_work_experiences_current_only_false_returns_all():
    repo = ResumeRepository()
    repo.add_resume(_make_resume_mixed_dates())
    assert len(repo.list_work_experiences(current_only=False)) == 2


def test_list_work_experiences_current_only_with_resume_id():
    repo = ResumeRepository()
    resp_a = repo.add_resume(_make_resume_mixed_dates("Alice", "A"))
    repo.add_resume(_make_resume_mixed_dates("Bob", "B"))
    results = repo.list_work_experiences(resume_id=resp_a.id, current_only=True)
    assert len(results) == 1
    assert results[0].company_name == "CurrentCo"


def test_list_work_experiences_current_only_case_insensitive():
    repo = ResumeRepository()
    repo.add_resume(ResumeCreate(
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
    results = repo.list_work_experiences(current_only=True)
    assert len(results) == 1
    assert results[0].company_name == "NowCo"


def test_list_work_experiences_current_only_no_current_roles():
    repo = ResumeRepository()
    repo.add_resume(ResumeCreate(
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
    assert repo.list_work_experiences(current_only=True) == []


# ── search_achievements ───────────────────────────────────────────────────────

def test_search_achievements_returns_match():
    repo = ResumeRepository()
    resp = repo.add_resume(_make_resume(companies=["Acme"]))
    results = repo.search_achievements("great")
    assert len(results) == 1
    assert "great" in results[0]["desc"]
    assert results[0]["company_name"] == "Acme"
    assert results[0]["resume_id"] == resp.id


def test_search_achievements_includes_parent_context():
    repo = ResumeRepository()
    resp = repo.add_resume(_make_resume(companies=["Globex"]))
    results = repo.search_achievements("Globex")
    assert results
    r = results[0]
    assert "company_name" in r
    assert "position_title" in r
    assert "work_experience_id" in r
    assert "resume_id" in r
    assert r["resume_id"] == resp.id


def test_search_achievements_case_insensitive():
    repo = ResumeRepository()
    repo.add_resume(_make_resume(companies=["Acme"]))
    assert len(repo.search_achievements("GREAT")) == 1
    assert len(repo.search_achievements("Great")) == 1


def test_search_achievements_no_match():
    repo = ResumeRepository()
    repo.add_resume(_make_resume(companies=["Acme"]))
    assert repo.search_achievements("quantum entanglement") == []


def test_search_achievements_scoped_by_resume_id():
    repo = ResumeRepository()
    resp_a = repo.add_resume(_make_resume("Alice", "A", companies=["Alpha"]))
    repo.add_resume(_make_resume("Bob", "B", companies=["Beta"]))
    # Both have "great" in achievements; scoping to resp_a should return only Alpha's
    results = repo.search_achievements("great", resume_id=resp_a.id)
    assert all(r["resume_id"] == resp_a.id for r in results)
    assert all(r["company_name"] == "Alpha" for r in results)


def test_search_achievements_scope_wrong_resume_returns_empty():
    repo = ResumeRepository()
    resp_a = repo.add_resume(_make_resume("Alice", "A", companies=["Alpha"]))
    resp_b = repo.add_resume(_make_resume("Bob", "B", companies=["Beta"]))
    # "Alpha" only appears in resp_a; scoping to resp_b should return nothing
    results = repo.search_achievements("Alpha", resume_id=resp_b.id)
    assert results == []


def test_search_achievements_returns_only_matching_bullets():
    repo = ResumeRepository()
    repo.add_resume(ResumeCreate(
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
    results = repo.search_achievements("latency")
    assert len(results) == 1
    assert "latency" in results[0]["desc"]


# ── search_resumes_by_name ────────────────────────────────────────────────────

def test_search_resumes_by_name_first_name():
    repo = ResumeRepository()
    resp = repo.add_resume(_make_resume("Hannah", "Hill"))
    results = repo.search_resumes_by_name("Hannah")
    assert len(results) == 1
    assert results[0]["id"] == resp.id


def test_search_resumes_by_name_last_name():
    repo = ResumeRepository()
    resp = repo.add_resume(_make_resume("Hannah", "Hill"))
    results = repo.search_resumes_by_name("Hill")
    assert len(results) == 1
    assert results[0]["id"] == resp.id


def test_search_resumes_by_name_case_insensitive():
    repo = ResumeRepository()
    repo.add_resume(_make_resume("Ivan", "Ivanov"))
    assert len(repo.search_resumes_by_name("ivan")) == 1
    assert len(repo.search_resumes_by_name("IVANOV")) == 1


def test_search_resumes_by_name_partial_match():
    repo = ResumeRepository()
    repo.add_resume(_make_resume("Julia", "Jones"))
    results = repo.search_resumes_by_name("Jul")
    assert len(results) == 1


def test_search_resumes_by_name_no_match():
    repo = ResumeRepository()
    repo.add_resume(_make_resume("Karl", "King"))
    assert repo.search_resumes_by_name("Zephyr") == []


def test_search_resumes_by_name_returns_identity_fields_only():
    repo = ResumeRepository()
    repo.add_resume(_make_resume("Lena", "Lee", companies=["Acme"], skills=["Python"]))
    results = repo.search_resumes_by_name("Lena")
    assert len(results) == 1
    r = results[0]
    assert set(r.keys()) == {"id", "first_name", "last_name", "email", "phone_num"}


def test_search_resumes_by_name_multiple_results():
    repo = ResumeRepository()
    resp_a = repo.add_resume(_make_resume("Mary", "Martin"))
    resp_b = repo.add_resume(_make_resume("Max", "Morris"))
    results = repo.search_resumes_by_name("Ma")
    assert {r["id"] for r in results} == {resp_a.id, resp_b.id}


# ── search_resumes_by_skill ───────────────────────────────────────────────────

def test_search_resumes_by_skill_returns_match():
    repo = ResumeRepository()
    resp = repo.add_resume(_make_resume("Nina", "Nash", skills=["Python", "Go"]))
    results = repo.search_resumes_by_skill("Python")
    assert len(results) == 1
    assert results[0]["id"] == resp.id
    assert "Python" in results[0]["matched_skills"]


def test_search_resumes_by_skill_case_insensitive():
    repo = ResumeRepository()
    repo.add_resume(_make_resume(skills=["TypeScript"]))
    assert len(repo.search_resumes_by_skill("typescript")) == 1
    assert len(repo.search_resumes_by_skill("TYPESCRIPT")) == 1


def test_search_resumes_by_skill_partial_match():
    repo = ResumeRepository()
    resp_a = repo.add_resume(_make_resume("Oscar", "O", skills=["JavaScript"]))
    resp_b = repo.add_resume(_make_resume("Paula", "P", skills=["TypeScript"]))
    repo.add_resume(_make_resume("Quinn", "Q", skills=["Go"]))
    results = repo.search_resumes_by_skill("script")
    assert {r["id"] for r in results} == {resp_a.id, resp_b.id}


def test_search_resumes_by_skill_no_match():
    repo = ResumeRepository()
    repo.add_resume(_make_resume(skills=["Python"]))
    assert repo.search_resumes_by_skill("COBOL") == []


def test_search_resumes_by_skill_excludes_non_matching_resumes():
    repo = ResumeRepository()
    resp_a = repo.add_resume(_make_resume("Rose", "R", skills=["Rust"]))
    repo.add_resume(_make_resume("Sam", "S", skills=["Python"]))
    results = repo.search_resumes_by_skill("Rust")
    assert len(results) == 1
    assert results[0]["id"] == resp_a.id


def test_search_resumes_by_skill_returns_minimal_fields():
    repo = ResumeRepository()
    repo.add_resume(_make_resume("Tara", "T", skills=["Java"]))
    results = repo.search_resumes_by_skill("Java")
    assert len(results) == 1
    r = results[0]
    assert set(r.keys()) == {"id", "first_name", "last_name", "matched_skills"}


# ── clear ─────────────────────────────────────────────────────────────────────

def test_clear_empties_all_stores():
    repo = ResumeRepository()
    repo.add_resume(_make_resume(companies=["Acme"], skills=["Python"]))
    repo.clear()
    assert repo.list_resumes() == []
    assert repo.list_work_experiences() == []
    assert repo.list_achievements() == []
    assert repo.list_badge_skills() == []
    assert repo._resumes == []
    assert repo._work_experiences == []
    assert repo._achievements == []
    assert repo._badge_skills == []
