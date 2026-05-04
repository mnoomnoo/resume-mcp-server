from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .collection import ResumeCollection
from .repository import ResumeRepository

logger = logging.getLogger(__name__)

_collection: ResumeCollection | None = None
_reload_pending = False

RESUME_DIR = Path(os.environ.get("RESUME_DIR", Path.home() / "resumes"))


def _do_reload() -> None:
    global _reload_pending
    _reload_pending = False
    if _collection is not None:
        count = _collection.load()
        logger.info("Reloaded %d documents (file change detected)", count)


class _ReloadHandler(FileSystemEventHandler):
    def on_any_event(self, event) -> None:
        global _reload_pending
        if event.is_directory or _collection is None:
            return
        if not _reload_pending:
            _reload_pending = True
            threading.Timer(2.0, _do_reload).start()


@asynccontextmanager
async def lifespan(server: FastMCP):
    global _collection
    _collection = ResumeCollection(resume_dir=RESUME_DIR)
    count = _collection.load()
    logger.info("Loaded %d documents from %s", count, RESUME_DIR)

    observer = Observer()
    observer.schedule(_ReloadHandler(), str(RESUME_DIR), recursive=True)
    observer.start()

    yield

    observer.stop()
    observer.join()
    _collection = None


mcp = FastMCP("resume-collection", lifespan=lifespan)


def _get_collection() -> ResumeCollection:
    if _collection is None:
        raise RuntimeError("Collection not initialized")
    return _collection


def _get_repo() -> ResumeRepository:
    return _get_collection()._repo


@mcp.tool()
def list_resumes(doc_type: str | None = None) -> list[dict[str, Any]]:
    """List all documents. When doc_type is 'resume' (or omitted), structured resume data
    is returned if available; otherwise flat file metadata is returned.

    Args:
        doc_type: Optional filter — one of: resume, cover_letter, application_material, other
    """
    if doc_type is None or doc_type == "resume":
        structured = _get_repo().list_resumes()
        if structured:
            return [r.model_dump() for r in structured]

    results = _get_collection().list_all(doc_type=doc_type)
    return [
        {
            "path": m.path,
            "filename": m.filename,
            "doc_type": m.doc_type,
            "modified": m.modified,
            "size_bytes": m.size_bytes,
        }
        for m in results
    ]


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
def search_resumes(query: str, doc_type: str | None = None) -> list[dict[str, Any]]:
    """Search across all documents for a keyword or phrase.

    Args:
        query: Text to search for (case-insensitive)
        doc_type: Optional filter — one of: resume, cover_letter, application_material, other
    """
    results = _get_collection().search(query=query, doc_type=doc_type)
    return [
        {
            "path": r.path,
            "filename": r.filename,
            "doc_type": r.doc_type,
            "match_count": r.match_count,
            "snippet": r.snippet,
        }
        for r in results
    ]


@mcp.tool()
def list_work_experiences(resume_id: str | None = None) -> list[dict[str, Any]]:
    """List work experiences, optionally filtered to a specific resume.

    Args:
        resume_id: Optional resume ID from list_resumes to filter results
    """
    results = _get_repo().list_work_experiences(resume_id=resume_id)
    return [r.model_dump() for r in results]


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
def list_achievements(resume_id: str | None = None) -> list[dict[str, Any]]:
    """List all achievements (phrase skills), optionally filtered to a specific resume.

    Args:
        resume_id: Optional resume ID from list_resumes to filter results
    """
    results = _get_repo().list_achievements(resume_id=resume_id)
    return [r.model_dump() for r in results]


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
def list_badge_skills(resume_id: str | None = None) -> list[dict[str, Any]]:
    """List all badge skills (technologies, tools, languages), optionally filtered to a resume.

    Args:
        resume_id: Optional resume ID from list_resumes to filter results
    """
    results = _get_repo().list_badge_skills(resume_id=resume_id)
    return [r.model_dump() for r in results]


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


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    transport = os.environ.get("FASTMCP_TRANSPORT", "http")
    host = os.environ.get("FASTMCP_HOST", "0.0.0.0")
    port = int(os.environ.get("FASTMCP_PORT", "8001"))
    mcp.run(transport=transport, host=host, port=port)


if __name__ == "__main__":
    main()
