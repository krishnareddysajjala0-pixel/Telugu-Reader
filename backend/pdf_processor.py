import os
import pymupdf
from typing import Dict, Any, List, Tuple
from backend import database, llm_service, tts_service

def is_telugu_text(text: str) -> bool:
    """Checks if text contains Telugu Unicode characters (U+0C00 to U+0C7F)."""
    return any('\u0C00' <= char <= '\u0C7F' for char in text)

def is_legacy_font(text: str) -> bool:
    """
    Detects legacy Telugu DTP fonts (Anu Script, Shree Lipi, Modular).
    These PDFs have text, but almost 0% Telugu Unicode,
    and contain dense clusters of glyph codes like '=∂#= rq`« „áê^è•#º`«'.
    """
    if not text or len(text.strip()) < 10:
        return False
    telugu_chars = sum(1 for c in text if '\u0C00' <= c <= '\u0C7F')
    # If genuine Telugu Unicode characters are present in significant numbers, it's not legacy
    if telugu_chars > 20:
        return False
    # Signature characters abundant in Anu/Shree legacy ASCII encodings
    legacy_glyphs = set("„ãÑÖÅÜÕ^~°áê∂`=Q+*&{}|<>[]/\\_…‡‰´˙ˇ†")
    matches = sum(1 for c in text if c in legacy_glyphs)
    return matches >= 10

def ocr_single_page(filepath: str, page_number: int) -> str:
    """
    Renders a single PDF page to an image and transcribes it to Telugu Unicode using Gemini Vision.
    """
    if not llm_service.has_api_key():
        return ""
    try:
        doc = pymupdf.open(filepath)
        if 1 <= page_number <= len(doc):
            page = doc[page_number - 1]
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("jpeg")
            doc.close()
            return llm_service.extract_telugu_ocr_from_image(img_bytes)
        doc.close()
    except Exception as e:
        print(f"Error in ocr_single_page: {e}")
    return ""

def process_txt(filepath: str, filename: str) -> Dict[str, Any]:
    """
    Reads a Telugu text file (.txt), segments it into logical pages (~1500 chars),
    generates summary and topics via Gemini, and stores it in SQLite.
    """
    content = ""
    for enc in ["utf-8", "utf-8-sig", "utf-16", "cp1252", "latin-1"]:
        try:
            with open(filepath, "r", encoding=enc) as f:
                content = f.read()
            break
        except Exception:
            continue
            
    content = content.strip()
    if not content:
        raise ValueError(f"{filename} లో టెక్స్ట్ కనుగొనబడలేదు (Empty text file)")
        
    file_size = os.path.getsize(filepath)
    
    # Split into logical pages of ~1500 characters respecting paragraphs
    paragraphs = content.split("\n\n")
    pages_data = []
    current_page = []
    current_len = 0
    page_num = 1
    
    for para in paragraphs:
        p_clean = para.strip()
        if not p_clean:
            continue
        if current_len + len(p_clean) > 1500 and current_page:
            pages_data.append({
                "page_number": page_num,
                "page_text": "\n\n".join(current_page),
                "is_ocr": 1
            })
            page_num += 1
            current_page = [p_clean]
            current_len = len(p_clean)
        else:
            current_page.append(p_clean)
            current_len += len(p_clean)
            
    if current_page:
        pages_data.append({
            "page_number": page_num,
            "page_text": "\n\n".join(current_page),
            "is_ocr": 1
        })
        
    page_count = len(pages_data)
    full_text = "\n\n".join([f"--- పేజీ {p['page_number']} ---\n{p['page_text']}" for p in pages_data])
    
    # Generate summary & topics
    summary, topics = llm_service.summarize_document(filename, full_text)
    
    # Save to SQLite database
    doc_id = database.save_document(
        filename=filename,
        filepath=filepath,
        file_size=file_size,
        page_count=page_count,
        full_text=full_text,
        pages=pages_data,
        summary=summary,
        key_topics=topics
    )
    
    # Pre-generate TTS audio for summary
    summary_audio_url = None
    if summary:
        try:
            summary_audio_url = tts_service.generate_telugu_audio(summary, lang="te")
        except Exception as e:
            print(f"Error pre-generating summary audio for txt: {e}")
            
    return {
        "id": doc_id,
        "filename": filename,
        "file_size": file_size,
        "page_count": page_count,
        "summary": summary,
        "key_topics": topics,
        "summary_audio_url": summary_audio_url,
        "pages": pages_data,
        "is_legacy_font": False
    }

def process_pdf(filepath: str, filename: str, force_ocr: bool = False) -> Dict[str, Any]:
    """
    Extracts text from PDF, executes OCR on scanned/unreadable or legacy font pages,
    summarizes the Telugu content, and stores it in SQLite.
    """
    doc = pymupdf.open(filepath)
    page_count = len(doc)
    pages_data = []
    full_text_parts = []
    
    can_ocr = llm_service.has_api_key()
    
    # Check sample page to detect if entire PDF uses legacy DTP font
    is_doc_legacy_font = False
    for sample_idx in range(min(5, page_count)):
        sample_text = doc[sample_idx].get_text("text").strip()
        if is_legacy_font(sample_text):
            is_doc_legacy_font = True
            break
            
    print(f"[*] Processing {filename} ({page_count} pages) | Legacy Font Detected: {is_doc_legacy_font}")
    
    for page_idx in range(page_count):
        page = doc[page_idx]
        extracted_text = page.get_text("text").strip()
        is_ocr = False
        clean_extracted = extracted_text.replace(" ", "").replace("\n", "")
        
        # Determine if this page needs OCR:
        # 1. Scanned page (very scarce text < 30 chars)
        # 2. Or force_ocr is enabled
        # 3. Or it's a legacy font PDF and within the first 6 pages (for instant accurate book summary)
        page_is_legacy = is_legacy_font(extracted_text)
        needs_ocr = (len(clean_extracted) < 30) or force_ocr or (page_is_legacy and page_idx < 6)
        
        if needs_ocr and can_ocr:
            try:
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("jpeg")
                ocr_text = llm_service.extract_telugu_ocr_from_image(img_bytes)
                if ocr_text:
                    extracted_text = ocr_text
                    is_ocr = True
            except Exception as e:
                print(f"Error doing OCR on page {page_idx + 1}: {e}")
                
        pages_data.append({
            "page_number": page_idx + 1,
            "page_text": extracted_text,
            "is_ocr": is_ocr
        })
        full_text_parts.append(f"--- పేజీ {page_idx + 1} ---\n{extracted_text}")
    
    doc.close()
    
    full_text = "\n\n".join(full_text_parts)
    file_size = os.path.getsize(filepath)
    
    # Generate summary & topics
    summary, topics = llm_service.summarize_document(filename, full_text)
    
    # Save to SQLite database
    doc_id = database.save_document(
        filename=filename,
        filepath=filepath,
        file_size=file_size,
        page_count=page_count,
        full_text=full_text,
        pages=pages_data,
        summary=summary,
        key_topics=topics
    )
    
    # Pre-generate TTS audio for the summary if summary is available
    summary_audio_url = None
    if summary:
        try:
            summary_audio_url = tts_service.generate_telugu_audio(summary, lang="te")
        except Exception as e:
            print(f"Error pre-generating summary audio: {e}")
            
    # If the document uses legacy fonts or force_ocr was requested, auto-trigger full conversion in background!
    if (is_doc_legacy_font or force_ocr) and can_ocr:
        trigger_background_conversion(doc_id)
            
    return {
        "id": doc_id,
        "filename": filename,
        "file_size": file_size,
        "page_count": page_count,
        "summary": summary,
        "key_topics": topics,
        "summary_audio_url": summary_audio_url,
        "pages": pages_data,
        "is_legacy_font": is_doc_legacy_font
    }

import threading
import time

active_conversions = set()

def convert_whole_pdf_background(doc_id: int):
    """
    Background worker that converts all remaining pages of doc_id
    into genuine Telugu Unicode using Gemini Vision OCR page-by-page.
    """
    if doc_id in active_conversions:
        return
    active_conversions.add(doc_id)
    
    try:
        doc = database.get_document(doc_id)
        if not doc or not llm_service.has_api_key():
            return
            
        unconverted = database.get_unconverted_pages(doc_id)
        print(f"[OCR Worker] Starting full conversion for doc {doc_id} ({len(unconverted)} pages to convert)")
        
        for p_num in unconverted:
            try:
                converted_text = ocr_single_page(doc["filepath"], p_num)
                if converted_text:
                    database.update_page_text(doc_id, p_num, converted_text)
                    print(f"[OCR Worker] Doc {doc_id} - Page {p_num} converted to clean Telugu.")
                time.sleep(1.5) # respectful rate pacing
            except Exception as page_err:
                print(f"[OCR Worker] Doc {doc_id} - Error on page {p_num}: {page_err}")
                time.sleep(3.0)
                
        # Update full_text and regenerate comprehensive summary
        database.update_document_full_text(doc_id)
        updated_doc = database.get_document(doc_id)
        summary, topics = llm_service.summarize_document(updated_doc["filename"], updated_doc["full_text"])
        database.update_document_summary(doc_id, summary, topics)
        tts_service.generate_telugu_audio(summary, lang="te")
        print(f"[OCR Worker] Doc {doc_id} - All pages converted & summarized in Telugu!")
    finally:
        active_conversions.discard(doc_id)

def trigger_background_conversion(doc_id: int):
    t = threading.Thread(target=convert_whole_pdf_background, args=(doc_id,), daemon=True)
    t.start()

def is_doc_converting(doc_id: int) -> bool:
    return doc_id in active_conversions
