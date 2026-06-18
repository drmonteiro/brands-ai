"""LinkedIn URL extraction from discovery text."""

from services.discovery_prefill import extract_linkedin_from_text


def test_prefers_person_profile_over_company():
    text = """
    Visit us at https://www.linkedin.com/company/sartoria-vienna
    Owner: https://linkedin.com/in/johndoe
    """
    assert extract_linkedin_from_text(text) == "https://linkedin.com/in/johndoe"


def test_company_when_no_person():
    text = "Follow https://www.linkedin.com/company/knize-vienna"
    assert extract_linkedin_from_text(text) == "https://www.linkedin.com/company/knize-vienna"
