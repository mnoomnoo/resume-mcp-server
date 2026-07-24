from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

from .extractor import extract_text
from .models import PaginatedResponse
from .parser import parse_resume
from .repository import ResumeRepository

SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".md", ".txt"}


def _infer_doc_type(filename: str) -> str:
    name = filename.lower()
    if re.search(r"resume", name):
        return "resume"
    if re.search(r"cover.?letter|_cl\.|_cl_|coverletter", name):
        return "cover_letter"
    if re.search(r"interview|study.?guide|why_|application.?question|job.?desc", name):
        return "application_material"
    return "other"


@dataclass
class ResumeMetadata:
    path: str
    filename: str
    doc_type: str
    modified: str
    size_bytes: int


@dataclass
class ResumeCollection:
    resume_dir: Path
    _index: dict[str, tuple[ResumeMetadata, str]] = field(default_factory=dict, repr=False)
    _repo: ResumeRepository = field(default_factory=ResumeRepository, repr=False)

    def load(self) -> int:
        self._index.clear()
        self._repo.clear()
        for file_path in sorted(self.resume_dir.rglob("*")):
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            if not file_path.is_file():
                continue
            rel = str(file_path.relative_to(self.resume_dir))
            stat = file_path.stat()
            doc_type = _infer_doc_type(file_path.name)
            meta = ResumeMetadata(
                path=rel,
                filename=file_path.name,
                doc_type=doc_type,
                modified=datetime.fromtimestamp(stat.st_mtime).date().isoformat(),
                size_bytes=stat.st_size,
            )
            try:
                text = extract_text(file_path)
            except Exception as exc:
                logger.debug("Could not extract text from %r: %s", file_path.name, exc)
                text = ""
            self._index[rel] = (meta, text)
            if doc_type == "resume" and text:
                try:
                    create = parse_resume(text, file_path.name)
                    if create is not None:
                        self._repo.add_resume(create)
                except Exception as exc:
                    logger.warning("Failed to parse resume %r: %s", file_path.name, exc)
        return len(self._index)

    def list_all(self, doc_type: str | None = None) -> list[ResumeMetadata]:
        results = [meta for meta, _ in self._index.values()]
        if doc_type:
            results = [m for m in results if m.doc_type == doc_type]
        return sorted(results, key=lambda m: m.modified, reverse=True)

    def get_text(self, path: str) -> str:
        if path not in self._index:
            raise KeyError(f"Document not found: {path!r}")
        return self._index[path][1]

    def search(self, query: str, doc_type: str | None = None, mode: str = "literal",
               limit: int = 100, offset: int = 0) -> PaginatedResponse:
        if mode.lower() == "regex":
            try:
                pattern = re.compile(query, re.IGNORECASE)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern {query!r}: {e}") from e
        else:
            pattern = re.compile(re.escape(query), re.IGNORECASE)
        results: list[dict] = []
        for rel, (meta, text) in self._index.items():
            if doc_type and meta.doc_type != doc_type:
                continue
            it = pattern.finditer(text)
            m = next(it, None)
            if m is None:
                continue
            match_count = 1 + sum(1 for _ in it)
            start = max(0, m.start() - 100)
            end = min(len(text), m.end() + 100)
            snippet = text[start:end].strip()
            results.append({
                "path": rel,
                "filename": meta.filename,
                "doc_type": meta.doc_type,
                "snippet": snippet,
                "match_count": match_count,
            })
        results.sort(key=lambda r: r["match_count"], reverse=True)
        return PaginatedResponse.paginate(results, offset, limit)
