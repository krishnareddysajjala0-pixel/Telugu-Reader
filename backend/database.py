import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Any

if os.environ.get("VERCEL"):
    DB_PATH = "/tmp/telugu_rag.db"
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "telugu_rag.db")

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    
    # Documents table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        filepath TEXT NOT NULL,
        file_size INTEGER DEFAULT 0,
        page_count INTEGER DEFAULT 0,
        full_text TEXT DEFAULT '',
        summary TEXT DEFAULT '',
        key_topics TEXT DEFAULT '[]',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Document pages table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS document_pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER NOT NULL,
        page_number INTEGER NOT NULL,
        page_text TEXT DEFAULT '',
        is_ocr INTEGER DEFAULT 0,
        FOREIGN KEY (doc_id) REFERENCES documents (id) ON DELETE CASCADE
    )
    """)
    
    # Chat history table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        audio_url TEXT,
        sources TEXT DEFAULT '[]',
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (doc_id) REFERENCES documents (id) ON DELETE SET NULL
    )
    """)
    
    # Ensure sources column exists if table was created previously
    cursor.execute("PRAGMA table_info(chat_messages)")
    columns = [col[1] for col in cursor.fetchall()]
    if "sources" not in columns:
        cursor.execute("ALTER TABLE chat_messages ADD COLUMN sources TEXT DEFAULT '[]'")
    
    conn.commit()
    conn.close()

# Ensure tables exist upon module import
init_db()

# Settings Helpers
def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row['value']
    # Fallback to environment variable
    return os.environ.get(key.upper(), default)

def set_setting(key: str, value: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

# Document Helpers
def save_document(filename: str, filepath: str, file_size: int, page_count: int, full_text: str, pages: List[Dict[str, Any]], summary: str = "", key_topics: List[str] = None) -> int:
    conn = get_db()
    cursor = conn.cursor()
    topics_json = json.dumps(key_topics or [], ensure_ascii=False)
    
    cursor.execute("""
    INSERT INTO documents (filename, filepath, file_size, page_count, full_text, summary, key_topics)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (filename, filepath, file_size, page_count, full_text, summary, topics_json))
    
    doc_id = cursor.lastrowid
    
    for page in pages:
        cursor.execute("""
        INSERT INTO document_pages (doc_id, page_number, page_text, is_ocr)
        VALUES (?, ?, ?, ?)
        """, (doc_id, page["page_number"], page["page_text"], 1 if page.get("is_ocr") else 0))
        
    conn.commit()
    conn.close()
    return doc_id

def update_page_text(doc_id: int, page_number: int, page_text: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE document_pages 
    SET page_text = ?, is_ocr = 1 
    WHERE doc_id = ? AND page_number = ?
    """, (page_text, doc_id, page_number))
    conn.commit()
    conn.close()

def update_document_full_text(doc_id: int):
    """Rebuilds full_text from document_pages and updates documents table."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT page_number, page_text FROM document_pages WHERE doc_id = ? ORDER BY page_number ASC", (doc_id,))
    pages = cursor.fetchall()
    full_text_parts = [f"--- పేజీ {p['page_number']} ---\n{p['page_text']}" for p in pages if p['page_text']]
    full_text = "\n\n".join(full_text_parts)
    cursor.execute("UPDATE documents SET full_text = ? WHERE id = ?", (full_text, doc_id))
    conn.commit()
    conn.close()

def get_unconverted_pages(doc_id: int) -> List[int]:
    """Returns list of page numbers that are not yet OCR converted."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT page_number FROM document_pages WHERE doc_id = ? AND is_ocr = 0 ORDER BY page_number ASC", (doc_id,))
    rows = cursor.fetchall()
    conn.close()
    return [r["page_number"] for r in rows]

def get_document_conversion_status(doc_id: int) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total FROM document_pages WHERE doc_id = ?", (doc_id,))
    total = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) as converted FROM document_pages WHERE doc_id = ? AND is_ocr = 1", (doc_id,))
    converted = cursor.fetchone()["converted"]
    conn.close()
    return {
        "doc_id": doc_id,
        "total_pages": total,
        "converted_pages": converted,
        "is_complete": total > 0 and converted == total
    }

def update_document_summary(doc_id: int, summary: str, key_topics: List[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    topics_json = json.dumps(key_topics or [], ensure_ascii=False)
    cursor.execute("UPDATE documents SET summary = ?, key_topics = ? WHERE id = ?", (summary, topics_json, doc_id))
    conn.commit()
    conn.close()

def get_all_documents() -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, filename, filepath, file_size, page_count, summary, key_topics, created_at FROM documents ORDER BY created_at DESC")
    rows = cursor.fetchall()
    docs = []
    for r in rows:
        docs.append({
            "id": r["id"],
            "filename": r["filename"],
            "filepath": r["filepath"],
            "file_size": r["file_size"],
            "page_count": r["page_count"],
            "summary": r["summary"],
            "key_topics": json.loads(r["key_topics"]) if r["key_topics"] else [],
            "created_at": r["created_at"]
        })
    conn.close()
    return docs

def is_legacy_font_text(text: str) -> bool:
    if not text or len(text.strip()) < 10:
        return False
    telugu_chars = sum(1 for c in text if '\u0C00' <= c <= '\u0C7F')
    if telugu_chars > 20:
        return False
    legacy_glyphs = set("„ãÑÖÅÜÕ^~°áê∂`=Q+*&{}|<>[]_…‡‰´˙ˇ†")
    return sum(1 for c in text if c in legacy_glyphs) >= 10

def get_document(doc_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    
    cursor.execute("SELECT page_number, page_text, is_ocr FROM document_pages WHERE doc_id = ? ORDER BY page_number ASC", (doc_id,))
    page_rows = cursor.fetchall()
    pages = []
    for p in page_rows:
        raw = p["page_text"]
        is_ocr = bool(p["is_ocr"])
        is_legacy = not is_ocr and is_legacy_font_text(raw)
        # Never display garbled legacy font gibberish to user
        display_text = raw
        if is_legacy:
            display_text = "⏳ [ఈ పేజీని AI స్వచ్ఛమైన తెలుగులోకి మారుస్తోంది... దయచేసి వేచి ఉండండి లేదా 'వెంటనే మార్చండి' బటన్ నొక్కండి]"
            
        pages.append({
            "page_number": p["page_number"], 
            "page_text": display_text, 
            "is_ocr": is_ocr,
            "is_legacy": is_legacy
        })
    
    doc = {
        "id": row["id"],
        "filename": row["filename"],
        "filepath": row["filepath"],
        "file_size": row["file_size"],
        "page_count": row["page_count"],
        "full_text": row["full_text"],
        "summary": row["summary"],
        "key_topics": json.loads(row["key_topics"]) if row["key_topics"] else [],
        "created_at": row["created_at"],
        "pages": pages
    }
    conn.close()
    return doc

def delete_document(doc_id: int) -> bool:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT filepath FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    if row and os.path.exists(row["filepath"]):
        try:
            os.remove(row["filepath"])
        except Exception:
            pass
            
    cursor.execute("DELETE FROM document_pages WHERE doc_id = ?", (doc_id,))
    cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    cursor.execute("DELETE FROM chat_messages WHERE doc_id = ?", (doc_id,))
    conn.commit()
    conn.close()
    return True

# Chat History Helpers
def add_chat_message(role: str, content: str, doc_id: Optional[int] = None, audio_url: Optional[str] = None, sources: Optional[List[Dict[str, Any]]] = None) -> int:
    conn = get_db()
    cursor = conn.cursor()
    sources_json = json.dumps(sources or [], ensure_ascii=False)
    cursor.execute("""
    INSERT INTO chat_messages (doc_id, role, content, audio_url, sources)
    VALUES (?, ?, ?, ?, ?)
    """, (doc_id, role, content, audio_url, sources_json))
    msg_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return msg_id

def get_chat_history(doc_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    if doc_id is not None:
        cursor.execute("""
        SELECT cm.*, d.filename as doc_name 
        FROM chat_messages cm 
        LEFT JOIN documents d ON cm.doc_id = d.id 
        WHERE cm.doc_id = ? 
        ORDER BY cm.timestamp ASC LIMIT ?
        """, (doc_id, limit))
    else:
        cursor.execute("""
        SELECT cm.*, d.filename as doc_name 
        FROM chat_messages cm 
        LEFT JOIN documents d ON cm.doc_id = d.id 
        ORDER BY cm.timestamp ASC LIMIT ?
        """, (limit,))
        
    rows = cursor.fetchall()
    messages = []
    for r in rows:
        sources_val = []
        try:
            if "sources" in r.keys() and r["sources"]:
                sources_val = json.loads(r["sources"])
        except Exception:
            sources_val = []
            
        messages.append({
            "id": r["id"],
            "doc_id": r["doc_id"],
            "doc_name": r["doc_name"],
            "role": r["role"],
            "content": r["content"],
            "audio_url": r["audio_url"],
            "sources": sources_val,
            "timestamp": r["timestamp"]
        })
    conn.close()
    return messages

def clear_chat_history(doc_id: Optional[int] = None):
    conn = get_db()
    cursor = conn.cursor()
    if doc_id is not None:
        cursor.execute("DELETE FROM chat_messages WHERE doc_id = ?", (doc_id,))
    else:
        cursor.execute("DELETE FROM chat_messages")
    conn.commit()
    conn.close()
