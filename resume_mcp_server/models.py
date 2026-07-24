from __future__ import annotations

from typing import Any
from uuid import uuid4
from datetime import datetime, timezone
from pydantic import BaseModel, Field

ID = str


def generate_id() -> str:
    return str(uuid4())


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"


# ── Internal storage models ──────────────────────────────────────────────────

class BadgeSkillModel(BaseModel):
    id: ID
    created_at: str
    title: str


class AchievementModel(BaseModel):
    id: ID
    created_at: str
    desc: str


class WorkExperienceModel(BaseModel):
    id: ID
    created_at: str
    company_name: str
    position_title: str
    start_date: str
    end_date: str
    achievements: list[ID]


class SideProjectModel(BaseModel):
    id: ID
    created_at: str
    name: str
    description: str
    technologies: list[ID]


class EducationModel(BaseModel):
    id: ID
    created_at: str
    institution: str
    degree: str
    year: str
    competencies: list[ID]


class ResumeModel(BaseModel):
    id: ID
    created_at: str
    first_name: str
    last_name: str
    email: str
    phone_num: str
    address: str
    professional_statement: str
    education: str
    work_experiences: list[ID]
    badge_skills: list[ID]
    side_projects: list[ID]
    education_entries: list[ID]


# ── Create schemas ────────────────────────────────────────────────────────────

class BadgeSkillCreate(BaseModel):
    title: str


class AchievementCreate(BaseModel):
    desc: str


class WorkExperienceCreate(BaseModel):
    company_name: str
    position_title: str
    start_date: str
    end_date: str
    achievements: list[AchievementCreate]


class SideProjectCreate(BaseModel):
    name: str
    description: str
    technologies: list[BadgeSkillCreate]


class EducationCreate(BaseModel):
    institution: str
    degree: str
    year: str
    competencies: list[BadgeSkillCreate]


class ResumeCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone_num: str
    address: str
    professional_statement: str
    education: str
    work_experiences: list[WorkExperienceCreate]
    badge_skills: list[BadgeSkillCreate]
    side_projects: list[SideProjectCreate]
    education_entries: list[EducationCreate] = Field(default_factory=list)


# ── Response schemas (nested, resolved) ─────────────────────────────────────

class BadgeSkillResponse(BaseModel):
    id: ID
    created_at: str
    title: str


class AchievementResponse(BaseModel):
    id: ID
    created_at: str
    desc: str


class WorkExperienceResponse(BaseModel):
    id: ID
    created_at: str
    company_name: str
    position_title: str
    start_date: str
    end_date: str
    achievements: list[AchievementResponse]


class SideProjectResponse(BaseModel):
    id: ID
    created_at: str
    name: str
    description: str
    technologies: list[BadgeSkillResponse]


class EducationResponse(BaseModel):
    id: ID
    created_at: str
    institution: str
    degree: str
    year: str
    competencies: list[BadgeSkillResponse]


class ResumeResponse(BaseModel):
    id: ID
    created_at: str
    first_name: str
    last_name: str
    email: str
    phone_num: str
    address: str
    professional_statement: str
    education: str
    work_experiences: list[WorkExperienceResponse]
    badge_skills: list[BadgeSkillResponse]
    side_projects: list[SideProjectResponse]
    education_entries: list[EducationResponse]


# ── Analytics / aggregation response schemas ─────────────────────────────────

class CollectionStatsResponse(BaseModel):
    total_resumes: int
    total_work_experiences: int
    total_unique_skills: int
    total_side_projects: int
    total_education_entries: int
    total_achievements: int
    avg_skills_per_resume: float
    avg_work_experiences_per_resume: float


class SkillFrequencyItem(BaseModel):
    skill_id: ID
    skill_title: str
    resume_count: int


class PaginatedResponse(BaseModel):
    total_count: int
    items: list[Any]
    has_more: bool
    next_offset: int | None = None
    message: str

    @classmethod
    def paginate(cls, all_items: list[Any], offset: int, limit: int) -> "PaginatedResponse":
        total = len(all_items)
        page = all_items[offset:offset + limit]
        shown = offset + len(page)
        has_more = shown < total
        next_offset = shown if has_more else None
        message = (
            f"{shown} of {total} results shown. Call again with offset={next_offset} to see more."
            if has_more else
            f"All {total} results shown."
        )
        return cls(total_count=total, items=page, has_more=has_more, next_offset=next_offset, message=message)
