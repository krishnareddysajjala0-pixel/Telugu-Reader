import os
import shutil
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import database, pdf_processor, llm_service, tts_service

app = FastAPI(title="తెలుగు PDF విశ్లేషకుడు (Telugu PDF AI Assistant)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
STATIC_DIR = os.path.join(FRONTEND_DIR, "static")

if os.environ.get("VERCEL"):
    DATA_DIR = "/tmp"
    UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
    AUDIO_DIR = os.path.join(DATA_DIR, "audio")
else:
    DATA_DIR = os.path.join(BASE_DIR, "data")
    UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
    AUDIO_DIR = os.path.join(DATA_DIR, "audio")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# Helper functions to find frontend assets in serverless runtimes
def get_frontend_file_path(filename: str) -> Optional[str]:
    candidates = [
        os.path.join(FRONTEND_DIR, filename),
        os.path.join(os.getcwd(), "frontend", filename),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", filename),
        os.path.join("/var/task/frontend", filename)
    ]
    for p in candidates:
        if os.path.exists(p) and os.path.isfile(p):
            return p
    return None

def get_static_file_path(filename: str) -> Optional[str]:
    candidates = [
        os.path.join(STATIC_DIR, filename),
        os.path.join(os.getcwd(), "frontend", "static", filename),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "static", filename),
        os.path.join("/var/task/frontend/static", filename)
    ]
    for p in candidates:
        if os.path.exists(p) and os.path.isfile(p):
            return p
    return None

# Middleware to seamlessly normalize any Vercel proxy / rewrite prefixes
@app.middleware("http")
async def normalize_vercel_paths(request: Request, call_next):
    path = request.scope.get("path", "")
    if path in ("/api/index.py", "/api/index", "/api/index.py/", "/api/index/"):
        request.scope["path"] = "/"
    elif path.startswith("/api/index.py/"):
        request.scope["path"] = path[len("/api/index.py"):]
    elif path.startswith("/api/index/"):
        request.scope["path"] = path[len("/api/index"):]
    return await call_next(request)

# Initialize database schema
database.init_db()

# Mount static folders
app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Request Models
class ChatRequest(BaseModel):
    query: str
    doc_id: Optional[int] = None
    generate_speech: bool = True

class TTSRequest(BaseModel):
    text: str
    lang: Optional[str] = "te"

class ReadAloudRequest(BaseModel):
    page_number: Optional[int] = None
    mode: Optional[str] = "page"

class SettingsRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    voice_lang: Optional[str] = "te-IN"

# Endpoints
@app.get("/")
@app.get("/api")
@app.get("/api/")
@app.get("/api/index")
@app.get("/api/index.py")
@app.get("/index.html")
def get_index():
    index_path = get_frontend_file_path("index.html")
    if index_path and os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    return {"message": "Telugu PDF Assistant Backend is running."}

@app.get("/static/{file_path:path}")
def serve_static(file_path: str):
    static_file = get_static_file_path(file_path)
    if static_file and os.path.exists(static_file):
        media_type = "text/javascript" if file_path.endswith(".js") else ("text/css" if file_path.endswith(".css") else None)
        return FileResponse(static_file, media_type=media_type)
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/api/settings")
def get_settings():
    has_key = llm_service.has_api_key()
    api_key_val = database.get_setting("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")
    masked_key = ""
    if api_key_val:
        masked_key = api_key_val[:4] + "..." + api_key_val[-4:] if len(api_key_val) > 8 else "***"
    return {
        "has_api_key": has_key,
        "masked_api_key": masked_key,
        "voice_lang": database.get_setting("voice_lang", "te-IN")
    }

@app.post("/api/settings")
def update_settings(req: SettingsRequest):
    if req.gemini_api_key is not None and req.gemini_api_key.strip():
        database.set_setting("gemini_api_key", req.gemini_api_key.strip())
    if req.voice_lang is not None:
        database.set_setting("voice_lang", req.voice_lang)
    return {"status": "success", "has_api_key": llm_service.has_api_key()}

@app.get("/api/documents")
def list_documents():
    docs = database.get_all_documents()
    enhanced = []
    for d in docs:
        status = database.get_document_conversion_status(d["id"])
        is_converting = pdf_processor.is_doc_converting(d["id"])
        item = dict(d)
        item["conversion"] = status
        item["is_converting"] = is_converting
        enhanced.append(item)
    return {"documents": enhanced}

@app.post("/api/documents/{doc_id}/convert-all")
def start_full_conversion(doc_id: int):
    doc = database.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    pdf_processor.trigger_background_conversion(doc_id)
    return {"status": "started", "doc_id": doc_id, "message": "పూర్తి PDF తెలుగులోకి మారుతోంది (Conversion started)"}

@app.get("/api/documents/{doc_id}/conversion-status")
def get_conversion_status(doc_id: int):
    status = database.get_document_conversion_status(doc_id)
    status["is_converting"] = pdf_processor.is_doc_converting(doc_id)
    return status

@app.get("/api/documents/{doc_id}")
def get_document_details(doc_id: int):
    doc = database.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc["conversion"] = database.get_document_conversion_status(doc_id)
    doc["is_converting"] = pdf_processor.is_doc_converting(doc_id)
    return {"document": doc}

@app.post("/api/documents/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    force_ocr: bool = Form(False)
):
    processed = []
    errors = []
    
    for file in files:
        fname_lower = file.filename.lower()
        if not (fname_lower.endswith(".pdf") or fname_lower.endswith(".txt")):
            errors.append(f"{file.filename}: కేవలం PDF మరియు Text (.txt) ఫైల్స్ మాత్రమే అంగీకరించబడతాయి.")
            continue
            
        safe_filename = file.filename.replace(" ", "_")
        dest_path = os.path.join(UPLOAD_DIR, safe_filename)
        
        # Save file to disk
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        try:
            if fname_lower.endswith(".txt"):
                doc_data = pdf_processor.process_txt(dest_path, file.filename)
            else:
                doc_data = pdf_processor.process_pdf(dest_path, file.filename, force_ocr=force_ocr)
            processed.append(doc_data)
        except Exception as e:
            errors.append(f"{file.filename}: ప్రాసెస్ చేయడంలో లోపం - {str(e)}")
            
    return {
        "status": "success" if processed else "failed",
        "processed": processed,
        "errors": errors
    }

@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: int):
    success = database.delete_document(doc_id)
    return {"status": "success" if success else "failed"}

@app.post("/api/documents/{doc_id}/reanalyze")
def reanalyze_document(doc_id: int):
    doc = database.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    summary, topics = llm_service.summarize_document(doc["filename"], doc["full_text"])
    database.update_document_summary(doc_id, summary, topics)
    return {"status": "success", "summary": summary, "topics": topics}

@app.post("/api/documents/{doc_id}/ocr-page")
def ocr_document_page(doc_id: int, page_number: int = Form(...)):
    doc = database.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    ocr_text = pdf_processor.ocr_single_page(doc["filepath"], page_number)
    if ocr_text:
        database.update_page_text(doc_id, page_number, ocr_text)
        return {"status": "success", "page_number": page_number, "page_text": ocr_text}
    return {"status": "failed", "detail": "OCR could not transcribe page"}

@app.post("/api/documents/{doc_id}/read")
def read_document_aloud(
    doc_id: int,
    req: Optional[ReadAloudRequest] = None
):
    """
    Synthesizes Telugu audio for a document's actual content, a specific page, or its summary.
    If the page uses a legacy non-Unicode font, it automatically converts it to clean Telugu via AI OCR!
    """
    doc = database.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    mode = req.mode if (req and req.mode) else "content"
    page_number = req.page_number if req else None
    
    text_to_read = ""
    target_page_num = page_number or 1
    
    if mode == "page" and page_number is not None:
        target_page_num = page_number
        matching = [p for p in doc["pages"] if p["page_number"] == page_number]
        if matching:
            text_to_read = matching[0]["page_text"]
    elif mode == "summary" and doc["summary"] and "API Key" not in doc["summary"]:
        text_to_read = doc["summary"]
    else:
        # Default content mode: read requested page or page 1
        target_page_num = page_number or 1
        matching = [p for p in doc["pages"] if p["page_number"] == target_page_num]
        if matching:
            text_to_read = matching[0]["page_text"]
            # If the selected page is very short, add next page
            target_idx = target_page_num - 1
            if len(text_to_read) < 200 and len(doc["pages"]) > target_idx + 1:
                text_to_read += "\n\n" + doc["pages"][target_idx + 1]["page_text"]
        else:
            text_to_read = doc["full_text"][:1500]

    # If the text is legacy font garbled ASCII or placeholder, auto-OCR this exact page on the fly with Gemini Vision!
    if pdf_processor.is_legacy_font(text_to_read) or "[ఈ పేజీని AI" in text_to_read or not text_to_read.strip():
        try:
            converted = pdf_processor.ocr_single_page(doc["filepath"], target_page_num)
            if converted:
                text_to_read = converted
                database.update_page_text(doc_id, target_page_num, converted)
        except Exception as e:
            print(f"Error auto-converting legacy page {target_page_num}: {e}")
        
    if not text_to_read or "[ఈ పేజీని AI" in text_to_read:
        text_to_read = f"{doc['filename']} లోని పేజీ {target_page_num} లో చదవడానికి సరిపడా టెక్స్ట్ కనుగొనబడలేదు."
        
    audio_url = tts_service.generate_telugu_audio(text_to_read, lang="te")
    return {
        "status": "success",
        "doc_id": doc_id,
        "mode": mode,
        "page_number": target_page_num,
        "text": text_to_read,
        "audio_url": audio_url
    }

@app.post("/api/chat")
def chat(req: ChatRequest):
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
        
    # Gather context documents
    context_docs = []
    if req.doc_id is not None:
        target_doc = database.get_document(req.doc_id)
        if target_doc:
            context_docs.append(target_doc)
    else:
        # User is querying across all uploaded documents
        all_docs = database.get_all_documents()
        for doc_item in all_docs:
            full_d = database.get_document(doc_item["id"])
            if full_d:
                context_docs.append(full_d)
                
    if not context_docs:
        answer = "ప్రస్తుతం ఏ తెలుగు PDF పత్రాలు అప్‌లోడ్ చేయబడలేదు. దయచేసి ఎడమవైపు నుండి ఒక PDF ని అప్‌లోడ్ చేసి ప్రశ్నలు అడగండి."
        audio_url = tts_service.generate_telugu_audio(answer) if req.generate_speech else None
        database.add_chat_message(role="user", content=query, doc_id=req.doc_id)
        database.add_chat_message(role="assistant", content=answer, doc_id=req.doc_id, audio_url=audio_url)
        return {
            "answer": answer,
            "audio_url": audio_url,
            "sources": []
        }
        
    # Get previous chat history
    history = database.get_chat_history(doc_id=req.doc_id, limit=6)
    
    # Save user message
    database.add_chat_message(role="user", content=query, doc_id=req.doc_id)
    
    # Generate LLM answer in Telugu with multi-doc / multi-page citations
    llm_result = llm_service.answer_telugu_query(query, context_docs, history)
    answer = llm_result.get("answer", "")
    sources = llm_result.get("sources", [])
    
    # Generate Telugu audio speech for the answer
    audio_url = None
    if req.generate_speech and answer:
        try:
            audio_url = tts_service.generate_telugu_audio(answer, lang="te")
        except Exception as e:
            print(f"Error synthesizing answer speech: {e}")
            
    # Save assistant message with sources
    database.add_chat_message(role="assistant", content=answer, doc_id=req.doc_id, audio_url=audio_url, sources=sources)
    
    return {
        "answer": answer,
        "audio_url": audio_url,
        "sources": sources
    }

@app.get("/api/chat/history")
def get_chat_history(doc_id: Optional[int] = None):
    messages = database.get_chat_history(doc_id=doc_id, limit=50)
    return {"messages": messages}

@app.post("/api/chat/clear")
def clear_chat(doc_id: Optional[int] = None):
    database.clear_chat_history(doc_id=doc_id)
    return {"status": "success"}

@app.post("/api/tts")
def text_to_speech(req: TTSRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    audio_url = tts_service.generate_telugu_audio(req.text, lang=req.lang or "te")
    return {"audio_url": audio_url}
