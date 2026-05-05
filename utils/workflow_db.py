"""
Workflow Intelligence database layer.

Manages SQLite persistence for visitor feedback concerns, backlog candidates,
and the admin activity log. Mirrors the pattern used in guestbook_db.py.
"""
import sqlite3
import os
import uuid
from datetime import datetime

DB_DIR = os.path.join("data", "db")
DB_PATH = os.path.join(DB_DIR, "workflow.db")

def get_connection():
    """Return a sqlite3 connection, creating the DB directory if needed."""
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create all tables if they do not already exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS feedback_concerns (
            id TEXT PRIMARY KEY,
            original_quote TEXT,
            concern_category TEXT,
            workflow_stage TEXT,
            affected_role TEXT,
            likely_root_cause TEXT,
            existing_tool_match TEXT,
            status TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS backlog_candidates (
            id TEXT PRIMARY KEY,
            title TEXT,
            problem TEXT,
            original_evidence TEXT,
            workflow_stage TEXT,
            user_group TEXT,
            existing_tool_check TEXT,
            hypothesized_root_causes TEXT,
            impact TEXT,
            risk TEXT,
            suggested_validation TEXT,
            potential_mvp TEXT,
            acceptance_criteria TEXT,
            status TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS activity_log (
            id TEXT PRIMARY KEY,
            action TEXT,
            concern_id TEXT,
            note TEXT,
            timestamp TEXT
        );
    ''')
    conn.commit()
    conn.close()

def insert_concern(concern_data: dict, original_quote: str) -> str:
    """Persist a new concern and return its UUID."""
    conn = get_connection()
    cursor = conn.cursor()
    concern_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO feedback_concerns (
            id, original_quote, concern_category, workflow_stage, 
            affected_role, likely_root_cause, existing_tool_match, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        concern_id,
        original_quote,
        concern_data.get("category", ""),
        concern_data.get("workflow_stage", ""),
        concern_data.get("affected_role", ""),
        concern_data.get("root_cause", ""),
        concern_data.get("tool_match", ""),
        "unresolved",
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()
    return concern_id

def get_unresolved_concerns() -> list[dict]:
    """Return all concerns with status 'unresolved', newest first."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM feedback_concerns WHERE status = 'unresolved' ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_concerns() -> list[dict]:
    """Return all concerns regardless of status, newest first."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM feedback_concerns ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def log_activity(action, concern_id, note=""):
    """Logs an action to the activity_log table."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO activity_log (id, action, concern_id, note, timestamp) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), action, concern_id, note, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def mark_concern_resolved(concern_id: str) -> None:
    """Mark a concern as solved and log the action."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE feedback_concerns SET status = 'solved' WHERE id = ?", (concern_id,))
    conn.commit()
    conn.close()
    log_activity("solved", concern_id, "Manually marked as solved by Admin.")

def discard_concern(concern_id: str, reason: str = "") -> None:
    """Mark a concern as discarded with an optional reason and log the action."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE feedback_concerns SET status = 'discarded' WHERE id = ?", (concern_id,))
    conn.commit()
    conn.close()
    log_activity("discarded", concern_id, reason or "Discarded by Admin.")

def mark_concern_accepted(concern_id: str, backlog_id: str) -> None:
    """Mark a concern as accepted to the backlog and log the link."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE feedback_concerns SET status = 'accepted_to_backlog' WHERE id = ?", (concern_id,))
    conn.commit()
    conn.close()
    log_activity("accepted_to_backlog", concern_id, f"Linked to backlog candidate {backlog_id[:8]}.")

def get_activity_log() -> list[dict]:
    """Return all audit log entries joined with their source concern, newest first."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT al.*, fc.original_quote, fc.concern_category
        FROM activity_log al
        LEFT JOIN feedback_concerns fc ON al.concern_id = fc.id
        ORDER BY al.timestamp DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def insert_backlog_candidate(candidate_data: dict) -> str:
    """Persist a new backlog candidate and return its UUID."""
    conn = get_connection()
    cursor = conn.cursor()
    candidate_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO backlog_candidates (
            id, title, problem, original_evidence, workflow_stage, 
            user_group, existing_tool_check, hypothesized_root_causes, 
            impact, risk, suggested_validation, potential_mvp, 
            acceptance_criteria, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        candidate_id,
        candidate_data.get("title", ""),
        candidate_data.get("problem", ""),
        candidate_data.get("original_evidence", ""),
        candidate_data.get("workflow_stage", ""),
        candidate_data.get("user_group", ""),
        candidate_data.get("existing_tool_check", ""),
        candidate_data.get("hypothesized_root_causes", ""),
        candidate_data.get("impact", ""),
        candidate_data.get("risk", ""),
        candidate_data.get("suggested_validation", ""),
        candidate_data.get("potential_mvp", ""),
        candidate_data.get("acceptance_criteria", ""),
        "draft",
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()
    return candidate_id

def get_backlog_candidates() -> list[dict]:
    """Return all backlog candidates, newest first."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM backlog_candidates ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
