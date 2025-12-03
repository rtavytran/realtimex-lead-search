import json
import os
from pathlib import Path

from realtimex_lead_search.lead_search import lead_data_manager
from realtimex_lead_search.lead_search.models import LeadCandidate, RunMetadata, ScoredLead


def test_persist_creates_db_and_json(tmp_path: Path):
    db_path = tmp_path / "lead_search.db"
    json_path = tmp_path / "leads.json"
    metadata = RunMetadata()
    lead = LeadCandidate(company_name="Test Co", email="a@test.com", phone="123")
    scored = [ScoredLead(lead=lead, score=0.8, rationale="test")]

    result = lead_data_manager.persist(
        scored, metadata, db_path=str(db_path), json_export=True, json_path=str(json_path)
    )

    assert result.db_path == str(db_path)
    assert result.json_path == str(json_path)
    assert db_path.exists()
    assert json_path.exists()

    data = json.loads(json_path.read_text())
    assert data[0]["company_name"] == "Test Co"
