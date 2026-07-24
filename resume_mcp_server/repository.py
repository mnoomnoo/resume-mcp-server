from __future__ import annotations

import re

from .models import (
    ID, generate_id, utc_now,
    BadgeSkillModel, AchievementModel, WorkExperienceModel, SideProjectModel, EducationModel, ResumeModel,
    BadgeSkillCreate, AchievementCreate, WorkExperienceCreate, SideProjectCreate, EducationCreate, ResumeCreate,
    BadgeSkillResponse, AchievementResponse, WorkExperienceResponse, SideProjectResponse, EducationResponse, ResumeResponse,
    CollectionStatsResponse, SkillFrequencyItem, PaginatedResponse,
)


def _make_matcher(query: str, mode: str = "and"):
    mode = mode.lower()
    if mode == "regex":
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern {query!r}: {e}") from e
        return lambda text: pattern.search(text) is not None
    tokens = query.split() or [query]
    patterns = [re.compile(re.escape(t), re.IGNORECASE) for t in tokens]
    if mode == "and":
        return lambda text: all(p.search(text) for p in patterns)
    return lambda text: any(p.search(text) for p in patterns)


class ResumeRepository:
    def __init__(self) -> None:
        self._badge_skills: list[BadgeSkillModel] = []
        self._achievements: list[AchievementModel] = []
        self._work_experiences: list[WorkExperienceModel] = []
        self._side_projects: list[SideProjectModel] = []
        self._education: list[EducationModel] = []
        self._resumes: list[ResumeModel] = []

        self._badge_skills_by_id: dict[ID, BadgeSkillModel] = {}
        self._achievements_by_id: dict[ID, AchievementModel] = {}
        self._work_experiences_by_id: dict[ID, WorkExperienceModel] = {}
        self._side_projects_by_id: dict[ID, SideProjectModel] = {}
        self._education_by_id: dict[ID, EducationModel] = {}
        self._resumes_by_id: dict[ID, ResumeModel] = {}
        self._badge_skills_by_title: dict[str, BadgeSkillModel] = {}
        self._work_experience_to_resume: dict[ID, ID] = {}
        self._side_project_to_resume: dict[ID, ID] = {}
        self._education_to_resume: dict[ID, ID] = {}

    def clear(self) -> None:
        self._badge_skills.clear()
        self._achievements.clear()
        self._work_experiences.clear()
        self._side_projects.clear()
        self._education.clear()
        self._resumes.clear()
        self._badge_skills_by_id.clear()
        self._achievements_by_id.clear()
        self._work_experiences_by_id.clear()
        self._side_projects_by_id.clear()
        self._education_by_id.clear()
        self._resumes_by_id.clear()
        self._badge_skills_by_title.clear()
        self._work_experience_to_resume.clear()
        self._side_project_to_resume.clear()
        self._education_to_resume.clear()

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

    def _side_project_to_response(self, m: SideProjectModel) -> SideProjectResponse:
        technologies = [
            self._badge_skill_to_response(self._badge_skills_by_id[tid])
            for tid in m.technologies
            if tid in self._badge_skills_by_id
        ]
        return SideProjectResponse(
            id=m.id, created_at=m.created_at,
            name=m.name, description=m.description,
            technologies=technologies,
        )

    def _education_to_response(self, m: EducationModel) -> EducationResponse:
        competencies = [
            self._badge_skill_to_response(self._badge_skills_by_id[cid])
            for cid in m.competencies
            if cid in self._badge_skills_by_id
        ]
        return EducationResponse(
            id=m.id, created_at=m.created_at,
            institution=m.institution, degree=m.degree, year=m.year,
            competencies=competencies,
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
        side_projects = [
            self._side_project_to_response(self._side_projects_by_id[pid])
            for pid in m.side_projects
            if pid in self._side_projects_by_id
        ]
        education_entries = [
            self._education_to_response(self._education_by_id[eid])
            for eid in m.education_entries
            if eid in self._education_by_id
        ]
        return ResumeResponse(
            id=m.id, created_at=m.created_at,
            first_name=m.first_name, last_name=m.last_name,
            email=m.email, phone_num=m.phone_num, address=m.address,
            professional_statement=m.professional_statement, education=m.education,
            work_experiences=work_experiences, badge_skills=badge_skills,
            side_projects=side_projects,
            education_entries=education_entries,
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

    def _add_side_project(self, create: SideProjectCreate) -> SideProjectModel:
        technology_ids = [self._add_badge_skill(t).id for t in create.technologies]
        model = SideProjectModel(
            id=generate_id(), created_at=utc_now(),
            name=create.name, description=create.description,
            technologies=technology_ids,
        )
        self._side_projects.append(model)
        self._side_projects_by_id[model.id] = model
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

    def _add_education(self, create: EducationCreate) -> EducationModel:
        competency_ids = [self._add_badge_skill(c).id for c in create.competencies]
        model = EducationModel(
            id=generate_id(), created_at=utc_now(),
            institution=create.institution, degree=create.degree, year=create.year,
            competencies=competency_ids,
        )
        self._education.append(model)
        self._education_by_id[model.id] = model
        return model

    # ── Public add ───────────────────────────────────────────────────────────

    def add_resume(self, create: ResumeCreate) -> ResumeResponse:
        badge_skill_ids = [self._add_badge_skill(b).id for b in create.badge_skills]
        work_experience_ids = [self._add_work_experience(w).id for w in create.work_experiences]
        side_project_ids = [self._add_side_project(p).id for p in create.side_projects]
        education_entry_ids = [self._add_education(e).id for e in create.education_entries]
        model = ResumeModel(
            id=generate_id(), created_at=utc_now(),
            first_name=create.first_name, last_name=create.last_name,
            email=create.email, phone_num=create.phone_num, address=create.address,
            professional_statement=create.professional_statement, education=create.education,
            work_experiences=work_experience_ids, badge_skills=badge_skill_ids,
            side_projects=side_project_ids,
            education_entries=education_entry_ids,
        )
        self._resumes.append(model)
        self._resumes_by_id[model.id] = model
        for wid in work_experience_ids:
            self._work_experience_to_resume[wid] = model.id
        for pid in side_project_ids:
            self._side_project_to_resume[pid] = model.id
        for eid in education_entry_ids:
            self._education_to_resume[eid] = model.id
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

    def find_side_project(self, id: ID) -> SideProjectResponse | None:
        m = self._side_projects_by_id.get(id)
        return self._side_project_to_response(m) if m else None

    def find_education(self, id: ID) -> EducationResponse | None:
        m = self._education_by_id.get(id)
        return self._education_to_response(m) if m else None

    # ── List all ──────────────────────────────────────────────────────────────

    def resume_exists(self, resume_id: ID) -> bool:
        return resume_id in self._resumes_by_id

    def _require_resume(self, resume_id: ID) -> None:
        if not self.resume_exists(resume_id):
            raise ValueError(f"resume {resume_id!r} not found")

    def list_resumes(self, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        all_items = [self._resume_to_response(m).model_dump() for m in self._resumes]
        return PaginatedResponse.paginate(all_items, offset, limit)

    def list_resume_summaries(self, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        all_items = [
            {
                "id": r.id,
                "first_name": r.first_name,
                "last_name": r.last_name,
                "email": r.email,
                "phone_num": r.phone_num,
            }
            for r in self._resumes
        ]
        return PaginatedResponse.paginate(all_items, offset, limit)

    def get_resume_profile(self, resume_id: ID) -> dict | None:
        r = self._resumes_by_id.get(resume_id)
        if r is None:
            return None
        return {
            "id": r.id,
            "first_name": r.first_name,
            "last_name": r.last_name,
            "email": r.email,
            "phone_num": r.phone_num,
            "address": r.address,
            "professional_statement": r.professional_statement,
            "education": r.education,
        }

    def list_achievements(self, resume_id: ID | None = None, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        if resume_id is None:
            all_items = [self._achievement_to_response(a).model_dump() for a in self._achievements]
        else:
            self._require_resume(resume_id)
            resume = self._resumes_by_id[resume_id]
            we_ids = set(resume.work_experiences)
            achievement_ids: set[ID] = set()
            for wid in we_ids:
                w = self._work_experiences_by_id.get(wid)
                if w:
                    achievement_ids.update(w.achievements)
            all_items = [self._achievement_to_response(a).model_dump() for a in self._achievements if a.id in achievement_ids]
        return PaginatedResponse.paginate(all_items, offset, limit)

    def list_work_experiences(self, resume_id: ID | None = None, current_only: bool = False, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        if resume_id is None:
            results = self._work_experiences
        else:
            self._require_resume(resume_id)
            resume = self._resumes_by_id[resume_id]
            results = [self._work_experiences_by_id[wid] for wid in resume.work_experiences if wid in self._work_experiences_by_id]
        if current_only:
            results = [w for w in results if re.search(r"present", w.end_date, re.IGNORECASE)]
        all_items = [self._work_experience_to_response(w).model_dump() for w in results]
        return PaginatedResponse.paginate(all_items, offset, limit)

    def list_badge_skills(self, resume_id: ID | None = None, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        if resume_id is None:
            all_items = [self._badge_skill_to_response(b).model_dump() for b in self._badge_skills]
        else:
            self._require_resume(resume_id)
            resume = self._resumes_by_id[resume_id]
            all_items = [
                self._badge_skill_to_response(self._badge_skills_by_id[bid]).model_dump()
                for bid in resume.badge_skills
                if bid in self._badge_skills_by_id
            ]
        return PaginatedResponse.paginate(all_items, offset, limit)

    def list_side_projects(self, resume_id: ID | None = None, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        if resume_id is None:
            all_items = [self._side_project_to_response(p).model_dump() for p in self._side_projects]
        else:
            self._require_resume(resume_id)
            resume = self._resumes_by_id[resume_id]
            all_items = [
                self._side_project_to_response(self._side_projects_by_id[pid]).model_dump()
                for pid in resume.side_projects
                if pid in self._side_projects_by_id
            ]
        return PaginatedResponse.paginate(all_items, offset, limit)

    def list_education(self, resume_id: ID | None = None, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        if resume_id is None:
            all_items = [self._education_to_response(e).model_dump() for e in self._education]
        else:
            self._require_resume(resume_id)
            resume = self._resumes_by_id[resume_id]
            all_items = [
                self._education_to_response(self._education_by_id[eid]).model_dump()
                for eid in resume.education_entries
                if eid in self._education_by_id
            ]
        return PaginatedResponse.paginate(all_items, offset, limit)

    # ── Analytics ─────────────────────────────────────────────────────────────

    def get_collection_stats(self) -> CollectionStatsResponse:
        total_resumes = len(self._resumes)
        avg_skills = (
            sum(len(r.badge_skills) for r in self._resumes) / total_resumes
            if total_resumes else 0.0
        )
        avg_work_exp = (
            sum(len(r.work_experiences) for r in self._resumes) / total_resumes
            if total_resumes else 0.0
        )
        return CollectionStatsResponse(
            total_resumes=total_resumes,
            total_work_experiences=len(self._work_experiences),
            total_unique_skills=len(self._badge_skills),
            total_side_projects=len(self._side_projects),
            total_education_entries=len(self._education),
            total_achievements=len(self._achievements),
            avg_skills_per_resume=round(avg_skills, 2),
            avg_work_experiences_per_resume=round(avg_work_exp, 2),
        )

    def get_skill_frequency(self, limit: int = 20) -> list[SkillFrequencyItem]:
        counts: dict[ID, int] = {}
        for r in self._resumes:
            for skill_id in r.badge_skills:
                counts[skill_id] = counts.get(skill_id, 0) + 1
        sorted_ids = sorted(counts, key=lambda sid: counts[sid], reverse=True)[:limit]
        return [
            SkillFrequencyItem(
                skill_id=sid,
                skill_title=self._badge_skills_by_id[sid].title,
                resume_count=counts[sid],
            )
            for sid in sorted_ids
            if sid in self._badge_skills_by_id
        ]

    def search_resumes_by_skill(self, skill: str | list[str], mode: str = "and", limit: int = 100, offset: int = 0) -> PaginatedResponse:
        skills = [skill] if isinstance(skill, str) else skill
        if not skills or not any(s.strip() for s in skills):
            raise ValueError("skill must contain at least one non-empty value")
        skill_match_groups: list[set[ID]] = []
        for s in skills:
            matcher = _make_matcher(s, mode)
            matched_ids = {bs.id for bs in self._badge_skills if matcher(bs.title)}
            skill_match_groups.append(matched_ids)
        valid_groups = [g for g in skill_match_groups if g]
        if not valid_groups or (mode.lower() == "and" and len(valid_groups) < len(skill_match_groups)):
            return PaginatedResponse.paginate([], offset, limit)
        results = []
        for r in self._resumes:
            resume_skill_ids = set(r.badge_skills)
            per_skill_matched = [g & resume_skill_ids for g in valid_groups]
            if mode.lower() == "and":
                hit = all(per_skill_matched)
            else:
                hit = any(per_skill_matched)
            if hit:
                matched_titles = [
                    self._badge_skills_by_id[sid].title
                    for matched_set in per_skill_matched
                    for sid in matched_set
                    if sid in self._badge_skills_by_id
                ]
                results.append({
                    "id": r.id,
                    "first_name": r.first_name,
                    "last_name": r.last_name,
                    "matched_skills": matched_titles,
                })
        return PaginatedResponse.paginate(results, offset, limit)

    # ── Search ────────────────────────────────────────────────────────────────

    def search_badge_skills(self, query: str, mode: str = "and", limit: int = 100, offset: int = 0) -> PaginatedResponse:
        matches = _make_matcher(query, mode)
        results = [
            self._badge_skill_to_response(s).model_dump()
            for s in self._badge_skills
            if matches(s.title)
        ]
        return PaginatedResponse.paginate(results, offset, limit)

    def search_work_experiences(self, query: str, mode: str = "and", limit: int = 100, offset: int = 0) -> PaginatedResponse:
        matches = _make_matcher(query, mode)
        results = []
        for we in self._work_experiences:
            if matches(we.company_name) or matches(we.position_title):
                hit = True
            else:
                hit = any(
                    (ach := self._achievements_by_id.get(aid)) is not None
                    and matches(ach.desc)
                    for aid in we.achievements
                )
            if hit:
                result = self._work_experience_to_response(we).model_dump()
                result["resume_id"] = self._work_experience_to_resume.get(we.id)
                results.append(result)
        return PaginatedResponse.paginate(results, offset, limit)

    def search_achievements(self, query: str, resume_id: ID | None = None, mode: str = "and", limit: int = 100, offset: int = 0) -> PaginatedResponse:
        if resume_id is not None:
            self._require_resume(resume_id)
        matches = _make_matcher(query, mode)
        results = []
        for we in self._work_experiences:
            if resume_id is not None and self._work_experience_to_resume.get(we.id) != resume_id:
                continue
            for aid in we.achievements:
                ach = self._achievements_by_id.get(aid)
                if ach and matches(ach.desc):
                    results.append({
                        "id": ach.id,
                        "desc": ach.desc,
                        "company_name": we.company_name,
                        "position_title": we.position_title,
                        "work_experience_id": we.id,
                        "resume_id": self._work_experience_to_resume.get(we.id),
                    })
        return PaginatedResponse.paginate(results, offset, limit)

    def search_side_projects(self, query: str, resume_id: ID | None = None, mode: str = "and", limit: int = 100, offset: int = 0) -> PaginatedResponse:
        if resume_id is not None:
            self._require_resume(resume_id)
        matches = _make_matcher(query, mode)
        results = []
        for p in self._side_projects:
            if resume_id is not None and self._side_project_to_resume.get(p.id) != resume_id:
                continue
            tech_titles = [
                self._badge_skills_by_id[tid].title
                for tid in p.technologies
                if tid in self._badge_skills_by_id
            ]
            hit = (
                matches(p.name)
                or matches(p.description)
                or any(matches(t) for t in tech_titles)
            )
            if hit:
                result = self._side_project_to_response(p).model_dump()
                result["resume_id"] = self._side_project_to_resume.get(p.id)
                results.append(result)
        return PaginatedResponse.paginate(results, offset, limit)

    def search_side_projects_by_technology(self, technology: str, mode: str = "and", limit: int = 100, offset: int = 0) -> PaginatedResponse:
        matches = _make_matcher(technology, mode)
        matching_ids = {s.id for s in self._badge_skills if matches(s.title)}
        results = []
        if matching_ids:
            for p in self._side_projects:
                matched = matching_ids & set(p.technologies)
                if matched:
                    titles = [self._badge_skills_by_id[tid].title for tid in matched if tid in self._badge_skills_by_id]
                    results.append({
                        "id": p.id,
                        "name": p.name,
                        "description": p.description,
                        "matched_technologies": titles,
                        "resume_id": self._side_project_to_resume.get(p.id),
                    })
        return PaginatedResponse.paginate(results, offset, limit)

    def search_resumes_by_name(self, query: str, mode: str = "and", limit: int = 100, offset: int = 0) -> PaginatedResponse:
        matches = _make_matcher(query, mode)
        results = [
            {
                "id": r.id,
                "first_name": r.first_name,
                "last_name": r.last_name,
                "email": r.email,
                "phone_num": r.phone_num,
            }
            for r in self._resumes
            if matches(r.first_name) or matches(r.last_name)
        ]
        return PaginatedResponse.paginate(results, offset, limit)

    def search_education(self, query: str, resume_id: ID | None = None, mode: str = "and", limit: int = 100, offset: int = 0) -> PaginatedResponse:
        if resume_id is not None:
            self._require_resume(resume_id)
        matches = _make_matcher(query, mode)
        results = []
        for e in self._education:
            if resume_id is not None and self._education_to_resume.get(e.id) != resume_id:
                continue
            competency_titles = [
                self._badge_skills_by_id[cid].title
                for cid in e.competencies
                if cid in self._badge_skills_by_id
            ]
            hit = (
                matches(e.institution)
                or matches(e.degree)
                or any(matches(t) for t in competency_titles)
            )
            if hit:
                result = self._education_to_response(e).model_dump()
                result["resume_id"] = self._education_to_resume.get(e.id)
                results.append(result)
        return PaginatedResponse.paginate(results, offset, limit)

    def search_education_by_competency(self, competency: str, mode: str = "and", limit: int = 100, offset: int = 0) -> PaginatedResponse:
        matches = _make_matcher(competency, mode)
        matching_ids = {s.id for s in self._badge_skills if matches(s.title)}
        results = []
        if matching_ids:
            for e in self._education:
                matched = matching_ids & set(e.competencies)
                if matched:
                    titles = [self._badge_skills_by_id[cid].title for cid in matched if cid in self._badge_skills_by_id]
                    results.append({
                        "id": e.id,
                        "institution": e.institution,
                        "degree": e.degree,
                        "year": e.year,
                        "matched_competencies": titles,
                        "resume_id": self._education_to_resume.get(e.id),
                    })
        return PaginatedResponse.paginate(results, offset, limit)
