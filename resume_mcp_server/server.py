from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from dotenv import load_dotenv

from .collection import ResumeCollection, SUPPORTED_EXTENSIONS
from .models import PaginatedResponse
from .repository import ResumeRepository

load_dotenv()

logger = logging.getLogger(__name__)

_collection: ResumeCollection | None = None

RESUME_DIR = Path(os.environ.get("RESUME_DIR", Path.home() / "resumes"))


class _ReloadHandler(FileSystemEventHandler):
    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def _is_relevant(self, path: str) -> bool:
        return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS

    def _schedule(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(2.0, self._reload)
            self._timer.daemon = True
            self._timer.start()

    def _reload(self) -> None:
        with self._lock:
            self._timer = None
        if _collection is not None:
            count = _collection.load()
            logger.info("Reloaded %d documents (file change detected)", count)

    def cancel(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def on_modified(self, event) -> None:
        if not event.is_directory and self._is_relevant(event.src_path):
            self._schedule()

    def on_created(self, event) -> None:
        if not event.is_directory and self._is_relevant(event.src_path):
            self._schedule()

    def on_deleted(self, event) -> None:
        if not event.is_directory and self._is_relevant(event.src_path):
            self._schedule()

    def on_moved(self, event) -> None:
        src_ok = not event.is_directory and self._is_relevant(event.src_path)
        dst_ok = self._is_relevant(getattr(event, "dest_path", ""))
        if src_ok or dst_ok:
            self._schedule()


@asynccontextmanager
async def lifespan(server: FastMCP):
    global _collection
    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    _collection = ResumeCollection(resume_dir=RESUME_DIR)
    count = _collection.load()
    logger.info("Loaded %d documents from %s", count, RESUME_DIR)

    handler = _ReloadHandler()
    observer = Observer()
    observer.schedule(handler, str(RESUME_DIR), recursive=True)
    observer.start()

    yield

    observer.stop()
    observer.join()
    handler.cancel()
    _collection = None


mcp = FastMCP("resume-collection", lifespan=lifespan)


def _get_collection() -> ResumeCollection:
    if _collection is None:
        raise RuntimeError("Collection not initialized")
    return _collection


def _get_repo() -> ResumeRepository:
    return _get_collection()._repo


def _safe_search(fn, *args, **kwargs) -> dict[str, Any]:
    try:
        return fn(*args, **kwargs).model_dump()
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
def list_resume_summaries(limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """List all resumes as lightweight identity records — id, name, email, phone only.
    Use this to orient and pick a resume_id before fetching details with other tools.
    Much more token-efficient than list_resumes when you only need to identify who is present.
    Response includes total_count and items for pagination.

    Args:
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    """
    return _get_repo().list_resume_summaries(limit=limit, offset=offset).model_dump()


@mcp.tool()
def get_resume_profile(resume_id: str) -> dict[str, Any] | str:
    """Get a resume's top-level fields (contact info, professional statement, education)
    without the nested work experience and badge skill lists.

    Args:
        resume_id: Resume ID from list_resume_summaries or search_resumes_by_name
    """
    result = _get_repo().get_resume_profile(resume_id)
    if result is None:
        return f"Error: resume {resume_id!r} not found"
    return result


@mcp.tool()
def list_resumes(doc_type: str | None = None, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """List all documents. When doc_type is 'resume' (or omitted), structured resume data
    is returned if available; otherwise flat file metadata is returned.
    Response includes total_count and items for pagination.

    Args:
        doc_type: Optional filter — one of: resume, cover_letter, application_material, other
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    """
    if doc_type is None or doc_type == "resume":
        paginated = _get_repo().list_resumes(limit=limit, offset=offset)
        if paginated.total_count > 0:
            return paginated.model_dump()

    all_meta = _get_collection().list_all(doc_type=doc_type)
    all_items = [
        {
            "path": m.path,
            "filename": m.filename,
            "doc_type": m.doc_type,
            "modified": m.modified,
            "size_bytes": m.size_bytes,
        }
        for m in all_meta
    ]
    return PaginatedResponse.paginate(all_items, offset, limit).model_dump()


@mcp.tool()
def get_resume(path: str) -> str:
    """Return the full extracted text of a document.

    Args:
        path: Relative path as returned by list_resumes, e.g. 'MyResume_v2.docx' or 'Acme/MyResume.docx'
    """
    try:
        return _get_collection().get_text(path)
    except KeyError as e:
        return f"Error: {e}"


@mcp.tool()
def search_resumes(query: str, doc_type: str | None = None, mode: str = "literal",
                    limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Search across all documents for a keyword or phrase.
    Response includes total_count, items, has_more, next_offset, and message for pagination.

    Args:
        query: Text to search for (case-insensitive)
        doc_type: Optional filter — one of: resume, cover_letter, application_material, other
        mode: 'literal' (default) matches query as-is; 'regex' treats query as a case-insensitive regular expression
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    """
    return _safe_search(_get_collection().search, query, doc_type, mode, limit, offset)


@mcp.tool()
def search_skills(query: str, mode: str = "and", limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Search badge skills by title keyword.
    Response includes total_count, items, has_more, next_offset, and message for pagination.

    Args:
        query: Text to search for in skill titles (case-insensitive)
        mode: Token match mode — 'and' (default) requires all words to match; 'or' requires any word to match; 'regex' treats query as a case-insensitive regular expression
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    """
    return _safe_search(_get_repo().search_badge_skills, query, mode, limit, offset)


@mcp.tool()
def search_work_experiences(query: str, mode: str = "and", limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Search work experiences by company name, position title, or achievement descriptions.

    Each result includes a resume_id field identifying which resume the experience belongs to.
    Response includes total_count, items, has_more, next_offset, and message for pagination.

    Args:
        query: Text to search for (case-insensitive)
        mode: Token match mode — 'and' (default) requires all words to match within the same field; 'or' requires any word to match; 'regex' treats query as a case-insensitive regular expression
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    """
    return _safe_search(_get_repo().search_work_experiences, query, mode, limit, offset)


@mcp.tool()
def search_achievements(query: str, resume_id: str | None = None, mode: str = "and",
                         limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Search achievement descriptions directly, returning only matching bullets with minimal parent context.
    More token-efficient than search_work_experiences when you only need matching achievements.

    Each result includes: id, desc, company_name, position_title, work_experience_id, resume_id.
    Response includes total_count, items, has_more, next_offset, and message for pagination.

    Args:
        query: Text to search for in achievement descriptions (case-insensitive)
        resume_id: Optional resume ID to scope the search to one resume
        mode: Token match mode — 'and' (default) requires all words to appear in the description; 'or' requires any word to match; 'regex' treats query as a case-insensitive regular expression
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    """
    return _safe_search(_get_repo().search_achievements, query, resume_id, mode, limit, offset)


@mcp.tool()
def search_resumes_by_name(query: str, mode: str = "and", limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Find resumes by person name (first or last name). Returns minimal identity fields only —
    use the returned id with other tools to fetch full details.

    Each result includes: id, first_name, last_name, email, phone_num.
    Response includes total_count, items, has_more, next_offset, and message for pagination.

    Args:
        query: Name fragment to search for (case-insensitive)
        mode: Token match mode — 'and' (default) requires all words to appear in the same name field; 'or' requires any word to match; 'regex' treats query as a case-insensitive regular expression
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    """
    return _safe_search(_get_repo().search_resumes_by_name, query, mode, limit, offset)


@mcp.tool()
def search_resumes_by_skill(skill: str, mode: str = "and", limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Find which resumes list a given badge skill. Returns resume identity and matched skill names only —
    more token-efficient than list_resumes when filtering by skill.

    Each result includes: id, first_name, last_name, matched_skills.
    Response includes total_count, items, has_more, next_offset, and message for pagination.

    Args:
        skill: Skill title fragment to search for (case-insensitive, partial match)
        mode: Token match mode — 'and' (default) requires all words to appear in the skill title; 'or' requires any word to match; 'regex' treats query as a case-insensitive regular expression
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    """
    return _safe_search(_get_repo().search_resumes_by_skill, skill, mode, limit, offset)


@mcp.tool()
def list_work_experiences(resume_id: str | None = None, current_only: bool = False, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """List work experiences, optionally filtered to a specific resume and/or only current roles.
    Response includes total_count and items for pagination.

    Args:
        resume_id: Optional resume ID from list_resume_summaries to filter results
        current_only: If True, return only roles where end_date is 'Present'
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    """
    return _get_repo().list_work_experiences(resume_id=resume_id, current_only=current_only, limit=limit, offset=offset).model_dump()


@mcp.tool()
def get_work_experience(id: str) -> dict[str, Any] | str:
    """Get a single work experience entry with its achievements.

    Args:
        id: Work experience ID from list_work_experiences
    """
    result = _get_repo().find_work_experience(id)
    if result is None:
        return f"Error: work experience {id!r} not found"
    return result.model_dump()


@mcp.tool()
def list_achievements(resume_id: str | None = None, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """List all achievements (phrase skills), optionally filtered to a specific resume.
    Response includes total_count and items for pagination.

    Args:
        resume_id: Optional resume ID from list_resumes to filter results
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    """
    return _get_repo().list_achievements(resume_id=resume_id, limit=limit, offset=offset).model_dump()


@mcp.tool()
def get_achievement(id: str) -> dict[str, Any] | str:
    """Get a single achievement (phrase skill) by ID.

    Args:
        id: Achievement ID from list_achievements
    """
    result = _get_repo().find_achievement(id)
    if result is None:
        return f"Error: achievement {id!r} not found"
    return result.model_dump()


@mcp.tool()
def list_badge_skills(resume_id: str | None = None, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """List all badge skills (technologies, tools, languages), optionally filtered to a resume.
    Response includes total_count and items for pagination.

    Args:
        resume_id: Optional resume ID from list_resumes to filter results
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    """
    return _get_repo().list_badge_skills(resume_id=resume_id, limit=limit, offset=offset).model_dump()


@mcp.tool()
def get_badge_skill(id: str) -> dict[str, Any] | str:
    """Get a single badge skill by ID.

    Args:
        id: Badge skill ID from list_badge_skills
    """
    result = _get_repo().find_badge_skill(id)
    if result is None:
        return f"Error: badge skill {id!r} not found"
    return result.model_dump()


@mcp.tool()
def list_side_projects(resume_id: str | None = None, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """List side projects (personal/portfolio projects, distinct from work experience)
    that demonstrate competency with specific technologies, optionally filtered to a resume.
    Response includes total_count and items for pagination.

    Args:
        resume_id: Optional resume ID from list_resume_summaries to filter results
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    """
    return _get_repo().list_side_projects(resume_id=resume_id, limit=limit, offset=offset).model_dump()


@mcp.tool()
def get_side_project(id: str) -> dict[str, Any] | str:
    """Get a single side project by ID, including the technologies it demonstrates.

    Args:
        id: Side project ID from list_side_projects
    """
    result = _get_repo().find_side_project(id)
    if result is None:
        return f"Error: side project {id!r} not found"
    return result.model_dump()


@mcp.tool()
def search_side_projects(query: str, resume_id: str | None = None, mode: str = "and",
                          limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Search side projects by name, description, or associated technology.

    Each result includes a resume_id field identifying which resume the project belongs to.
    Response includes total_count, items, has_more, next_offset, and message for pagination.

    Args:
        query: Text to search for (case-insensitive)
        resume_id: Optional resume ID to scope the search to one resume
        mode: Token match mode — 'and' (default) requires all words to match within the same field; 'or' requires any word to match; 'regex' treats query as a case-insensitive regular expression
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    """
    return _safe_search(_get_repo().search_side_projects, query, resume_id, mode, limit, offset)


@mcp.tool()
def search_side_projects_by_technology(technology: str, mode: str = "and",
                                        limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Find side projects that demonstrate competency with a given technology.

    Each result includes: id, name, description, matched_technologies, resume_id.
    Response includes total_count, items, has_more, next_offset, and message for pagination.

    Args:
        technology: Technology/skill name fragment to search for (case-insensitive, partial match)
        mode: Token match mode — 'and' (default) requires all words to appear in the technology name; 'or' requires any word to match; 'regex' treats query as a case-insensitive regular expression
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    """
    return _safe_search(_get_repo().search_side_projects_by_technology, technology, mode, limit, offset)


@mcp.tool()
def list_education(resume_id: str | None = None, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """List education entries (degree, institution, year, and relevant coursework/competencies),
    optionally filtered to a resume.
    Response includes total_count and items for pagination.

    Args:
        resume_id: Optional resume ID from list_resume_summaries to filter results
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    """
    return _get_repo().list_education(resume_id=resume_id, limit=limit, offset=offset).model_dump()


@mcp.tool()
def get_education(id: str) -> dict[str, Any] | str:
    """Get a single education entry by ID, including its competencies.

    Args:
        id: Education entry ID from list_education
    """
    result = _get_repo().find_education(id)
    if result is None:
        return f"Error: education entry {id!r} not found"
    return result.model_dump()


@mcp.tool()
def search_education(query: str, resume_id: str | None = None, mode: str = "and",
                      limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Search education entries by institution, degree, or competency.

    Each result includes a resume_id field identifying which resume the entry belongs to.
    Response includes total_count, items, has_more, next_offset, and message for pagination.

    Args:
        query: Text to search for (case-insensitive)
        resume_id: Optional resume ID to scope the search to one resume
        mode: Token match mode — 'and' (default) requires all words to match within the same field; 'or' requires any word to match; 'regex' treats query as a case-insensitive regular expression
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    """
    return _safe_search(_get_repo().search_education, query, resume_id, mode, limit, offset)


@mcp.tool()
def search_education_by_competency(competency: str, mode: str = "and",
                                    limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Find education entries that demonstrate competency with a given skill — useful for
    matching a candidate's coursework/training to a specific position's requirements.

    Each result includes: id, institution, degree, year, matched_competencies, resume_id.
    Response includes total_count, items, has_more, next_offset, and message for pagination.

    Args:
        competency: Skill/competency name fragment to search for (case-insensitive, partial match)
        mode: Token match mode — 'and' (default) requires all words to appear in the competency name; 'or' requires any word to match; 'regex' treats query as a case-insensitive regular expression
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    """
    return _safe_search(_get_repo().search_education_by_competency, competency, mode, limit, offset)


@mcp.tool()
def get_collection_stats() -> dict[str, Any]:
    """Return aggregate counts and averages across the entire loaded resume collection.

    Returns total_resumes, total_work_experiences, total_unique_skills, total_side_projects,
    total_education_entries, total_achievements, avg_skills_per_resume,
    avg_work_experiences_per_resume.
    """
    return _get_repo().get_collection_stats().model_dump()


@mcp.tool()
def get_skill_frequency(limit: int = 20) -> list[dict[str, Any]]:
    """Return badge skills ranked by how many resumes list them, in descending order.

    Useful for identifying the most common technologies across all candidates.

    Args:
        limit: Maximum number of skills to return (default 20)
    """
    return [item.model_dump() for item in _get_repo().get_skill_frequency(limit)]


@mcp.tool()
def search_resumes_by_skills(skills: list[str], mode: str = "and",
                              limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Find resumes that have specific skills, using the same partial token matching as search_resumes_by_skill.

    Each result includes: id, first_name, last_name, matched_skills.
    Response includes total_count, items, has_more, next_offset, and message for pagination.

    Args:
        skills: List of skill title fragments to filter by, e.g. ["Python", "Docker"]
        mode: 'and' (default) — resume must have at least one matching skill for EACH query;
              'or' — resume must have a matching skill for ANY query
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    """
    return _get_repo().search_resumes_by_skills(skills, mode, limit, offset).model_dump()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    transport = os.environ.get("FASTMCP_TRANSPORT", "stdio")
    host = os.environ.get("FASTMCP_HOST", "0.0.0.0")
    port = int(os.environ.get("FASTMCP_PORT", "8001"))
    if transport == "stdio":
        mcp.run(transport=transport)
    else:
        raw_origins = os.environ.get("FASTMCP_CORS_ORIGINS", "*")
        allow_origins = [o.strip() for o in raw_origins.split(",")] if raw_origins != "*" else ["*"]
        cors = Middleware(
            CORSMiddleware,
            allow_origins=allow_origins,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["Mcp-Session-Id"],
        )
        mcp.run(transport=transport, host=host, port=port, middleware=[cors])


if __name__ == "__main__":
    main()
