import random

from app.tools.generate_fake_jobs import _salary_range


def test_salary_range_increases_with_experience_for_technology():
    low_junior_min, low_junior_max = _salary_range("Technology", "0-1 nam", "Hanoi")
    senior_min, senior_max = _salary_range("Technology", "5+ nam", "Hanoi")
    assert senior_min > low_junior_min
    assert senior_max > low_junior_max


def test_salary_range_respects_location_multiplier():
    random.seed(1234)
    hanoi_min, _ = _salary_range("Operations", "1-3 nam", "Hanoi")
    random.seed(1234)
    cantho_min, _ = _salary_range("Operations", "1-3 nam", "Can Tho")
    assert hanoi_min >= cantho_min
