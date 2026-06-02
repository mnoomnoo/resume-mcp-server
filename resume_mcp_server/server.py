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

from .collection import ResumeCollection, SUPPORTED_EXTENSIONS
from .repository import ResumeRepository

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
def search_skills(query: str) -> list[dict[str, Any]]:
    """Search badge skills by title keyword.

    Args:
        query: Text to search for in skill titles (case-insensitive)
    """
    return [s.model_dump() for s in _get_repo().search_badge_skills(query)]


@mcp.tool()
def search_work_experiences(query: str) -> list[dict[str, Any]]:
    """Search work experiences by company name, position title, or achievement descriptions.

    Each result includes a resume_id field identifying which resume the experience belongs to.

    Args:
        query: Text to search for (case-insensitive)
    """
    return _get_repo().search_work_experiences(query)


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
