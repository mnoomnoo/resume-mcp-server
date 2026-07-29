from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, field

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid integer in %s=%r; using default %s", name, raw, default)
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid float in %s=%r; using default %s", name, raw, default)
        return default


# ── Defaults, overridable per-call by list_ranked_resumes callers; these env
#    vars only control what's used when a call omits the corresponding arg. ──
DEFAULT_SKILL_MATCH_THRESHOLD = _env_int("ATS_SKILL_MATCH_THRESHOLD", 85)
DEFAULT_SKILLS_WEIGHT = _env_float("ATS_SKILLS_WEIGHT", 0.6)
DEFAULT_KEYWORD_WEIGHT = _env_float("ATS_KEYWORD_WEIGHT", 0.4)

MAX_LISTED_TERMS = 30
MAX_MISSING_SKILLS = 15

# ── Stopwords (hand-rolled; repo has no NLP dep to source one from) ───────
STOPWORDS = frozenset("""
a an the and or but if then else when at by for with about against between
into through during before after above below to from up down in out on off
over under again further once here there all any both each few more most
other some such no nor not only own same so than too very s t can will just
don should now is are was were be been being have has had having do does
did doing i you he she it we they them their his her its our your what
which who whom this that these those am as of we're they're you're i'm
he's she's it's we've you've i've we'll you'll i'll he'll she'll they'll
would could should've isn't aren't wasn't weren't hasn't haven't hadn't
doesn't don't didn't won't wouldn't shan't shouldn't can't cannot couldn't
mustn't let's that's who's what's here's there's when's where's why's how's
etc within per via using use used also may might must shall
""".split())

# ── Alias groups: bridges abbreviation/format variants pure fuzzy matching
#    can't reach (e.g. "js" vs "javascript" share almost no characters).
#    Curated, extensible via ATS_EXTRA_ALIAS_GROUPS — not a general
#    synonym dictionary. ──────────────────────────────────────────────────
_BUILTIN_ALIAS_GROUPS: list[list[str]] = [
    ["js", "javascript"], ["ts", "typescript"], ["py", "python"],
    ["k8s", "kubernetes"], ["postgres", "postgresql"], ["ml", "machine learning"],
    ["ai", "artificial intelligence"], ["nlp", "natural language processing"],
    ["cv", "computer vision"], ["aws", "amazon web services"],
    ["gcp", "google cloud platform"], ["node", "nodejs", "node.js"],
    ["reactjs", "react.js", "react"], ["vuejs", "vue.js", "vue"],
    ["golang", "go"], ["ux", "user experience"], ["ui", "user interface"],
    ["qa", "quality assurance"], ["devops", "development operations"],
    ["sql", "structured query language"], ["oop", "object oriented programming"],
    ["db", "database"], ["dbs", "databases"], ["gql", "graphql"],
    ["oss", "open source software"], ["saas", "software as a service"],
    ["api", "application programming interface"],
    ["cicd", "ci/cd", "ci cd", "continuous integration continuous deployment"],
    ["ci", "continuous integration"], ["cd", "continuous deployment"],
    ["oncall", "on-call", "on call"], ["fe", "frontend", "front end"],
    ["be", "backend", "back end"],
]


def _load_extra_alias_groups() -> list[list[str]]:
    raw = os.environ.get("ATS_EXTRA_ALIAS_GROUPS")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, list) or not all(
            isinstance(group, list) and all(isinstance(v, str) for v in group) for group in parsed
        ):
            raise ValueError("must be a JSON array of arrays of strings")
        return parsed
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Invalid ATS_EXTRA_ALIAS_GROUPS=%r (%s); ignoring, using built-in aliases only", raw, e)
        return []


_ALIAS_GROUPS: list[list[str]] = _BUILTIN_ALIAS_GROUPS + _load_extra_alias_groups()
ALIAS_MAP: dict[str, str] = {
    variant.lower(): group[0].lower() for group in _ALIAS_GROUPS for variant in group
}

_TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9+#./-]*")


def _tokenize(text: str) -> list[str]:
    return [t.strip(".-/") for t in _TOKEN_RE.findall((text or "").lower())]


def _significant_words(text: str) -> set[str]:
    return {t for t in _tokenize(text) if t and t not in STOPWORDS and len(t) >= 2}


def _canonical_word(word: str) -> str:
    return ALIAS_MAP.get(word, word)


def _canonical_phrase(phrase: str) -> str:
    stripped = phrase.strip().lower()
    if stripped in ALIAS_MAP:
        return ALIAS_MAP[stripped]
    return " ".join(_canonical_word(w) for w in _tokenize(phrase))


def _ngrams(tokens: list[str], n: int) -> list[str]:
    if n <= 0 or n > len(tokens):
        return []
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def _candidate_phrases(text: str, max_results: int = 40) -> list[str]:
    """Unigrams + bigrams built from significant (non-stopword) words, ranked
    by frequency — used as the job-description 'significant phrase' pool for
    missing-skill detection."""
    tokens = _tokenize(text)
    counts: Counter[str] = Counter()
    order: list[str] = []
    for i, tok in enumerate(tokens):
        if tok in STOPWORDS or len(tok) < 2:
            continue
        if tok not in counts:
            order.append(tok)
        counts[tok] += 1
        if i + 1 < len(tokens) and tokens[i + 1] not in STOPWORDS:
            bigram = f"{tok} {tokens[i + 1]}"
            if bigram not in counts:
                order.append(bigram)
            counts[bigram] += 1
    order.sort(key=lambda p: counts[p], reverse=True)
    return order[:max_results]


@dataclass
class SkillsScoreResult:
    score: float
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    total: int = 0
    matched_count: int = 0


@dataclass
class KeywordScoreResult:
    score: float
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    total: int = 0
    matched_count: int = 0


@dataclass
class ScoreResult:
    overall_score: float
    skills: SkillsScoreResult
    keywords: KeywordScoreResult


def compute_skills_score(
    skill_titles: list[str], job_description: str,
    threshold: int = DEFAULT_SKILL_MATCH_THRESHOLD,
) -> SkillsScoreResult:
    jd_tokens = _tokenize(job_description)
    jd_lower = job_description.lower()
    matched: list[str] = []
    for title in skill_titles:
        title_words = _tokenize(title)
        if not title_words:
            continue
        if title.lower() in jd_lower:
            matched.append(title)
            continue
        n = len(title_words)
        candidates: set[str] = set()
        for k in range(max(1, n - 1), n + 2):
            candidates.update(_ngrams(jd_tokens, k))
        canon_title = _canonical_phrase(title)
        best = max(
            (fuzz.token_set_ratio(canon_title, _canonical_phrase(c)) for c in candidates),
            default=0,
        )
        if best >= threshold:
            matched.append(title)

    total = len(skill_titles)
    score = round(100 * len(matched) / total, 1) if total else 0.0

    # Missing-skills signal: significant JD phrases not covered by ANY resume skill.
    missing_from_jd: list[str] = []
    for cand in _candidate_phrases(job_description):
        canon_cand = _canonical_phrase(cand)
        hit = any(
            cand in t.lower() or t.lower() in cand
            or fuzz.token_set_ratio(canon_cand, _canonical_phrase(t)) >= threshold
            for t in skill_titles
        )
        if not hit:
            missing_from_jd.append(cand)
        if len(missing_from_jd) >= MAX_MISSING_SKILLS:
            break

    return SkillsScoreResult(
        score=score, matched=matched, missing=missing_from_jd,
        total=total, matched_count=len(matched),
    )


def compute_keyword_score(resume_text: str, job_description: str) -> KeywordScoreResult:
    jd_significant = _significant_words(job_description)
    jd_counts = Counter(w for w in _tokenize(job_description) if w in jd_significant)
    if not jd_counts:
        return KeywordScoreResult(score=0.0, total=0, matched_count=0)

    resume_words = _significant_words(resume_text)
    resume_canon = {_canonical_word(w) for w in resume_words}

    matched: list[str] = []
    missing: list[str] = []
    for word, _count in jd_counts.most_common():
        canon = _canonical_word(word)
        if word in resume_words or canon in resume_canon:
            matched.append(word)
        else:
            missing.append(word)

    total = len(jd_counts)
    score = round(100 * len(matched) / total, 1)
    return KeywordScoreResult(
        score=score, matched=matched[:MAX_LISTED_TERMS], missing=missing[:MAX_LISTED_TERMS],
        total=total, matched_count=len(matched),
    )


def score_resume(
    skill_titles: list[str], resume_text: str, job_description: str,
    threshold: int = DEFAULT_SKILL_MATCH_THRESHOLD,
    skills_weight: float = DEFAULT_SKILLS_WEIGHT,
    keyword_weight: float = DEFAULT_KEYWORD_WEIGHT,
) -> ScoreResult:
    skills = compute_skills_score(skill_titles, job_description, threshold=threshold)
    keywords = compute_keyword_score(resume_text, job_description)
    weight_sum = skills_weight + keyword_weight
    overall = round(
        (skills_weight * skills.score + keyword_weight * keywords.score) / weight_sum, 1
    ) if weight_sum else 0.0
    return ScoreResult(overall_score=overall, skills=skills, keywords=keywords)
