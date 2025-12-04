"""Data manager: persistence, duplicate detection, run stats, logging hooks."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

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
            run_uuid TEXT,
            started_at TEXT,
            ended_at TEXT,
            sources_attempted TEXT,
            errors TEXT,
            stats TEXT,
            search_input_json TEXT,
            search_fingerprint TEXT,
            segments_json TEXT
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_uuid TEXT,
            run_uuid TEXT,
            run_id INTEGER,
            segment_key TEXT,
            segment_level TEXT,
            unique_key TEXT,
            times_seen INTEGER DEFAULT 1,
            first_seen_run_id TEXT,
            last_seen_run_id TEXT,
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
    _ensure_column(conn, "runs", "run_uuid", "TEXT")
    _ensure_column(conn, "runs", "search_input_json", "TEXT")
    _ensure_column(conn, "runs", "search_fingerprint", "TEXT")
    _ensure_column(conn, "runs", "segments_json", "TEXT")
    _ensure_column(conn, "leads", "lead_uuid", "TEXT")
    _ensure_column(conn, "leads", "run_uuid", "TEXT")
    _ensure_column(conn, "leads", "segment_key", "TEXT")
    _ensure_column(conn, "leads", "segment_level", "TEXT")
    _ensure_column(conn, "leads", "unique_key", "TEXT")
    _ensure_column(conn, "leads", "times_seen", "INTEGER DEFAULT 1")
    _ensure_column(conn, "leads", "first_seen_run_id", "TEXT")
    _ensure_column(conn, "leads", "last_seen_run_id", "TEXT")
    _ensure_unique(conn, "leads", "uq_leads_unique_key", "unique_key")
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
        """
        INSERT INTO runs (
            run_uuid, started_at, ended_at, sources_attempted, errors, stats,
            search_input_json, search_fingerprint, segments_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            metadata.run_id,
            metadata.start_time,
            metadata.end_time,
            json.dumps(metadata.sources_attempted),
            json.dumps(metadata.errors),
            json.dumps(metadata.stats),
            metadata.search_input_json,
            metadata.search_fingerprint,
            metadata.segments_json,
        ),
    )
    run_id = cur.lastrowid

    saved_rows = 0
    for scored in leads:
        lead: LeadCandidate = scored.lead
        unique_key = _lead_unique_key(lead)
        lead.unique_key = unique_key
        if lead.first_seen_run_id is None:
            lead.first_seen_run_id = metadata.run_id
        lead.last_seen_run_id = metadata.run_id

        params = (
            lead.lead_id,
            metadata.run_id,
            run_id,
            lead.segment_key,
            lead.segment_level,
            unique_key,
            lead.times_seen,
            lead.first_seen_run_id,
            lead.last_seen_run_id,
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
        )

        if unique_key:
            cur.execute(
                """
                INSERT INTO leads (
                    lead_uuid, run_uuid, run_id, segment_key, segment_level, unique_key,
                    times_seen, first_seen_run_id, last_seen_run_id,
                    company_name, website, phone, email, address, category,
                    contact_name, contact_title, confidence, source_url, source,
                    score, rationale, captured_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(unique_key) DO UPDATE SET
                    times_seen = leads.times_seen + 1,
                    last_seen_run_id = excluded.last_seen_run_id,
                    company_name = COALESCE(excluded.company_name, leads.company_name),
                    website = COALESCE(excluded.website, leads.website),
                    phone = COALESCE(excluded.phone, leads.phone),
                    email = COALESCE(excluded.email, leads.email),
                    address = COALESCE(excluded.address, leads.address),
                    category = COALESCE(excluded.category, leads.category),
                    contact_name = COALESCE(excluded.contact_name, leads.contact_name),
                    contact_title = COALESCE(excluded.contact_title, leads.contact_title),
                    confidence = COALESCE(excluded.confidence, leads.confidence),
                    source_url = COALESCE(excluded.source_url, leads.source_url),
                    source = COALESCE(excluded.source, leads.source),
                    score = excluded.score,
                    rationale = excluded.rationale,
                    captured_at = excluded.captured_at
                """
                ,
                params,
            )
        else:
            cur.execute(
                """
                INSERT INTO leads (
                    lead_uuid, run_uuid, run_id, segment_key, segment_level, unique_key,
                    times_seen, first_seen_run_id, last_seen_run_id,
                    company_name, website, phone, email, address, category,
                    contact_name, contact_title, confidence, source_url, source,
                    score, rationale, captured_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
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


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl_type: str) -> None:
    """Add column if missing; safe for older DBs."""
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cur.fetchall()}
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")
        conn.commit()


def _ensure_unique(conn: sqlite3.Connection, table: str, index_name: str, column: str) -> None:
    cur = conn.cursor()
    cur.execute("PRAGMA index_list({})".format(table))
    existing = {row[1] for row in cur.fetchall()}
    if index_name not in existing:
        cur.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table}({column})")
        conn.commit()


def _lead_unique_key(lead: LeadCandidate) -> Optional[str]:
    """Generate a normalized uniqueness key for DB upsert."""
    if lead.email:
        return f"email:{lead.email.lower()}"
    if lead.phone:
        digits = re.sub(r"\\D", "", lead.phone)
        if digits:
            return f"phone:{digits}"
    if lead.website:
        normalized_site = lead.website.lower().rstrip("/")
        return f"web:{normalized_site}"
    if lead.source_url:
        parsed = urlparse(lead.source_url)
        path = parsed.path.rstrip("/")
        return f"src:{parsed.netloc.lower()}{path}"
    return None
