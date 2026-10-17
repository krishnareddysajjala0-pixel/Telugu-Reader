import os
import sys
import webbrowser
import threading
import time

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import uvicorn

def open_browser():
    time.sleep(1.5)
    url = "http://127.0.0.1:8000"
    print(f"\n[+] Opening Telugu PDF Assistant in your browser: {url}")
    webbrowser.open(url)

if __name__ == "__main__":
    project_dir = os.path.dirname(os.path.abspath(__file__))
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)
        
    print("=" * 65)
    print("   Telugu PDF AI Assistant (తెలుగు PDF సహాయకుడు)")
    print("   - Voice & Text Q&A in Telugu")
    print("   - PDF Reader with Telugu Text-To-Speech (TTS)")
    print("   - Scanned PDF Vision OCR")
    print("   - Persistent Memory & Library")
    print("   Server running at: http://127.0.0.1:8000")
    print("=" * 65)
    
    # Launch browser in a background thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run FastAPI server
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
