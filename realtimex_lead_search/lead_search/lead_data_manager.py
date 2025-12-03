"""Data manager: persistence, duplicate detection, run stats, logging hooks."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import List, Optional

from .models import LeadCandidate, PersistenceResult, RunMetadata, ScoredLead


def ensure_db(db_path: str) -> None:
    """Create SQLite schema if missing."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT,
            ended_at TEXT,
            sources_attempted TEXT,
            errors TEXT,
            stats TEXT
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            company_name TEXT,
            website TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            category TEXT,
            contact_name TEXT,
            contact_title TEXT,
            confidence REAL,
            source_url TEXT,
            source TEXT,
            score REAL,
            rationale TEXT,
            captured_at TEXT,
            FOREIGN KEY(run_id) REFERENCES runs(id)
        );
        """
    )
    conn.commit()
    conn.close()


def persist(
    leads: List[ScoredLead],
    metadata: RunMetadata,
    db_path: str,
    json_export: bool = False,
    json_path: Optional[str] = None,
) -> PersistenceResult:
    """Persist leads and run metadata to SQLite and optional JSON."""
    ensure_db(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO runs (started_at, ended_at, sources_attempted, errors, stats) VALUES (?, ?, ?, ?, ?)",
        (
            metadata.start_time,
            metadata.end_time,
            json.dumps(metadata.sources_attempted),
            json.dumps(metadata.errors),
            json.dumps(metadata.stats),
        ),
    )
    run_id = cur.lastrowid

    saved_rows = 0
    for scored in leads:
        lead: LeadCandidate = scored.lead
        cur.execute(
            """
            INSERT INTO leads (
                run_id, company_name, website, phone, email, address, category,
                contact_name, contact_title, confidence, source_url, source, score, rationale, captured_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                lead.company_name,
                lead.website,
                lead.phone,
                lead.email,
                lead.address,
                lead.category,
                lead.contact_name,
                lead.contact_title,
                lead.confidence,
                lead.source_url,
                lead.source,
                scored.score,
                scored.rationale,
                lead.captured_at,
            ),
        )
        saved_rows += 1

    conn.commit()
    conn.close()

    json_output_path = None
    if json_export:
        json_output_path = json_path or os.path.join(os.path.dirname(db_path), "leads.json")
        Path(json_output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(json_output_path, "w", encoding="utf-8") as f:
            json.dump([_scored_to_dict(s) for s in leads], f, ensure_ascii=False, indent=2)

    return PersistenceResult(saved_rows=saved_rows, db_path=db_path, json_path=json_output_path)


def _scored_to_dict(scored: ScoredLead):
    data = scored.lead.__dict__.copy()
    data["score"] = scored.score
    data["rationale"] = scored.rationale
    return data
