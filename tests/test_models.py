from __future__ import annotations

import unittest
from datetime import datetime
from uuid import UUID

from pydantic import ValidationError

from resume_mcp_server.models import (
    MAX_PAGE_LIMIT,
    AchievementCreate,
    PaginatedResponse,
    ResumeCreate,
    WorkExperienceCreate,
    generate_id,
    utc_now,
    validate_pagination,
)


# ── generate_id ─────────────────────────────────────────────────────────────

class TestGenerateId(unittest.TestCase):
    def test_returns_string(self):
        self.assertIsInstance(generate_id(), str)

    def test_is_valid_uuid(self):
        UUID(generate_id())  # should not raise

    def test_successive_calls_differ(self):
        self.assertNotEqual(generate_id(), generate_id())


# ── utc_now ─────────────────────────────────────────────────────────────────

class TestUtcNow(unittest.TestCase):
    def test_ends_with_z(self):
        self.assertTrue(utc_now().endswith("Z"))

    def test_parses_as_datetime(self):
        value = utc_now()
        datetime.strptime(value[:-1], "%Y-%m-%dT%H:%M:%S")  # should not raise


# ── validate_pagination ───────────────────────────────────────────────────────

class TestValidatePagination(unittest.TestCase):
    def test_zero_limit_raises(self):
        with self.assertRaises(ValueError):
            validate_pagination(0, 0)

    def test_negative_limit_raises(self):
        with self.assertRaises(ValueError):
            validate_pagination(-1, 0)

    def test_negative_offset_raises(self):
        with self.assertRaises(ValueError):
            validate_pagination(10, -1)

    def test_valid_input_does_not_raise(self):
        validate_pagination(1, 0)  # should not raise


# ── PaginatedResponse.paginate ────────────────────────────────────────────────

class TestPaginatedResponsePaginate(unittest.TestCase):
    def test_empty_items(self):
        result = PaginatedResponse.paginate([], offset=0, limit=10)
        self.assertEqual(result.total_count, 0)
        self.assertEqual(result.items, [])
        self.assertFalse(result.has_more)
        self.assertIsNone(result.next_offset)
        self.assertEqual(result.message, "All 0 results shown.")

    def test_offset_at_end_has_no_more(self):
        result = PaginatedResponse.paginate([1, 2, 3], offset=3, limit=10)
        self.assertEqual(result.items, [])
        self.assertFalse(result.has_more)
        self.assertIsNone(result.next_offset)

    def test_partial_page_has_more(self):
        result = PaginatedResponse.paginate([1, 2, 3, 4, 5], offset=0, limit=2)
        self.assertEqual(result.items, [1, 2])
        self.assertTrue(result.has_more)
        self.assertEqual(result.next_offset, 2)
        self.assertIn("Call again with offset=2", result.message)

    def test_limit_above_max_is_capped(self):
        items = list(range(300))
        result = PaginatedResponse.paginate(items, offset=0, limit=500)
        self.assertEqual(len(result.items), MAX_PAGE_LIMIT)
        self.assertIn(f"Requested limit 500 capped to {MAX_PAGE_LIMIT}.", result.message)

    def test_invalid_limit_raises(self):
        with self.assertRaises(ValueError):
            PaginatedResponse.paginate([1, 2, 3], offset=0, limit=0)


# ── Create model validation ───────────────────────────────────────────────────

class TestCreateModelValidation(unittest.TestCase):
    def test_work_experience_missing_required_field_raises(self):
        with self.assertRaises(ValidationError):
            WorkExperienceCreate(company_name="Acme")  # type: ignore[call-arg]

    def test_resume_create_missing_required_field_raises(self):
        with self.assertRaises(ValidationError):
            ResumeCreate(first_name="Jane")  # type: ignore[call-arg]

    def test_nested_resume_create_round_trips(self):
        resume = ResumeCreate(
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            phone_num="503-555-1234",
            address="Portland, OR",
            professional_statement="Experienced engineer.",
            education="BS Computer Science",
            work_experiences=[
                WorkExperienceCreate(
                    company_name="Acme Corp",
                    position_title="Software Engineer",
                    start_date="2020",
                    end_date="2022",
                    achievements=[AchievementCreate(desc="Built a distributed system")],
                )
            ],
            badge_skills=[],
            side_projects=[],
        )
        dumped = resume.model_dump()
        self.assertEqual(dumped["first_name"], "Jane")
        self.assertEqual(len(dumped["work_experiences"]), 1)
        self.assertEqual(
            dumped["work_experiences"][0]["achievements"][0]["desc"],
            "Built a distributed system",
        )
        self.assertEqual(dumped["education_entries"], [])


if __name__ == "__main__":
    unittest.main()
