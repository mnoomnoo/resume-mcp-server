from __future__ import annotations

from uuid import uuid4
from datetime import datetime, timezone
from pydantic import BaseModel

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
