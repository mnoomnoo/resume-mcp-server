from __future__ import annotations

import importlib
import os
import unittest

from resume_mcp_server import scoring
from resume_mcp_server.scoring import (
    _canonical_word,
    _significant_words,
    _tokenize,
    compute_keyword_score,
    compute_skills_score,
    score_resume,
)


class TestTokenize(unittest.TestCase):
    def test_handles_punctuation_and_compounds(self):
        tokens = _tokenize("Node.js, C++, k8s!")
        self.assertIn("node.js", tokens)
        self.assertIn("c++", tokens)
        self.assertIn("k8s", tokens)

    def test_lowercases(self):
        self.assertEqual(_tokenize("Python DEVELOPER"), ["python", "developer"])

    def test_empty_string(self):
        self.assertEqual(_tokenize(""), [])
        self.assertEqual(_tokenize(None), [])


class TestSignificantWords(unittest.TestCase):
    def test_filters_stopwords_and_short_tokens(self):
        words = _significant_words("We are looking for a strong Python engineer")
        self.assertIn("python", words)
        self.assertIn("engineer", words)
        self.assertIn("strong", words)
        self.assertNotIn("we", words)
        self.assertNotIn("are", words)
        self.assertNotIn("for", words)
        self.assertNotIn("a", words)


class TestAliasMap(unittest.TestCase):
    def test_canonicalizes_js_and_javascript(self):
        self.assertEqual(_canonical_word("js"), _canonical_word("javascript"))

    def test_canonicalizes_k8s_and_kubernetes(self):
        self.assertEqual(_canonical_word("k8s"), _canonical_word("kubernetes"))

    def test_unknown_word_passes_through(self):
        self.assertEqual(_canonical_word("zephyr"), "zephyr")


class TestComputeSkillsScore(unittest.TestCase):
    def test_exact_substring_match(self):
        result = compute_skills_score(["Python"], "We need a Python developer.")
        self.assertEqual(result.score, 100.0)
        self.assertEqual(result.matched, ["Python"])

    def test_fuzzy_abbreviation_match(self):
        result = compute_skills_score(["Kubernetes"], "Experience with k8s is required.")
        self.assertIn("Kubernetes", result.matched)

    def test_fuzzy_format_variant_match(self):
        result = compute_skills_score(["PostgreSQL"], "Must know Postgres well.")
        self.assertIn("PostgreSQL", result.matched)

    def test_no_false_positive_on_unrelated_multiword_skill(self):
        jd = (
            "We are hiring a backend engineer to build distributed systems in Go, "
            "manage Kubernetes clusters, and own our CI/CD pipeline. Experience with "
            "PostgreSQL and gRPC is a plus. Strong communication skills required."
        )
        result = compute_skills_score(["Machine Learning"], jd)
        self.assertEqual(result.matched, [])

    def test_empty_skill_list_returns_zero(self):
        result = compute_skills_score([], "Some job description")
        self.assertEqual(result.score, 0.0)
        self.assertEqual(result.total, 0)

    def test_threshold_controls_fuzzy_strictness(self):
        # A near-miss typo (not an alias pair, so canonicalization doesn't force
        # an exact match) — loose threshold catches it, strict threshold doesn't.
        jd = "We use Snowflaek for our data warehouse."
        loose = compute_skills_score(["Snowflake"], jd, threshold=50)
        strict = compute_skills_score(["Snowflake"], jd, threshold=95)
        self.assertIn("Snowflake", loose.matched)
        self.assertNotIn("Snowflake", strict.matched)

    def test_missing_reports_uncovered_jd_terms(self):
        result = compute_skills_score(["Python"], "Python expert needed with Terraform skills")
        self.assertTrue(any("terraform" in m for m in result.missing))

    def test_short_skill_title_does_not_false_positive_on_substring(self):
        result_r = compute_skills_score(["R"], "We need a strong marketer for our growing team.")
        self.assertEqual(result_r.matched, [])
        result_c = compute_skills_score(["C"], "Excellent communication skills required.")
        self.assertEqual(result_c.matched, [])

    def test_short_skill_title_still_matches_when_actually_present(self):
        result = compute_skills_score(["R"], "Experience with R and Python for data analysis")
        self.assertEqual(result.matched, ["R"])

    def test_missing_skills_not_masked_by_unrelated_short_skill(self):
        result = compute_skills_score(
            ["R"], "Looking for a Terraform expert to join our growing team."
        )
        self.assertEqual(result.matched, [])
        self.assertTrue(any("terraform" in m for m in result.missing))

    def test_missing_skills_deduplicates_unigram_when_bigram_present(self):
        jd = (
            "We are hiring a backend engineer to build distributed systems in Go, "
            "manage Kubernetes clusters, and own our CI/CD pipeline."
        )
        result = compute_skills_score(["Python"], jd)
        self.assertIn("distributed systems", result.missing)
        self.assertNotIn("distributed", result.missing)

    def test_missing_excludes_generic_job_posting_words(self):
        jd = (
            "Senior Backend Engineer. We are looking for a Senior Backend Engineer "
            "with strong experience in Python and distributed systems. You will "
            "lead a small team and mentor junior engineers."
        )
        result = compute_skills_score(["Python"], jd)
        for generic in ("senior", "engineer", "engineers", "experience", "looking",
                        "strong", "lead", "mentor", "team", "small", "big"):
            self.assertNotIn(generic, result.missing)
        # "distributed systems" (the bigram) is preferred over the bare "distributed"
        # unigram — see test_missing_skills_deduplicates_unigram_when_bigram_present.
        self.assertIn("distributed systems", result.missing)


class TestComputeKeywordScore(unittest.TestCase):
    def test_full_overlap(self):
        jd = "distributed systems engineer"
        resume_text = "Experienced distributed systems engineer at Acme"
        result = compute_keyword_score(resume_text, jd)
        self.assertEqual(result.score, 100.0)

    def test_no_overlap(self):
        result = compute_keyword_score("gardening and pottery", "quantum physics research")
        self.assertEqual(result.score, 0.0)

    def test_stopwords_excluded_from_denominator(self):
        jd = "The role is for a team that we are proud of"
        result = compute_keyword_score("some resume text", jd)
        # Only "role" and "team" (and "proud") are non-stopword tokens.
        self.assertLessEqual(result.total, 3)

    def test_empty_job_description(self):
        result = compute_keyword_score("some resume text", "")
        self.assertEqual(result.score, 0.0)
        self.assertEqual(result.total, 0)


class TestScoreResume(unittest.TestCase):
    def test_overall_is_weighted_blend_default_weights(self):
        result = score_resume(["Python"], "Python", "Python")
        self.assertEqual(result.overall_score, round(0.6 * 100.0 + 0.4 * 100.0, 1))

    def test_overall_respects_custom_weights(self):
        result = score_resume(
            ["Python"], "unrelated resume text", "Python developer role, other jargon here",
            skills_weight=1.0, keyword_weight=0.0,
        )
        self.assertEqual(result.overall_score, result.skills.score)


class TestExtraAliasGroupsEnvVar(unittest.TestCase):
    def setUp(self):
        self._orig = os.environ.get("ATS_EXTRA_ALIAS_GROUPS")
        self.addCleanup(self._restore)

    def _restore(self):
        if self._orig is None:
            os.environ.pop("ATS_EXTRA_ALIAS_GROUPS", None)
        else:
            os.environ["ATS_EXTRA_ALIAS_GROUPS"] = self._orig
        importlib.reload(scoring)

    def test_valid_json_adds_alias(self):
        os.environ["ATS_EXTRA_ALIAS_GROUPS"] = '[["gpt", "llm"]]'
        reloaded = importlib.reload(scoring)
        self.assertEqual(reloaded._canonical_word("gpt"), reloaded._canonical_word("llm"))

    def test_invalid_json_falls_back_to_builtins_only(self):
        os.environ["ATS_EXTRA_ALIAS_GROUPS"] = "not valid json"
        reloaded = importlib.reload(scoring)
        # Built-in alias still present.
        self.assertEqual(reloaded._canonical_word("js"), reloaded._canonical_word("javascript"))


if __name__ == "__main__":
    unittest.main()
