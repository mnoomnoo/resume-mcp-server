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


# All tools in this server are pure read-only queries over a local, in-memory
# collection — no mutation, no network calls — so every tool shares this annotation set.
_READONLY = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False}


@mcp.tool(annotations=_READONLY)
def list_resume_summaries(query: str | None = None, mode: str = "and",
                           limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """List resumes as lightweight identity records — id, name, email, phone only.
    Use this to orient and pick a resume_id before fetching details with other tools.
    Much more token-efficient than list_resumes when you only need to identify who is present.
    Pass query to filter by first or last name (absorbs the old search_resumes_by_name tool).
    Response includes total_count and items for pagination.

    Args:
        query: Optional name fragment to filter by first or last name (case-insensitive)
        mode: Token match mode — 'and' (default) requires all words to appear in the same name field; 'or' requires any word to match; 'regex' treats query as a case-insensitive regular expression
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    Example: list_resume_summaries(query="jane doe")
    """
    return _safe_search(_get_repo().list_resume_summaries, query=query, mode=mode, limit=limit, offset=offset)


@mcp.tool(annotations=_READONLY)
def get_resume_profile(resume_id: str) -> dict[str, Any]:
    """Get a resume's top-level fields (contact info, professional statement, education)
    without the nested work experience and badge skill lists.
    See also: get_resume_full for everything about this resume in one call.
    Returns {"error": ...} if resume_id is not found.

    Args:
        resume_id: Resume ID from list_resume_summaries
    Example: get_resume_profile("a1b2c3d4-...")
    """
    result = _get_repo().get_resume_profile(resume_id)
    if result is None:
        return {"error": f"resume {resume_id!r} not found"}
    return result


@mcp.tool(annotations=_READONLY)
def get_resume_full(resume_id: str) -> dict[str, Any]:
    """Get a resume's complete nested structure in one call: profile fields plus all
    work experiences (with achievements), badge skills, side projects (with technologies),
    and education entries (with competencies).
    Prefer get_resume_profile plus the scoped list_* tools (list_work_experiences,
    list_skills, list_side_projects, list_education) when you only need part of this —
    it's more token-efficient. Use get_resume_full when you need the whole picture at once.
    Returns {"error": ...} if resume_id is not found.

    Args:
        resume_id: Resume ID from list_resume_summaries
    Example: get_resume_full("a1b2c3d4-...")
    """
    result = _get_repo().find_resume(resume_id)
    if result is None:
        return {"error": f"resume {resume_id!r} not found"}
    return result.model_dump()


@mcp.tool(annotations=_READONLY)
def list_resumes(doc_type: str | None = None, limit: int = 10, offset: int = 0) -> dict[str, Any]:
    """List all documents. When doc_type is 'resume' (or omitted), structured resume data
    is returned if available; otherwise flat file metadata is returned.
    Response includes total_count and items for pagination.
    See also: list_resume_summaries for a lighter-weight, more token-efficient listing;
    get_resume_full for one resume's full nested structure by resume_id.

    Args:
        doc_type: Optional filter — one of: resume, cover_letter, application_material, other
        limit: Maximum number of results to return (default 10 — each item is a fully nested resume)
        offset: Number of results to skip for pagination (default 0)
    Example: list_resumes(doc_type="resume", limit=10)
    """
    try:
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
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool(annotations=_READONLY)
def get_resume(path: str) -> dict[str, Any]:
    """Return the full extracted text of a document, as {"text": "..."}.
    Note: takes a file path (see list_resumes), not a resume_id — use get_resume_profile
    or list_resumes to fetch structured data by resume_id instead.
    Returns {"error": ...} if path is not found.

    Args:
        path: Relative path as returned by list_resumes, e.g. 'MyResume_v2.docx' or 'Acme/MyResume.docx'
    Example: get_resume("Acme/MyResume.docx")
    """
    try:
        return {"text": _get_collection().get_text(path)}
    except KeyError as e:
        return {"error": str(e)}


@mcp.tool(annotations=_READONLY)
def search_resumes(query: str, doc_type: str | None = None, mode: str = "and",
                    limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Search across all documents for a keyword or phrase.
    Response includes total_count, items, has_more, next_offset, and message for pagination.

    Args:
        query: Text to search for (case-insensitive)
        doc_type: Optional filter — one of: resume, cover_letter, application_material, other
        mode: Token match mode — 'and' (default) requires all words to appear in the document; 'or' requires any word to match; 'regex' treats query as a case-insensitive regular expression
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    Example: search_resumes("distributed systems", mode="and")
    """
    return _safe_search(_get_collection().search, query, doc_type, mode, limit, offset)


@mcp.tool(annotations=_READONLY)
def search_resumes_by_skill(skill: str | list[str], mode: str = "and", limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Find which resumes list one or more given badge skills. Returns resume identity and matched
    skill names only — more token-efficient than list_resumes when filtering by skill.
    Accepts either a single skill string or a list of skills to filter by multiple at once.

    Each result includes: id, first_name, last_name, matched_skills.
    Response includes total_count, items, has_more, next_offset, and message for pagination.

    Args:
        skill: Skill title fragment, or list of fragments, to search for (case-insensitive, partial match)
        mode: Token match mode. For a single skill: 'and' (default) requires all words to appear in the
              skill title, 'or' requires any word to match, 'regex' treats it as a case-insensitive
              regular expression. For multiple skills, mode also controls whether a resume must match
              EACH skill in the list ('and') or ANY skill in the list ('or'); 'regex' mode combines
              multiple skills with OR semantics.
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    Example: search_resumes_by_skill(["Python", "Docker"], mode="and")
    """
    return _safe_search(_get_repo().search_resumes_by_skill, skill, mode, limit, offset)


@mcp.tool(annotations=_READONLY)
def list_work_experiences(resume_id: str | None = None, query: str | None = None,
                           current_only: bool = False, mode: str = "and",
                           limit: int = 25, offset: int = 0) -> dict[str, Any]:
    """List work experiences, optionally filtered to a specific resume, only current roles,
    and/or a keyword query matched against company name, position title, or achievement
    descriptions (absorbs the old search_work_experiences tool).
    Each result includes a resume_id field identifying which resume the experience belongs to.
    Response includes total_count and items for pagination.
    Returns {"error": ...} if resume_id is given but not found.

    Args:
        resume_id: Optional resume ID from list_resume_summaries to filter results
        query: Optional text to match against company name, position title, or achievement descriptions (case-insensitive)
        current_only: If True, return only roles where end_date is 'Present'
        mode: Token match mode for query — 'and' (default) requires all words to match within the same field; 'or' requires any word to match; 'regex' treats query as a case-insensitive regular expression
        limit: Maximum number of results to return (default 25)
        offset: Number of results to skip for pagination (default 0)
    Example: list_work_experiences(query="staff engineer", current_only=True)
    """
    return _safe_search(_get_repo().list_work_experiences, resume_id=resume_id, query=query,
                         current_only=current_only, mode=mode, limit=limit, offset=offset)


@mcp.tool(annotations=_READONLY)
def get_work_experience(id: str) -> dict[str, Any]:
    """Get a single work experience entry with its achievements.
    Returns {"error": ...} if id is not found.

    Args:
        id: Work experience ID from list_work_experiences
    Example: get_work_experience("a1b2c3d4-...")
    """
    result = _get_repo().find_work_experience(id)
    if result is None:
        return {"error": f"work experience {id!r} not found"}
    return result.model_dump()


@mcp.tool(annotations=_READONLY)
def list_achievements(resume_id: str | None = None, query: str | None = None,
                       mode: str = "and", limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """List achievements (resume bullet points), optionally filtered to a specific resume
    and/or a keyword query matched against the achievement text (absorbs the old
    search_achievements tool).

    Response shape depends on the arguments given, to keep the common case cheap:
    - resume_id given, query omitted: bare {id, desc} per item (cheapest — you already
      know which resume these belong to).
    - query given, and/or resume_id omitted: each item also includes company_name,
      position_title, work_experience_id, and resume_id, since that context would
      otherwise be unrecoverable from the achievement alone.
    Response includes total_count and items for pagination.
    Returns {"error": ...} if resume_id is given but not found.

    Args:
        resume_id: Optional resume ID from list_resume_summaries to filter results
        query: Optional text to search for in achievement descriptions (case-insensitive)
        mode: Token match mode for query — 'and' (default) requires all words to appear in the description; 'or' requires any word to match; 'regex' treats query as a case-insensitive regular expression
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip for pagination (default 0)
    Example: list_achievements(resume_id="a1b2c3d4-...")
    """
    return _safe_search(_get_repo().list_achievements, resume_id=resume_id, query=query,
                         mode=mode, limit=limit, offset=offset)


@mcp.tool(annotations=_READONLY)
def get_achievement(id: str) -> dict[str, Any]:
    """Get a single achievement (phrase skill) by ID.
    Returns {"error": ...} if id is not found.

    Args:
        id: Achievement ID from list_achievements
    Example: get_achievement("a1b2c3d4-...")
    """
    result = _get_repo().find_achievement(id)
    if result is None:
        return {"error": f"achievement {id!r} not found"}
    return result.model_dump()


@mcp.tool(annotations=_READONLY)
def list_skills(resume_id: str | None = None, query: str | None = None,
                 mode: str = "and", limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """List badge skills (technologies, tools, languages), optionally filtered to a resume
    and/or a keyword query matched against the skill title (absorbs the old search_skills tool).
    Note: badge skills are deduplicated and shared across resumes by title, so — unlike
    work experiences, side projects, and education — items here do not carry a resume_id.
    Response includes total_count and items for pagination.
    Returns {"error": ...} if resume_id is given but not found.

    Args:
        resume_id: Optional resume ID from list_resume_summaries to filter results
        query: Optional text to search for in skill titles (case-insensitive)
        mode: Token match mode for query — 'and' (default) requires all words to match; 'or' requires any word to match; 'regex' treats query as a case-insensitive regular expression
        limit: Maximum number of results to return (default 100)
        offset: Number of results to skip for pagination (default 0)
    Example: list_skills(query="kubernetes")
    """
    return _safe_search(_get_repo().list_badge_skills, resume_id=resume_id, query=query,
                         mode=mode, limit=limit, offset=offset)


@mcp.tool(annotations=_READONLY)
def get_badge_skill(id: str) -> dict[str, Any]:
    """Get a single badge skill by ID.
    Returns {"error": ...} if id is not found.

    Args:
        id: Badge skill ID from list_skills
    Example: get_badge_skill("a1b2c3d4-...")
    """
    result = _get_repo().find_badge_skill(id)
    if result is None:
        return {"error": f"badge skill {id!r} not found"}
    return result.model_dump()


@mcp.tool(annotations=_READONLY)
def list_side_projects(resume_id: str | None = None, query: str | None = None,
                        technology: str | None = None, mode: str = "and",
                        limit: int = 25, offset: int = 0) -> dict[str, Any]:
    """List side projects (personal/portfolio projects, distinct from work experience),
    optionally filtered to a resume and/or matched by keyword or technology
    (absorbs the old search_side_projects and search_side_projects_by_technology tools).

    - If technology is given, projects are matched against technology names only, and each
      result uses a lighter shape: id, name, description, matched_technologies, resume_id.
    - Else if query is given, projects are matched against name, description, or technology
      names, and each result includes the full nested structure plus resume_id.
    - If both are given, technology takes precedence and query is ignored.
    - If neither is given, today's plain listing behavior applies.
    Response includes total_count and items for pagination.
    Returns {"error": ...} if resume_id is given but not found.

    Args:
        resume_id: Optional resume ID from list_resume_summaries to filter results
        query: Optional text to match against name, description, or technology (case-insensitive)
        technology: Optional technology/skill name fragment to match (case-insensitive, partial match); takes precedence over query
        mode: Token match mode — 'and' (default) requires all words to match within the same field; 'or' requires any word to match; 'regex' treats query/technology as a case-insensitive regular expression
        limit: Maximum number of results to return (default 25)
        offset: Number of results to skip for pagination (default 0)
    Example: list_side_projects(technology="kubernetes")
    """
    return _safe_search(_get_repo().list_side_projects, resume_id=resume_id, query=query,
                         technology=technology, mode=mode, limit=limit, offset=offset)


@mcp.tool(annotations=_READONLY)
def get_side_project(id: str) -> dict[str, Any]:
    """Get a single side project by ID, including the technologies it demonstrates.
    Returns {"error": ...} if id is not found.

    Args:
        id: Side project ID from list_side_projects
    Example: get_side_project("a1b2c3d4-...")
    """
    result = _get_repo().find_side_project(id)
    if result is None:
        return {"error": f"side project {id!r} not found"}
    return result.model_dump()


@mcp.tool(annotations=_READONLY)
def list_education(resume_id: str | None = None, query: str | None = None,
                    competency: str | None = None, mode: str = "and",
                    limit: int = 25, offset: int = 0) -> dict[str, Any]:
    """List education entries (degree, institution, year, and relevant coursework/competencies),
    optionally filtered to a resume and/or matched by keyword or competency
    (absorbs the old search_education and search_education_by_competency tools).

    - If competency is given, entries are matched against competency names only, and each
      result uses a lighter shape: id, institution, degree, year, matched_competencies, resume_id.
    - Else if query is given, entries are matched against institution, degree, or competency
      names, and each result includes the full nested structure plus resume_id.
    - If both are given, competency takes precedence and query is ignored.
    - If neither is given, today's plain listing behavior applies.
    Response includes total_count and items for pagination.
    Returns {"error": ...} if resume_id is given but not found.

    Args:
        resume_id: Optional resume ID from list_resume_summaries to filter results
        query: Optional text to match against institution, degree, or competency (case-insensitive)
        competency: Optional skill/competency name fragment to match (case-insensitive, partial match); takes precedence over query
        mode: Token match mode — 'and' (default) requires all words to match within the same field; 'or' requires any word to match; 'regex' treats query/competency as a case-insensitive regular expression
        limit: Maximum number of results to return (default 25)
        offset: Number of results to skip for pagination (default 0)
    Example: list_education(competency="machine learning")
    """
    return _safe_search(_get_repo().list_education, resume_id=resume_id, query=query,
                         competency=competency, mode=mode, limit=limit, offset=offset)


@mcp.tool(annotations=_READONLY)
def get_education(id: str) -> dict[str, Any]:
    """Get a single education entry by ID, including its competencies.
    Returns {"error": ...} if id is not found.

    Args:
        id: Education entry ID from list_education
    Example: get_education("a1b2c3d4-...")
    """
    result = _get_repo().find_education(id)
    if result is None:
        return {"error": f"education entry {id!r} not found"}
    return result.model_dump()


@mcp.tool(annotations=_READONLY)
def get_collection_stats() -> dict[str, Any]:
    """Return aggregate counts and averages across the entire loaded resume collection.

    Returns total_resumes, total_work_experiences, total_unique_skills, total_side_projects,
    total_education_entries, total_achievements, avg_skills_per_resume,
    avg_work_experiences_per_resume.
    Example: get_collection_stats()
    """
    return _get_repo().get_collection_stats().model_dump()


@mcp.tool(annotations=_READONLY)
def get_skill_frequency(limit: int = 20) -> list[dict[str, Any]]:
    """Return badge skills ranked by how many resumes list them, in descending order.

    Useful for identifying the most common technologies across all candidates.

    Args:
        limit: Maximum number of skills to return (default 20)
    Example: get_skill_frequency(limit=10)
    """
    return [item.model_dump() for item in _get_repo().get_skill_frequency(limit)]


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
