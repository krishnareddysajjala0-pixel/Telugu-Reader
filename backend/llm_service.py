import os
import json
from typing import List, Dict, Any, Optional, Tuple
from google import genai
from google.genai import types
from backend import database

DEFAULT_MODELS = [
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest"
]
DEFAULT_MODEL = "gemini-3.7-flash"

def get_api_key() -> Optional[str]:
    # Check SQLite settings first, then env variable
    key = database.get_setting("gemini_api_key")
    if not key or not key.strip():
        key = os.environ.get("GEMINI_API_KEY", "")
    return key.strip() if key else None

def get_gemini_client() -> Optional[genai.Client]:
    api_key = get_api_key()
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        print(f"Error creating Gemini client: {e}")
        return None

def has_api_key() -> bool:
    return bool(get_api_key())

def extract_telugu_ocr_from_image(image_bytes: bytes) -> str:
    """
    Uses Gemini Vision to read scanned or non-Unicode Telugu PDF pages.
    """
    client = get_gemini_client()
    if not client:
        return ""
    
    prompt = (
        "You are an expert Telugu document OCR engine. Carefully transcribe all the Telugu text "
        "and English text from this document image exactly as it appears. Preserve headings, paragraphs, "
        "tables, numbers, and bullet points. Output ONLY the transcribed text in Unicode Telugu script."
    )
    
    try:
        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=[prompt, image_part],
            config=types.GenerateContentConfig(
                temperature=0.1,
            )
        )
        return response.text.strip() if response.text else ""
    except Exception as e:
        print(f"Error during Gemini OCR: {e}")
        return ""

def summarize_document(filename: str, full_text: str) -> Tuple[str, List[str]]:
    """
    Summarizes document content in Telugu and generates 3-5 key topics.
    """
    client = get_gemini_client()
    if not client:
        # Fallback local summary if no API key
        preview = full_text[:300].strip()
        fallback_summary = f"{filename} డాక్యుమెంట్ విజయవంతంగా అప్‌లోడ్ చేయబడింది. పూర్తి విశ్లేషణ కోసం దయచేసి మీ Gemini API Key ని సెట్టింగ్స్‌లో నమోదు చేయండి."
        return fallback_summary, ["Telugu PDF", "Document Upload"]
    
    # Truncate if extremely long (Gemini 2.5 Flash handles ~1M tokens, but safe chunking is good)
    doc_snippet = full_text[:40000]
    
    prompt = f"""
డాక్యుమెంట్ పేరు: {filename}
క్రింది తెలుగు డాక్యుమెంట్ పాఠాన్ని విశ్లేషించి:
1. డాక్యుమెంట్‌లో ఉన్న ముఖ్యమైన సమాచారాన్ని సంగ్రహంగా 3-5 వాక్యాలలో చక్కని తెలుగులో సారాంశం (Summary) ఇవ్వండి.
2. డాక్యుమెంట్‌లో చర్చించిన 3 నుండి 5 ముఖ్యమైన అంశాలను (Key Topics / Keywords) ఇవ్వండి.

దయచేసి ఖచ్చితమైన JSON ఆకృతిలో మాత్రమే సమాధానం ఇవ్వండి:
{{
  "summary": "తెలుగులో స్పష్టమైన సారాంశం...",
  "topics": ["అంశం 1", "అంశం 2", "అంశం 3"]
}}

డాక్యుమెంట్ పాఠం:
{doc_snippet}
"""
    for model_name in DEFAULT_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json"
                )
            )
            data = json.loads(response.text)
            return data.get("summary", ""), data.get("topics", [])
        except Exception as e:
            print(f"Error summarizing document with {model_name}: {e}")
            continue
            
    # Fallback to direct extraction if json failed
    return f"{filename} పత్రం లోడ్ చేయబడింది. ప్రశ్నలను అడగవచ్చు.", ["PDF Document"]

def answer_telugu_query(
    query: str, 
    context_docs: List[Dict[str, Any]], 
    chat_history: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Answers user's query in Telugu and provides detailed citations/references:
    which PDF, which page, and the exact content snippet.
    If related data exists in multiple PDFs, includes all of them.
    """
    client = get_gemini_client()
    if not client:
        return {
            "answer": (
                "⚠️ **Gemini API Key సెట్ చేయబడలేదు.**\n\n"
                "దయచేసి పైభాగంలో ఉన్న **సెట్టింగ్స్ (Settings)** ఐకాన్ క్లిక్ చేసి మీ ఉచిత Google Gemini API Key ని ఎంటర్ చేయండి.\n"
                "మీరు [Google AI Studio](https://aistudio.google.com/) నుండి ఉచితంగా API Key పొందవచ్చు."
            ),
            "sources": []
        }
    
    # Prepare structured context with clear Doc ID, Name, and Page tags
    context_str = ""
    # Map for easy lookup
    doc_map = {}
    for idx, doc in enumerate(context_docs, 1):
        d_id = doc.get("id", idx)
        d_name = doc.get("filename", f"Doc_{idx}")
        doc_map[d_id] = d_name
        
        context_str += f"\n======================================================\n"
        context_str += f"డాక్యుమెంట్ [DOC_ID: {d_id}] - ఫైల్ పేరు: {d_name}\n"
        if doc.get("summary"):
            context_str += f"సారాంశం: {doc['summary']}\n"
        context_str += f"======================================================\n"
        
        if "pages" in doc and doc["pages"]:
            for p in doc["pages"]:
                p_num = p.get("page_number", 1)
                p_text = p.get("page_text", "").strip()
                if p_text:
                    context_str += f"[డాక్యుమెంట్: {d_name} | DOC_ID: {d_id} | పేజీ నంబర్: {p_num}]:\n{p_text}\n\n"
        else:
            context_str += f"[డాక్యుమెంట్: {d_name} | DOC_ID: {d_id} | పూర్తి పాఠం]:\n{doc.get('full_text', '')}\n\n"

    # Format history
    history_str = ""
    if chat_history:
        recent = chat_history[-6:]
        for msg in recent:
            role = "యూజర్" if msg.get("role") == "user" else "సహాయకుడు"
            history_str += f"{role}: {msg.get('content', '')}\n"

    system_instruction = (
        "మీరు తెలుగు భాషా పత్రాల విశ్లేషణలో నిపుణుడైన AI సహాయకుడు (Telugu PDF Assistant).\n"
        "మీరు అందించే సమాధానం సమగ్రంగా, ఖచ్చితంగా మరియు ఆధారాలతో (Citations & References) కూడి ఉండాలి.\n\n"
        "ముఖ్యమైన నిబంధనలు:\n"
        "1. యూజర్ అడిగిన ప్రశ్నకు డాక్యుమెంట్లలోని సమాచారం ఆధారంగా చక్కని తెలుగులో స్పష్టమైన సమాధానం ఇవ్వండి.\n"
        "2. సంబంధిత సమాచారం ఒకటి కంటే ఎక్కువ PDFలలో లేదా బహుళ పేజీలలో ఉంటే, వాటన్నింటిని పరిశీలించి సమగ్ర సమాధానం ఇవ్వాలి.\n"
        "3. ఖచ్చితంగా ప్రతి ఆధారానికి (Reference):\n"
        "   - ఏ డాక్యుమెంట్ (doc_name మరియు doc_id)\n"
        "   - ఏ పేజీ నంబర్ (page_number)\n"
        "   - ఆ పేజీలోని సంబంధిత వాక్యం లేదా పేరాగ్రాఫ్ (snippet - exact text from the document)\n"
        "   - అది ప్రశ్నకు ఎలా సంబంధం కలిగి ఉందో (relevance)\n"
        "   వీటిని 'sources' జాబితాలో వివరంగా ఇవ్వాలి.\n"
        "4. సమాధానాన్ని ఎల్లప్పుడూ క్రింది JSON ఆకృతిలో మాత్రమే ఇవ్వాలి:\n"
        "{\n"
        '  "answer": "తెలుగులో పూర్తి సమాధానం...",\n'
        '  "sources": [\n'
        '    {\n'
        '      "doc_id": 1,\n'
        '      "doc_name": "filename.pdf",\n'
        '      "page_number": 2,\n'
        '      "snippet": "పేజీ నుండి తీసుకున్న వాస్తవ సమాచారం...",\n'
        '      "relevance": "సంబంధిత వివరణ..."\n'
        '    }\n'
        '  ]\n'
        "}"
    )

    prompt = f"""
అందుబాటులో ఉన్న డాక్యుమెంట్లు మరియు పేజీల సమాచారం (Context Documents):
{context_str}

గత సంభాషణ (Conversation History):
{history_str}

యూజర్ ప్రశ్న:
{query}

దయచేసి JSON ఆకృతిలో సమాధానం మరియు అన్ని ఆధారాలు (References) ఇవ్వండి:
"""

    for model_name in DEFAULT_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2,
                    response_mime_type="application/json"
                )
            )
            
            parsed = json.loads(response.text)
            answer = parsed.get("answer", "")
            sources = parsed.get("sources", [])
            
            # Ensure sources have doc_name
            for s in sources:
                if not s.get("doc_name") and s.get("doc_id") in doc_map:
                    s["doc_name"] = doc_map[s["doc_id"]]
                    
            return {
                "answer": answer,
                "sources": sources
            }
        except Exception as e:
            print(f"Error calling Gemini in JSON mode with {model_name}: {e}")
            continue
            
    # Fallback to direct text if JSON parsing or all models failed
    try:
        raw_resp = client.models.generate_content(
            model=DEFAULT_MODELS[0],
            contents=prompt
        )
        raw_text = raw_resp.text.strip()
        fallback_sources = find_fallback_sources(query, context_docs)
        return {
            "answer": raw_text,
            "sources": fallback_sources
        }
    except Exception as err:
        return {
            "answer": f"క్షమించండి, ప్రశ్నను విశ్లేషించడంలో లోపం ఎదురైంది: {str(err)}",
            "sources": []
        }

def find_fallback_sources(query: str, context_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Heuristic keyword matching to find pages containing query terms if JSON fails."""
    sources = []
    keywords = [w for w in query.replace("?", "").replace(",", "").split() if len(w) > 3]
    for doc in context_docs:
        pages = doc.get("pages", [])
        for p in pages:
            text = p.get("page_text", "")
            matches = [k for k in keywords if k in text]
            if matches:
                # Find snippet around the first match
                idx = text.find(matches[0])
                start = max(0, idx - 60)
                end = min(len(text), idx + 140)
                snippet = text[start:end].strip()
                sources.append({
                    "doc_id": doc.get("id"),
                    "doc_name": doc.get("filename"),
                    "page_number": p.get("page_number", 1),
                    "snippet": f"...{snippet}...",
                    "relevance": f"కీలకపదాలు: {', '.join(matches)}"
                })
                if len(sources) >= 5:
                    break
    return sources
