from app.graph.nodes.rag_retriever import _enforce_experience_hard_rule, _job_matches_experience, _rank_jobs


def test_rank_jobs_prefers_requested_location_and_role():
    jobs = [
        {
            "title": "AI Engineer",
            "location": "Brazil, Colombia, Philippines",
            "description": "AI platform engineer",
        },
        {
            "title": "Senior AI Engineer",
            "location": "Ho Chi Minh City, Vietnam",
            "description": "AI and machine learning projects",
        },
    ]
    ranked = _rank_jobs(
        jobs,
        positions=["AI Engineer"],
        locations=["Ho Chi Minh City"],
        skills=[],
        target_experience_years=None,
    )
    assert ranked[0]["location"] == "Ho Chi Minh City, Vietnam"


def test_rank_jobs_prefers_vietnam_when_location_not_specified():
    jobs = [
        {"title": "Data Analyst", "location": "Berlin", "description": "analytics and reporting"},
        {"title": "Data Analyst", "location": "Hanoi, Vietnam", "description": "analytics and reporting"},
    ]
    ranked = _rank_jobs(
        jobs,
        positions=["Data Analyst"],
        locations=[],
        skills=[],
        target_experience_years=None,
    )
    assert "vietnam" in ranked[0]["location"].lower()


def test_job_matches_experience_years():
    assert _job_matches_experience({"experience": "0-1 nam"}, 1)
    assert _job_matches_experience({"experience": "1-3 nam"}, 1)
    assert not _job_matches_experience({"experience": "3-5 nam"}, 1)


def test_enforce_one_year_experience_rule_strictly_filters_higher_bands():
    jobs = [
        {"experience": "0-1 nam"},
        {"experience": "1-3 nam"},
        {"experience": "2-4 nam"},
        {"experience": "3-5 nam"},
        {"experience": "5+ nam"},
    ]
    filtered = _enforce_experience_hard_rule(jobs, 1)
    assert [job["experience"] for job in filtered] == ["0-1 nam", "1-3 nam"]
