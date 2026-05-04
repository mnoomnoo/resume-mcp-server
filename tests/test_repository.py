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
