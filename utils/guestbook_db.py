import sqlite3
import os
import uuid
from datetime import datetime

DB_DIR = os.path.join("data", "db")
DB_PATH = os.path.join(DB_DIR, "guestbook.db")

def get_connection():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tables as proposed
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            title TEXT,
            status TEXT
        );

        CREATE TABLE IF NOT EXISTS document_versions (
            id TEXT PRIMARY KEY,
            document_id TEXT,
            content_markdown TEXT,
            created_by TEXT,
            created_at TEXT,
            is_live BOOLEAN,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );

        CREATE TABLE IF NOT EXISTS change_requests (
            id TEXT PRIMARY KEY,
            document_id TEXT,
            base_version_id TEXT,
            proposed_version_id TEXT,
            created_by TEXT,
            status TEXT,
            assigned_reviewer_id TEXT,
            merged_by TEXT,
            merged_at TEXT,
            FOREIGN KEY (document_id) REFERENCES documents(id),
            FOREIGN KEY (base_version_id) REFERENCES document_versions(id),
            FOREIGN KEY (proposed_version_id) REFERENCES document_versions(id)
        );

        CREATE TABLE IF NOT EXISTS change_comments (
            id TEXT PRIMARY KEY,
            change_request_id TEXT,
            line_range TEXT,
            comment_text TEXT,
            author_id TEXT,
            FOREIGN KEY (change_request_id) REFERENCES change_requests(id)
        );
        
        CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY,
            action TEXT,
            user_id TEXT,
            target_id TEXT,
            timestamp TEXT
        );
    ''')
    conn.commit()
    conn.close()

def log_audit(action, user_id, target_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO audit_log (id, action, user_id, target_id, timestamp) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), action, user_id, target_id, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def create_change_request(document_id, original_content, proposed_content, user_id):
    """Creates a new change request with the original and proposed versions."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Ensure document exists
    cursor.execute("SELECT id FROM documents WHERE id = ?", (document_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO documents (id, title, status) VALUES (?, ?, ?)",
                       (document_id, document_id, "active"))
    
    # 2. Create Base Version
    base_version_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO document_versions (id, document_id, content_markdown, created_by, created_at, is_live)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (base_version_id, document_id, original_content, "system", datetime.now().isoformat(), True))
    
    # 3. Create Proposed Version
    proposed_version_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO document_versions (id, document_id, content_markdown, created_by, created_at, is_live)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (proposed_version_id, document_id, proposed_content, user_id, datetime.now().isoformat(), False))
    
    # 4. Create Change Request
    request_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO change_requests (id, document_id, base_version_id, proposed_version_id, created_by, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (request_id, document_id, base_version_id, proposed_version_id, user_id, "in_review"))
    
    conn.commit()
    conn.close()
    
    log_audit("create_request", user_id, request_id)
    return request_id

def get_open_change_requests():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT cr.id, cr.document_id, cr.created_by, cr.status, 
               v_base.content_markdown as base_content, 
               v_prop.content_markdown as proposed_content
        FROM change_requests cr
        JOIN document_versions v_base ON cr.base_version_id = v_base.id
        JOIN document_versions v_prop ON cr.proposed_version_id = v_prop.id
        WHERE cr.status = 'in_review'
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_change_request_status(request_id, status, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    if status == 'merged':
        cursor.execute("UPDATE change_requests SET status = ?, merged_by = ?, merged_at = ? WHERE id = ?",
                       (status, user_id, datetime.now().isoformat(), request_id))
    else:
        cursor.execute("UPDATE change_requests SET status = ? WHERE id = ?", (status, request_id))
        
    conn.commit()
    conn.close()
    
    log_audit(f"update_request_{status}", user_id, request_id)
