from __future__ import annotations

import re

from .models import (
    ID, generate_id, utc_now,
    BadgeSkillModel, AchievementModel, WorkExperienceModel, ResumeModel,
    BadgeSkillCreate, AchievementCreate, WorkExperienceCreate, ResumeCreate,
    BadgeSkillResponse, AchievementResponse, WorkExperienceResponse, ResumeResponse,
)


class ResumeRepository:
    def __init__(self) -> None:
        self._badge_skills: list[BadgeSkillModel] = []
        self._achievements: list[AchievementModel] = []
        self._work_experiences: list[WorkExperienceModel] = []
        self._resumes: list[ResumeModel] = []

        self._badge_skills_by_id: dict[ID, BadgeSkillModel] = {}
        self._achievements_by_id: dict[ID, AchievementModel] = {}
        self._work_experiences_by_id: dict[ID, WorkExperienceModel] = {}
        self._resumes_by_id: dict[ID, ResumeModel] = {}
        self._badge_skills_by_title: dict[str, BadgeSkillModel] = {}
        self._work_experience_to_resume: dict[ID, ID] = {}

    def clear(self) -> None:
        self._badge_skills.clear()
        self._achievements.clear()
        self._work_experiences.clear()
        self._resumes.clear()
        self._badge_skills_by_id.clear()
        self._achievements_by_id.clear()
        self._work_experiences_by_id.clear()
        self._resumes_by_id.clear()
        self._badge_skills_by_title.clear()
        self._work_experience_to_resume.clear()

    # ── Model → Response ─────────────────────────────────────────────────────

    def _badge_skill_to_response(self, m: BadgeSkillModel) -> BadgeSkillResponse:
        return BadgeSkillResponse(id=m.id, created_at=m.created_at, title=m.title)

    def _achievement_to_response(self, m: AchievementModel) -> AchievementResponse:
        return AchievementResponse(id=m.id, created_at=m.created_at, desc=m.desc)

    def _work_experience_to_response(self, m: WorkExperienceModel) -> WorkExperienceResponse:
        achievements = [
            self._achievement_to_response(self._achievements_by_id[aid])
            for aid in m.achievements
            if aid in self._achievements_by_id
        ]
        return WorkExperienceResponse(
            id=m.id, created_at=m.created_at,
            company_name=m.company_name, position_title=m.position_title,
            start_date=m.start_date, end_date=m.end_date,
            achievements=achievements,
        )

    def _resume_to_response(self, m: ResumeModel) -> ResumeResponse:
        work_experiences = [
            self._work_experience_to_response(self._work_experiences_by_id[wid])
            for wid in m.work_experiences
            if wid in self._work_experiences_by_id
        ]
        badge_skills = [
            self._badge_skill_to_response(self._badge_skills_by_id[bid])
            for bid in m.badge_skills
            if bid in self._badge_skills_by_id
        ]
        return ResumeResponse(
            id=m.id, created_at=m.created_at,
            first_name=m.first_name, last_name=m.last_name,
            email=m.email, phone_num=m.phone_num, address=m.address,
            professional_statement=m.professional_statement, education=m.education,
            work_experiences=work_experiences, badge_skills=badge_skills,
        )

    # ── Internal add helpers ──────────────────────────────────────────────────

    def _add_badge_skill(self, create: BadgeSkillCreate) -> BadgeSkillModel:
        key = create.title.lower()
        existing = self._badge_skills_by_title.get(key)
        if existing:
            return existing
        model = BadgeSkillModel(id=generate_id(), created_at=utc_now(), title=create.title)
        self._badge_skills.append(model)
        self._badge_skills_by_id[model.id] = model
        self._badge_skills_by_title[key] = model
        return model

    def _add_achievement(self, create: AchievementCreate) -> AchievementModel:
        model = AchievementModel(id=generate_id(), created_at=utc_now(), desc=create.desc)
        self._achievements.append(model)
        self._achievements_by_id[model.id] = model
        return model

    def _add_work_experience(self, create: WorkExperienceCreate) -> WorkExperienceModel:
        achievement_ids = [self._add_achievement(a).id for a in create.achievements]
        model = WorkExperienceModel(
            id=generate_id(), created_at=utc_now(),
            company_name=create.company_name, position_title=create.position_title,
            start_date=create.start_date, end_date=create.end_date,
            achievements=achievement_ids,
        )
        self._work_experiences.append(model)
        self._work_experiences_by_id[model.id] = model
        return model

    # ── Public add ───────────────────────────────────────────────────────────

    def add_resume(self, create: ResumeCreate) -> ResumeResponse:
        badge_skill_ids = [self._add_badge_skill(b).id for b in create.badge_skills]
        work_experience_ids = [self._add_work_experience(w).id for w in create.work_experiences]
        model = ResumeModel(
            id=generate_id(), created_at=utc_now(),
            first_name=create.first_name, last_name=create.last_name,
            email=create.email, phone_num=create.phone_num, address=create.address,
            professional_statement=create.professional_statement, education=create.education,
            work_experiences=work_experience_ids, badge_skills=badge_skill_ids,
        )
        self._resumes.append(model)
        self._resumes_by_id[model.id] = model
        for wid in work_experience_ids:
            self._work_experience_to_resume[wid] = model.id
        return self._resume_to_response(model)

    # ── Find by ID ────────────────────────────────────────────────────────────

    def find_resume(self, id: ID) -> ResumeResponse | None:
        m = self._resumes_by_id.get(id)
        return self._resume_to_response(m) if m else None

    def find_achievement(self, id: ID) -> AchievementResponse | None:
        m = self._achievements_by_id.get(id)
        return self._achievement_to_response(m) if m else None

    def find_work_experience(self, id: ID) -> WorkExperienceResponse | None:
        m = self._work_experiences_by_id.get(id)
        return self._work_experience_to_response(m) if m else None

    def find_badge_skill(self, id: ID) -> BadgeSkillResponse | None:
        m = self._badge_skills_by_id.get(id)
        return self._badge_skill_to_response(m) if m else None

    # ── List all ──────────────────────────────────────────────────────────────

    def list_resumes(self) -> list[ResumeResponse]:
        return [self._resume_to_response(m) for m in self._resumes]

    def list_achievements(self, resume_id: ID | None = None) -> list[AchievementResponse]:
        if resume_id is None:
            return [self._achievement_to_response(a) for a in self._achievements]
        resume = self._resumes_by_id.get(resume_id)
        if not resume:
            return []
        we_ids = set(resume.work_experiences)
        achievement_ids: set[ID] = set()
        for wid in we_ids:
            w = self._work_experiences_by_id.get(wid)
            if w:
                achievement_ids.update(w.achievements)
        return [self._achievement_to_response(a) for a in self._achievements if a.id in achievement_ids]

    def list_work_experiences(self, resume_id: ID | None = None) -> list[WorkExperienceResponse]:
        if resume_id is None:
            return [self._work_experience_to_response(w) for w in self._work_experiences]
        resume = self._resumes_by_id.get(resume_id)
        if not resume:
            return []
        return [
            self._work_experience_to_response(self._work_experiences_by_id[wid])
            for wid in resume.work_experiences
            if wid in self._work_experiences_by_id
        ]

    def list_badge_skills(self, resume_id: ID | None = None) -> list[BadgeSkillResponse]:
        if resume_id is None:
            return [self._badge_skill_to_response(b) for b in self._badge_skills]
        resume = self._resumes_by_id.get(resume_id)
        if not resume:
            return []
        return [
            self._badge_skill_to_response(self._badge_skills_by_id[bid])
            for bid in resume.badge_skills
            if bid in self._badge_skills_by_id
        ]

    # ── Search ────────────────────────────────────────────────────────────────

    def search_badge_skills(self, query: str) -> list[BadgeSkillResponse]:
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        return [
            self._badge_skill_to_response(s)
            for s in self._badge_skills
            if pattern.search(s.title)
        ]

    def search_work_experiences(self, query: str) -> list[dict]:
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        results = []
        for we in self._work_experiences:
            if pattern.search(we.company_name) or pattern.search(we.position_title):
                hit = True
            else:
                hit = any(
                    (ach := self._achievements_by_id.get(aid)) is not None
                    and pattern.search(ach.desc)
                    for aid in we.achievements
                )
            if hit:
                result = self._work_experience_to_response(we).model_dump()
                result["resume_id"] = self._work_experience_to_resume.get(we.id)
                results.append(result)
        return results
