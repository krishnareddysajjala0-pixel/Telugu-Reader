# తెలుగు PDF సహాయకుడు (Telugu PDF AI Assistant)

A fullstack web application designed specifically for **Telugu PDF documents**. It reads, analyzes, extracts, and answers questions using **Voice (Speech-to-Text)** or **Text**, speaks answers aloud in natural Telugu **(Text-to-Speech)**, and **remembers all uploaded PDFs across sessions**.

---

## 🌟 Key Features

1. **Telugu PDF Extraction & Scanned Document OCR**:
   - Reads digital Telugu Unicode PDFs directly using PyMuPDF.
   - For scanned PDFs or non-standard legacy Telugu fonts, it uses **Gemini Vision OCR** to transcribe Telugu text faithfully.
   - View extracted text page by page in the built-in Document Reader.

2. **Voice & Text Q&A in Telugu**:
   - Ask questions by typing in Telugu or speaking through the microphone using the **Web Speech API (`te-IN`)**.
   - Answers are generated using **Gemini 2.5 Flash** in clear, polite, and fluent Telugu.

3. **Read Aloud (Telugu Text-to-Speech)**:
   - High-quality native Telugu audio generation via **gTTS**.
   - Listen to the document summary, read any page aloud, or automatically listen to AI answers.

4. **Persistent Memory & Document Library**:
   - All uploaded PDFs, page text, summaries, and conversation history are saved in a local SQLite database (`data/telugu_rag.db`).
   - Switch between **"అన్ని PDFలు (All Documents)"** to query across your entire library, or focus on a specific document.

5. **Local & Easy to Configure**:
   - Paste your free Google Gemini API key right inside the app's **Settings (సెట్టింగ్స్)** modal or put it in a `.env` file.

---

## 🚀 Quick Start

### 1. Requirements
Ensure Python 3.10+ is installed. Dependencies are listed in `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 2. Launch the Application
Run the launcher script:
```bash
python run.py
```
This will automatically launch the FastAPI server and open your browser at `http://127.0.0.1:8000`.

### 3. Setup Gemini API Key
- Click the **సెట్టింగ్స్ (Settings)** icon in the top right.
- Paste your Gemini API key (obtainable for free from [Google AI Studio](https://aistudio.google.com/)).
- Click **సేవ్ చేయండి (Save)**.

---

## 📁 Project Structure

```text
telugu-pdf-rag/
├── backend/
│   ├── database.py       # SQLite database layer for documents, pages, chat & settings
│   ├── llm_service.py    # Gemini LLM integration for Telugu Q&A, summaries & OCR
│   ├── pdf_processor.py  # PyMuPDF extractor and scanned document OCR pipeline
│   ├── tts_service.py    # Telugu Text-to-Speech (gTTS) audio synthesizer and cache
│   └── main.py           # FastAPI backend server and REST API endpoints
├── frontend/
│   ├── index.html        # Modern responsive Telugu UI (Tailwind CSS & Lucide icons)
│   └── static/
│       ├── app.js        # State, Web Speech voice input, audio player, & chat logic
│       └── style.css     # Custom Telugu typography and mic recording animations
├── data/
│   ├── uploads/          # Saved PDF documents
│   ├── audio/            # Generated Telugu audio cache (.mp3)
│   └── telugu_rag.db     # SQLite persistent database
├── run.py                # One-click launcher with automatic browser opening
└── requirements.txt      # Python dependencies
```
