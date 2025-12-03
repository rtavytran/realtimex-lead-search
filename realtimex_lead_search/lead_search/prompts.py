"""Prompt templates for extraction and scoring."""

from typing import Dict


def get_prompts() -> Dict[str, str]:
    return {
        "extract_company": (
            "Extract company/contact details from the provided page text. "
            "Return JSON with fields: company_name, website, phone, email, "
            "address, category, contact_name, contact_title, source_url."
        ),
        "score_lead": (
            "Given a lead with fields (company_name, vertical, location, category, email, phone), "
            "produce a numeric score 0-1 and a short rationale."
        ),
    }
