import os
import sys
import json
import pymupdf

# Set project root in path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient
from backend import database, pdf_processor, llm_service, tts_service
from backend.main import app

def run_tests():
    print("=" * 65)
    print("   STARTING TELUGU PDF MULTI-DOC & CITATIONS TEST SUITE")
    print("=" * 65)
    
    # 1. Clean test DB
    print("\n[Step 1] Initializing and resetting database...")
    database.init_db()
    for d in database.get_all_documents():
        database.delete_document(d["id"])
    database.clear_chat_history()
    print("✔ Database reset successfully.")

    # Font path for Telugu Unicode embedding
    font_path = "C:/Windows/Fonts/Nirmala.ttc"
    if not os.path.exists(font_path):
        font_path = None

    # 2. Create Sample PDF 1: Telangana Rythu Bandhu (2 pages)
    os.makedirs("data", exist_ok=True)
    pdf1_path = os.path.join("data", "telangana_rythu_bandhu.pdf")
    doc1 = pymupdf.open()
    
    page1_1 = doc1.new_page()
    page1_1.insert_text(
        (50, 72), 
        "రైతు బంధు పథకం: తెలంగాణ ప్రభుత్వం వ్యవసాయ పెట్టుబడి సహాయం కింద ప్రతి ఎకరానికి ఏడాదికి రూ. 10,000 అందిస్తుంది.",
        fontfile=font_path,
        fontname="nirmala" if font_path else None
    )
    
    page1_2 = doc1.new_page()
    page1_2.insert_text(
        (50, 72), 
        "అర్హతలు: పట్టాదారు పాసుపుస్తకం కలిగిన రైతులు అందరూ అర్హులు. ఆధార్ కార్డు, బ్యాంకు ఖాతా తప్పనిసరి.",
        fontfile=font_path,
        fontname="nirmala" if font_path else None
    )
    
    doc1.save(pdf1_path)
    doc1.close()
    print(f"✔ Created PDF 1: {pdf1_path} (2 pages with Telugu Unicode font)")

    # 3. Create Sample PDF 2: AP Rythu Bharosa (2 pages)
    pdf2_path = os.path.join("data", "ap_rythu_bharosa.pdf")
    doc2 = pymupdf.open()
    
    page2_1 = doc2.new_page()
    page2_1.insert_text(
        (50, 72), 
        "రైతు భరోసా పథకం: ఆంధ్రప్రదేశ్ ప్రభుత్వం రైతులకు పెట్టుబడి సాయంగా ఏడాదికి రూ. 13,500 అందిస్తుంది.",
        fontfile=font_path,
        fontname="nirmala" if font_path else None
    )
    
    page2_2 = doc2.new_page()
    page2_2.insert_text(
        (50, 72), 
        "షరతులు: కౌలు రైతులకు కూడా ఈ పథకం వర్తిస్తుంది. మే నెలలో మొదటి విడత నిధులు విడుదల చేస్తారు.",
        fontfile=font_path,
        fontname="nirmala" if font_path else None
    )
    
    doc2.save(pdf2_path)
    doc2.close()
    print(f"✔ Created PDF 2: {pdf2_path} (2 pages with Telugu Unicode font)")

    # 4. Ingest and Process both PDFs
    print("\n[Step 2] Processing both Telugu PDFs...")
    res1 = pdf_processor.process_pdf(pdf1_path, "telangana_rythu_bandhu.pdf")
    res2 = pdf_processor.process_pdf(pdf2_path, "ap_rythu_bharosa.pdf")
    print(f"✔ PDF 1 ingested: ID={res1['id']}, Pages={res1['page_count']}")
    print(f"✔ PDF 2 ingested: ID={res2['id']}, Pages={res2['page_count']}")

    # 5. Verify database storage
    docs = database.get_all_documents()
    assert len(docs) == 2, f"Expected 2 documents, found {len(docs)}"
    print(f"✔ Saved documents verified in SQLite: {[d['filename'] for d in docs]}")

    # 6. Test Multi-Document Cross-Referencing & Sources
    print("\n[Step 3] Testing Multi-Doc Cross-Reference Search...")
    full_doc1 = database.get_document(res1["id"])
    full_doc2 = database.get_document(res2["id"])
    all_context = [full_doc1, full_doc2]

    # Test keyword matching across multiple documents
    test_query = "రైతు పెట్టుబడి సాయం"
    sources = llm_service.find_fallback_sources(test_query, all_context)
    print(f"✔ Sources found across multiple PDFs: {len(sources)}")
    for s in sources:
        print(f"   ↳ Document: {s['doc_name']} | Page: {s['page_number']}")
        print(f"     Content: {s['snippet']}")

    assert len(sources) >= 2, f"Expected at least 2 matching sources across both PDFs, got {len(sources)}"
    doc_names_found = {s["doc_name"] for s in sources}
    assert "telangana_rythu_bandhu.pdf" in doc_names_found, "telangana_rythu_bandhu.pdf missing from sources"
    assert "ap_rythu_bharosa.pdf" in doc_names_found, "ap_rythu_bharosa.pdf missing from sources"
    print("✔ Successfully identified relevant pages and content snippets in BOTH PDFs!")

    # 7. Test Text-to-Speech (gTTS)
    print("\n[Step 4] Testing Telugu Text-to-Speech (TTS)...")
    sample_text = "తెలంగాణలో రైతు బంధు రూ. 10,000 మరియు ఆంధ్రప్రదేశ్‌లో రైతు భరోసా రూ. 13,500."
    audio_url = tts_service.generate_telugu_audio(sample_text)
    assert audio_url is not None and audio_url.startswith("/audio/"), "Audio URL invalid"
    audio_full_path = os.path.join(PROJECT_ROOT, "data", "audio", os.path.basename(audio_url))
    assert os.path.exists(audio_full_path) and os.path.getsize(audio_full_path) > 1000, "Audio file not created properly"
    print(f"✔ Telugu Audio generated: {audio_url} ({os.path.getsize(audio_full_path)} bytes)")

    # 8. Test FastAPI Endpoints with TestClient
    print("\n[Step 5] Testing Web API Endpoints with TestClient...")
    client = TestClient(app)
    
    # 8a. Test documents list
    resp = client.get("/api/documents")
    assert resp.status_code == 200
    assert len(resp.json()["documents"]) == 2
    print("✔ GET /api/documents passed")

    # 8b. Test single document with pages
    resp = client.get(f"/api/documents/{res1['id']}")
    assert resp.status_code == 200
    doc_detail = resp.json()["document"]
    assert len(doc_detail["pages"]) == 2
    print("✔ GET /api/documents/{id} passed (pages verified)")

    # 8c. Test read page aloud endpoint
    resp = client.post(f"/api/documents/{res1['id']}/read", json={"mode": "page", "page_number": 1})
    assert resp.status_code == 200
    assert resp.json()["audio_url"] is not None
    print(f"✔ POST /api/documents/{{id}}/read passed (Audio: {resp.json()['audio_url']})")

    # 8d. Test chat endpoint with multi-document question
    chat_resp = client.post("/api/chat", json={
        "query": test_query,
        "doc_id": None, # All documents
        "generate_speech": True
    })
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    print("✔ POST /api/chat passed")
    print(f"   ↳ Answer preview: {chat_data['answer'][:80]}...")
    print(f"   ↳ Sources count: {len(chat_data['sources'])}")
    print(f"   ↳ Audio response URL: {chat_data['audio_url']}")

    # 8e. Test chat history persistence with sources
    hist_resp = client.get("/api/chat/history")
    assert hist_resp.status_code == 200
    messages = hist_resp.json()["messages"]
    assert len(messages) >= 2 # user + assistant
    last_assistant_msg = [m for m in messages if m["role"] == "assistant"][-1]
    print(f"✔ GET /api/chat/history passed (Saved messages: {len(messages)})")
    print(f"   ↳ Persisted sources in message: {len(last_assistant_msg.get('sources', []))}")

    print("\n" + "=" * 65)
    print("🎉 ALL TESTS PASSED SUCCESSFULLY! 100% VERIFIED!")
    print("=" * 65)

if __name__ == "__main__":
    run_tests()
