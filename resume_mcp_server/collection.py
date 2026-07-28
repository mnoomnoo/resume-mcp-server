from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

from .extractor import extract_text
from .models import PaginatedResponse, ResumeCreate
from .parser import parse_resume
from .repository import ResumeRepository

SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".md", ".txt"}

_DEFAULT_PATTERNS: dict[str, str] = {
    "resume": r"resume",
    "cover_letter": r"cover.?letter|_cl\.|_cl_|coverletter",
    "application_material": r"interview|study.?guide|why_|application.?question|job.?desc",
}

_PATTERN_ENV_VARS: dict[str, str] = {
    "resume": "DOC_TYPE_PATTERN_RESUME",
    "cover_letter": "DOC_TYPE_PATTERN_COVER_LETTER",
    "application_material": "DOC_TYPE_PATTERN_APPLICATION_MATERIAL",
}


def _infer_doc_type(filename: str) -> str:
    name = filename.lower()
    for doc_type, env_var in _PATTERN_ENV_VARS.items():
        pattern = os.environ.get(env_var) or _DEFAULT_PATTERNS[doc_type]
        try:
            if re.search(pattern, name):
                return doc_type
        except re.error as exc:
            logger.warning(
                "Invalid regex in %s=%r (%s); falling back to default pattern",
                env_var, pattern, exc,
            )
            if re.search(_DEFAULT_PATTERNS[doc_type], name):
                return doc_type
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

    @staticmethod
    def _resume_identity_key(create: ResumeCreate) -> tuple[str, ...]:
        """Identify 'the same person' across file-format variants of a resume."""
        if create.email:
            return ("email", create.email.lower())
        return ("name", create.first_name.lower(), create.last_name.lower())

    @staticmethod
    def _resume_richness(create: ResumeCreate) -> int:
        """Rough measure of how much structured content a parsed resume has."""
        return (
            len(create.work_experiences)
            + len(create.badge_skills)
            + len(create.side_projects)
            + len(create.education_entries)
        )

    def load(self) -> int:
        self._index.clear()
        self._repo.clear()
        pending_resumes: dict[tuple[str, ...], ResumeCreate] = {}
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
                except Exception as exc:
                    logger.warning("Failed to parse resume %r: %s", file_path.name, exc)
                    continue
                if create is None:
                    continue
                key = self._resume_identity_key(create)
                existing = pending_resumes.get(key)
                if existing is None or self._resume_richness(create) > self._resume_richness(existing):
                    if existing is not None:
                        logger.info(
                            "Dropping duplicate resume for %r in favor of a richer copy",
                            file_path.name,
                        )
                    pending_resumes[key] = create
        for create in pending_resumes.values():
            self._repo.add_resume(create)
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

    def search(self, query: str, doc_type: str | None = None, mode: str = "and",
               limit: int = 100, offset: int = 0) -> PaginatedResponse:
        mode = mode.lower()
        if mode == "regex":
            try:
                patterns = [re.compile(query, re.IGNORECASE)]
            except re.error as e:
                raise ValueError(f"Invalid regex pattern {query!r}: {e}") from e
            require_all = True
        else:
            tokens = query.split() or [query]
            patterns = [re.compile(re.escape(t), re.IGNORECASE) for t in tokens]
            require_all = mode != "or"
        results: list[dict] = []
        for rel, (meta, text) in self._index.items():
            if doc_type and meta.doc_type != doc_type:
                continue
            per_pattern_matches = [list(p.finditer(text)) for p in patterns]
            hit_flags = [len(matches) > 0 for matches in per_pattern_matches]
            hit = all(hit_flags) if require_all else any(hit_flags)
            if not hit:
                continue
            match_count = sum(len(matches) for matches in per_pattern_matches)
            # snippet is built around the first match of the first token that matched
            first_match = next(matches[0] for matches in per_pattern_matches if matches)
            start = max(0, first_match.start() - 100)
            end = min(len(text), first_match.end() + 100)
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
