// Application State
let activeDocId = null; // null = all documents
let documentsList = [];
let isRecording = false;
let speechRecognition = null;
let currentPlayingAudioUrl = null;

// Initialize when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
    initVoiceRecognition();
    fetchSettings();
    fetchDocuments();
    fetchChatHistory();
    setupDropzone();
});

// ----------------------------------------------------
// Settings & API Status
// ----------------------------------------------------
async function fetchSettings() {
    try {
        const res = await fetch("/api/settings");
        const data = await res.json();
        const pill = document.getElementById("api-status-pill");
        const text = document.getElementById("api-status-text");
        
        if (data.has_api_key) {
            pill.className = "flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 cursor-pointer";
            text.textContent = "Gemini AI సిద్ధంగా ఉంది";
        } else {
            pill.className = "flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 cursor-pointer";
            text.textContent = "Gemini API Key నమోదు చేయండి";
        }

        if (data.voice_lang) {
            const langSelect = document.getElementById("voice-lang-select");
            if (langSelect) langSelect.value = data.voice_lang;
        }
    } catch (err) {
        console.error("Error fetching settings:", err);
    }
}

function openSettingsModal() {
    document.getElementById("settings-modal").classList.remove("hidden");
}

function closeSettingsModal() {
    document.getElementById("settings-modal").classList.add("hidden");
}

async function saveSettings() {
    const key = document.getElementById("gemini-key-input").value.trim();
    const lang = document.getElementById("voice-lang-select").value;
    
    try {
        const payload = { voice_lang: lang };
        if (key) payload.gemini_api_key = key;

        const res = await fetch("/api/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            closeSettingsModal();
            fetchSettings();
            alert("సెట్టింగ్స్ విజయవంతంగా సేవ్ చేయబడ్డాయి!");
        } else {
            alert("సెట్టింగ్స్ సేవ్ చేయడంలో లోపం ఎదురైంది.");
        }
    } catch (err) {
        console.error("Error saving settings:", err);
    }
}

// ----------------------------------------------------
// Document Management & Uploads
// ----------------------------------------------------
function setupDropzone() {
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("file-input");

    dropzone.addEventListener("click", () => fileInput.click());

    dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("border-brand-500", "bg-brand-50");
    });

    dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("border-brand-500", "bg-brand-50");
    });

    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("border-brand-500", "bg-brand-50");
        if (e.dataTransfer.files.length) {
            handleFileUpload(e.dataTransfer.files);
        }
    });

    fileInput.addEventListener("change", () => {
        if (fileInput.files.length) {
            handleFileUpload(fileInput.files);
            fileInput.value = "";
        }
    });
}

async function handleFileUpload(files) {
    const progressDiv = document.getElementById("upload-progress");
    const statusText = document.getElementById("upload-status-text");
    const forceOcr = document.getElementById("force-ocr-checkbox").checked;

    progressDiv.classList.remove("hidden");
    statusText.textContent = `${files.length} PDF(s) ప్రాసెస్ అవుతున్నాయి...`;

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        formData.append("files", files[i]);
    }
    formData.append("force_ocr", forceOcr ? "true" : "false");

    try {
        const res = await fetch("/api/documents/upload", {
            method: "POST",
            body: formData
        });
        const data = await res.json();

        if (data.errors && data.errors.length) {
            alert("కొన్ని లోపాలు సంభవించాయి:\n" + data.errors.join("\n"));
        }

        await fetchDocuments();
        
        // If a new doc was uploaded, select it
        if (data.processed && data.processed.length > 0) {
            selectScope(data.processed[0].id);
        }
    } catch (err) {
        console.error("Upload error:", err);
        alert("PDF అప్‌లోడ్ చేయడంలో లోపం ఎదురైంది.");
    } finally {
        progressDiv.classList.add("hidden");
    }
}

async function fetchDocuments() {
    try {
        const res = await fetch("/api/documents");
        const data = await res.json();
        documentsList = data.documents || [];
        renderDocumentsList();
    } catch (err) {
        console.error("Error fetching docs:", err);
    }
}

function renderDocumentsList() {
    const container = document.getElementById("documents-list");
    const countBadge = document.getElementById("doc-count-badge");
    const noDocsMsg = document.getElementById("no-docs-msg");

    countBadge.textContent = documentsList.length;

    if (documentsList.length === 0) {
        container.innerHTML = "";
        container.appendChild(noDocsMsg);
        noDocsMsg.classList.remove("hidden");
        return;
    }

    container.innerHTML = "";
    documentsList.forEach(doc => {
        const isActive = activeDocId === doc.id;
        const card = document.createElement("div");
        card.className = `p-3.5 rounded-xl border transition-all duration-200 cursor-pointer ${
            isActive 
                ? "border-brand-500 bg-brand-50/50 shadow-sm" 
                : "border-slate-200 hover:border-slate-300 bg-white"
        }`;
        card.onclick = () => selectScope(doc.id);

        const fileSizeMB = (doc.file_size / (1024 * 1024)).toFixed(1);

        let conversionBadge = '';
        if (doc.conversion) {
            if (doc.is_converting) {
                const percent = Math.round((doc.conversion.converted_pages / (doc.conversion.total_pages || 1)) * 100);
                conversionBadge = `
                    <div class="mt-2 p-2 rounded-lg bg-purple-50 border border-purple-200">
                        <div class="flex items-center justify-between text-[11px] text-purple-800 font-bold mb-1">
                            <span class="flex items-center gap-1.5">
                                <div class="w-3 h-3 border-2 border-purple-600 border-t-transparent rounded-full animate-spin"></div>
                                AI OCR మార్పు: ${doc.conversion.converted_pages}/${doc.conversion.total_pages}
                            </span>
                            <span>${percent}%</span>
                        </div>
                        <div class="w-full bg-purple-200 h-1.5 rounded-full overflow-hidden">
                            <div class="bg-purple-600 h-full transition-all duration-300" style="width: ${percent}%"></div>
                        </div>
                    </div>
                `;
            } else if (doc.conversion.converted_pages < doc.conversion.total_pages && doc.conversion.converted_pages > 0) {
                conversionBadge = `
                    <div class="mt-2 flex items-center justify-between gap-1 text-[10px] text-amber-800 bg-amber-50 p-1.5 rounded-lg border border-amber-200">
                        <span>మార్చబడింది: ${doc.conversion.converted_pages}/${doc.conversion.total_pages} పేజీలు</span>
                        <button onclick="event.stopPropagation(); startFullConversion(${doc.id})" class="px-2 py-0.5 rounded bg-purple-600 hover:bg-purple-700 text-white font-bold transition-colors">
                            పూర్తి PDF మార్చండి
                        </button>
                    </div>
                `;
            } else if (doc.conversion.is_complete) {
                conversionBadge = `
                    <div class="mt-1.5 text-[10px] text-emerald-700 flex items-center gap-1 font-medium">
                        <i data-lucide="check-circle" class="w-3 h-3 text-emerald-600"></i>
                        <span>స్వచ్ఛమైన తెలుగు (100% Clean Telugu)</span>
                    </div>
                `;
            }
        }
        
        card.innerHTML = `
            <div class="flex items-start justify-between gap-2">
                <div class="flex items-center gap-2 overflow-hidden">
                    <div class="w-8 h-8 rounded-lg bg-red-50 text-red-600 flex items-center justify-center flex-shrink-0">
                        <i data-lucide="file-text" class="w-4 h-4"></i>
                    </div>
                    <div class="truncate">
                        <h4 class="text-xs font-bold text-slate-800 truncate" title="${doc.filename}">${doc.filename}</h4>
                        <div class="flex items-center gap-2 text-[10px] text-slate-400 mt-0.5">
                            <span>${doc.page_count} పేజీలు</span>
                            <span>•</span>
                            <span>${fileSizeMB} MB</span>
                        </div>
                    </div>
                </div>
                <button onclick="event.stopPropagation(); deleteDocument(${doc.id})" title="తొలగించు" class="text-slate-400 hover:text-rose-500 p-1 rounded-md transition-colors">
                    <i data-lucide="trash" class="w-3.5 h-3.5"></i>
                </button>
            </div>

            ${conversionBadge}

            ${doc.summary ? `
                <p class="text-[11px] text-slate-600 mt-2 line-clamp-2 leading-relaxed bg-slate-50 p-2 rounded-lg border border-slate-100">
                    ${doc.summary}
                </p>
            ` : ''}

            <div class="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between gap-1 flex-wrap">
                <button onclick="event.stopPropagation(); playDocContent(${doc.id})" title="డాక్యుమెంట్ మొదటి పేజీ పాఠాన్ని చదవండి" class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-brand-50 hover:bg-brand-100 text-[11px] font-bold text-brand-700 transition-colors">
                    <i data-lucide="volume-2" class="w-3.5 h-3.5"></i>
                    <span>పాఠం చదవండి</span>
                </button>

                <button onclick="event.stopPropagation(); playDocSummary(${doc.id})" title="సారాంశాన్ని వినండి" class="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-slate-100 hover:bg-slate-200 text-[11px] font-medium text-slate-700 transition-colors">
                    <i data-lucide="sparkles" class="w-3.5 h-3.5 text-amber-500"></i>
                    <span>సారాంశం</span>
                </button>

                <button onclick="event.stopPropagation(); openReaderModal(${doc.id})" title="పేజీలను చూడండి మరియు చదవండి" class="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-slate-100 hover:bg-slate-200 text-[11px] font-medium text-slate-700 transition-colors">
                    <i data-lucide="book-open" class="w-3.5 h-3.5 text-slate-500"></i>
                    <span>పేజీలు</span>
                </button>
            </div>
        `;
        container.appendChild(card);
    });

    // Check if any document is converting to maintain live polling
    const hasActiveConversion = documentsList.some(d => d.is_converting);
    if (hasActiveConversion && !conversionPollInterval) {
        conversionPollInterval = setInterval(fetchDocuments, 3500);
    } else if (!hasActiveConversion && conversionPollInterval) {
        clearInterval(conversionPollInterval);
        conversionPollInterval = null;
    }

    lucide.createIcons();
}

let conversionPollInterval = null;

async function startFullConversion(docId) {
    try {
        const res = await fetch(`/api/documents/${docId}/convert-all`, { method: "POST" });
        if (res.ok) {
            await fetchDocuments();
        }
    } catch (e) {
        console.error("Error starting full conversion:", e);
    }
}

function selectScope(docId) {
    activeDocId = docId;
    const allBtn = document.getElementById("scope-all-btn");
    const scopeLabel = document.getElementById("current-scope-label");

    if (docId === null) {
        allBtn.className = "w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg border border-brand-500 bg-brand-50/70 text-brand-900 text-xs font-semibold hover:bg-brand-100 transition-all";
        scopeLabel.innerHTML = `<i data-lucide="layers" class="w-3.5 h-3.5 text-brand-600"></i> అన్ని PDFల నుండి శోధన`;
    } else {
        allBtn.className = "w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg border border-slate-200 bg-white text-slate-700 text-xs font-medium hover:bg-slate-50 transition-all";
        const doc = documentsList.find(d => d.id === docId);
        const name = doc ? doc.filename : "ఎంచుకున్న డాక్యుమెంట్";
        scopeLabel.innerHTML = `<i data-lucide="file-text" class="w-3.5 h-3.5 text-brand-600"></i> ${name}`;
    }

    renderDocumentsList();
    fetchChatHistory();
    lucide.createIcons();
}

async function deleteDocument(docId) {
    if (!confirm("ఈ డాక్యుమెంట్‌ను మరియు దీనికి సంబంధించిన సంభాషణను ఖచ్చితంగా తొలగించాలనుకుంటున్నారా?")) return;

    try {
        await fetch(`/api/documents/${docId}`, { method: "DELETE" });
        if (activeDocId === docId) activeDocId = null;
        await fetchDocuments();
        selectScope(null);
    } catch (err) {
        console.error("Delete doc error:", err);
    }
}

// ----------------------------------------------------
// Voice Recognition (Speech-to-Text in Telugu)
// ----------------------------------------------------
function initVoiceRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.warn("Web Speech API is not supported in this browser.");
        return;
    }

    speechRecognition = new SpeechRecognition();
    speechRecognition.continuous = false;
    speechRecognition.interimResults = true;
    speechRecognition.lang = "te-IN"; // Telugu (India)

    speechRecognition.onstart = () => {
        isRecording = true;
        updateMicUI(true);
    };

    speechRecognition.onresult = (event) => {
        let transcript = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
            transcript += event.results[i][0].transcript;
        }
        const queryInput = document.getElementById("query-input");
        queryInput.value = transcript;
        autoResizeTextarea(queryInput);
    };

    speechRecognition.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        stopVoiceRecording();
    };

    speechRecognition.onend = () => {
        isRecording = false;
        updateMicUI(false);
    };
}

function toggleVoiceRecording() {
    if (!speechRecognition) {
        alert("మీ బ్రౌజర్ Web Speech API కి మద్దతు ఇవ్వడం లేదు. దయచేసి Google Chrome లేదా Microsoft Edge ఉపయోగించండి.");
        return;
    }

    if (isRecording) {
        speechRecognition.stop();
    } else {
        const langSelect = document.getElementById("voice-lang-select");
        if (langSelect) {
            speechRecognition.lang = langSelect.value || "te-IN";
        }
        speechRecognition.start();
    }
}

function stopVoiceRecording() {
    if (speechRecognition && isRecording) {
        speechRecognition.stop();
    }
    isRecording = false;
    updateMicUI(false);
}

function updateMicUI(recording) {
    const micBtn = document.getElementById("mic-btn");
    const voiceStatus = document.getElementById("voice-status");

    if (recording) {
        micBtn.classList.add("mic-recording");
        voiceStatus.classList.remove("hidden");
    } else {
        micBtn.classList.remove("mic-recording");
        voiceStatus.classList.add("hidden");
    }
}

// ----------------------------------------------------
// Audio Player & Text-to-Speech
// ----------------------------------------------------
const globalAudio = document.getElementById("app-audio-player");

function playAudio(url) {
    if (!url) return;
    if (currentPlayingAudioUrl === url && !globalAudio.paused) {
        globalAudio.pause();
        currentPlayingAudioUrl = null;
        updateAllAudioIcons();
        return;
    }

    globalAudio.src = url;
    globalAudio.play();
    currentPlayingAudioUrl = url;
    updateAllAudioIcons();

    globalAudio.onended = () => {
        currentPlayingAudioUrl = null;
        updateAllAudioIcons();
    };
}

function updateAllAudioIcons() {
    document.querySelectorAll("[data-audio-url]").forEach(btn => {
        const url = btn.getAttribute("data-audio-url");
        const iconContainer = btn.querySelector(".audio-icon-slot");
        if (!iconContainer) return;

        if (url === currentPlayingAudioUrl && !globalAudio.paused) {
            iconContainer.innerHTML = `<i data-lucide="pause" class="w-4 h-4 text-emerald-600"></i>`;
        } else {
            iconContainer.innerHTML = `<i data-lucide="play" class="w-4 h-4 text-brand-600"></i>`;
        }
    });
    lucide.createIcons();
}

async function playDocContent(docId, pageNumber = 1) {
    try {
        const res = await fetch(`/api/documents/${docId}/read`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode: "content", page_number: pageNumber })
        });
        const data = await res.json();
        if (data.audio_url) {
            playAudio(data.audio_url);
        } else {
            alert("ఈ డాక్యుమెంట్ కంటెంట్ కోసం ఆడియో రూపొందించడంలో విఫలమైంది.");
        }
    } catch (err) {
        console.error("Error playing doc content:", err);
    }
}

async function playDocSummary(docId) {
    try {
        const res = await fetch(`/api/documents/${docId}/read`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode: "summary" })
        });
        const data = await res.json();
        if (data.audio_url) {
            playAudio(data.audio_url);
        } else {
            alert("ఈ సారాంశం కోసం ఆడియో సిద్ధం కాలేదు.");
        }
    } catch (err) {
        console.error("Error playing doc summary:", err);
    }
}

async function playDocAudio(docId) {
    return playDocContent(docId);
}

// ----------------------------------------------------
// Chat & Q&A
// ----------------------------------------------------
function setQueryPrompt(text) {
    const input = document.getElementById("query-input");
    input.value = text;
    autoResizeTextarea(input);
    input.focus();
}

function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendQuery();
    }
}

function autoResizeTextarea(textarea) {
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + "px";
}

async function sendQuery() {
    const queryInput = document.getElementById("query-input");
    const query = queryInput.value.trim();
    if (!query) return;

    const generateSpeech = document.getElementById("tts-auto-play").checked;

    // Clear input
    queryInput.value = "";
    queryInput.style.height = "auto";

    // Hide welcome banner if visible
    const welcome = document.getElementById("welcome-banner");
    if (welcome) welcome.classList.add("hidden");

    // Append User Message
    appendMessage({
        role: "user",
        content: query,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    });

    // Append Loading Indicator
    const loadingId = appendLoadingIndicator();

    try {
        const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                query: query,
                doc_id: activeDocId,
                generate_speech: generateSpeech
            })
        });
        const data = await res.json();

        // Remove loading
        removeLoadingIndicator(loadingId);

        // Append Assistant Message
        appendMessage({
            role: "assistant",
            content: data.answer,
            audio_url: data.audio_url,
            sources: data.sources,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        });

        // Auto play audio if enabled
        if (generateSpeech && data.audio_url) {
            playAudio(data.audio_url);
        }

    } catch (err) {
        removeLoadingIndicator(loadingId);
        appendMessage({
            role: "assistant",
            content: "క్షమించండి, ప్రశ్నను పూర్తి చేయడంలో లోపం ఎదురైంది: " + err.message,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        });
    }
}

function appendMessage(msg) {
    const container = document.getElementById("chat-messages");
    const isUser = msg.role === "user";

    const msgDiv = document.createElement("div");
    msgDiv.className = `flex gap-3 max-w-3xl ${isUser ? "ml-auto flex-row-reverse" : "mr-auto"}`;

    const avatar = isUser ? `
        <div class="w-8 h-8 rounded-full bg-slate-800 text-white flex items-center justify-center flex-shrink-0 text-xs font-semibold">
            మీరు
        </div>
    ` : `
        <div class="w-8 h-8 rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-500 text-white flex items-center justify-center flex-shrink-0 shadow-sm">
            <i data-lucide="bot" class="w-4 h-4"></i>
        </div>
    `;

    const htmlContent = isUser 
        ? `<p class="whitespace-pre-wrap">${escapeHtml(msg.content)}</p>` 
        : marked.parse(msg.content);

    let sourcesHtml = '';
    if (!isUser && msg.sources && msg.sources.length > 0) {
        sourcesHtml = `
            <div class="mt-4 pt-3 border-t border-slate-200">
                <div class="flex items-center justify-between mb-2">
                    <span class="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                        <i data-lucide="bookmark-check" class="w-4 h-4 text-brand-600"></i>
                        సంబంధిత ఆధారాలు & మూలాలు (${msg.sources.length} పత్రాలు/పేజీలు):
                    </span>
                </div>
                <div class="space-y-2.5">
                    ${msg.sources.map(s => `
                        <div class="p-3 bg-slate-50 border border-slate-200 rounded-xl hover:border-brand-200 transition-colors">
                            <div class="flex items-center justify-between gap-2 mb-1.5">
                                <div class="flex items-center gap-1.5 truncate">
                                    <i data-lucide="file-text" class="w-3.5 h-3.5 text-brand-600 flex-shrink-0"></i>
                                    <span class="text-xs font-bold text-slate-800 truncate" title="${escapeHtml(s.doc_name || '')}">
                                        ${escapeHtml(s.doc_name || 'PDF Document')}
                                    </span>
                                </div>
                                <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-brand-100 text-brand-800 flex-shrink-0">
                                    పేజీ ${s.page_number || 1}
                                </span>
                            </div>
                            
                            ${s.snippet ? `
                                <div class="text-xs text-slate-700 bg-white p-2.5 rounded-lg border border-slate-200 leading-relaxed font-normal border-l-4 border-l-brand-500">
                                    <span class="italic font-serif">"${escapeHtml(s.snippet)}"</span>
                                </div>
                            ` : ''}

                            <div class="mt-2 flex items-center justify-between gap-2 text-[11px]">
                                <span class="text-slate-500 text-[10px] truncate max-w-xs">${s.relevance ? escapeHtml(s.relevance) : ''}</span>
                                <div class="flex items-center gap-1.5 flex-shrink-0">
                                    ${s.snippet ? `
                                        <button onclick="playSnippetAudio(this.getAttribute('data-snippet'))" data-snippet="${escapeHtml(s.snippet)}" class="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-white hover:bg-brand-50 text-slate-700 hover:text-brand-700 border border-slate-200 text-xs font-medium transition-colors shadow-2xs">
                                            <i data-lucide="volume-2" class="w-3 h-3"></i>
                                            <span>వినండి</span>
                                        </button>
                                    ` : ''}
                                    ${s.doc_id ? `
                                        <button onclick="openReaderModal(${s.doc_id})" class="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 text-xs font-medium transition-colors shadow-2xs">
                                            <i data-lucide="book-open" class="w-3 h-3"></i>
                                            <span>పేజీ చూడండి</span>
                                        </button>
                                    ` : ''}
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    const audioButton = (!isUser && msg.audio_url) ? `
        <div class="mt-3 pt-2 border-t border-slate-100 flex items-center gap-2">
            <button 
                onclick="playAudio('${msg.audio_url}')" 
                data-audio-url="${msg.audio_url}"
                class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-brand-50 hover:bg-brand-100 text-brand-700 text-xs font-medium transition-colors"
            >
                <span class="audio-icon-slot"><i data-lucide="volume-2" class="w-3.5 h-3.5"></i></span>
                <span>సమాధానం వినండి (Listen)</span>
            </button>
        </div>
    ` : '';

    msgDiv.innerHTML = `
        ${avatar}
        <div class="flex-1 ${isUser ? "text-right" : "text-left"}">
            <div class="inline-block text-left p-4 rounded-2xl text-xs md:text-sm ${
                isUser 
                    ? "bg-brand-600 text-white rounded-tr-none shadow-md shadow-brand-500/20" 
                    : "bg-white text-slate-800 border border-slate-200 rounded-tl-none shadow-sm prose-telugu"
            }">
                ${htmlContent}
                ${audioButton}
                ${sourcesHtml}
            </div>
            <div class="text-[10px] text-slate-400 mt-1 px-1">
                ${msg.timestamp || ''}
            </div>
        </div>
    `;

    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
    lucide.createIcons();
}

function appendLoadingIndicator() {
    const container = document.getElementById("chat-messages");
    const id = "loading-" + Date.now();
    const div = document.createElement("div");
    div.id = id;
    div.className = "flex gap-3 max-w-3xl mr-auto";
    div.innerHTML = `
        <div class="w-8 h-8 rounded-xl bg-brand-100 text-brand-600 flex items-center justify-center flex-shrink-0">
            <i data-lucide="bot" class="w-4 h-4"></i>
        </div>
        <div class="bg-white border border-slate-200 p-4 rounded-2xl rounded-tl-none flex items-center gap-2 shadow-sm">
            <span class="text-xs text-slate-500 font-medium">విశ్లేషిస్తున్నాను...</span>
            <div class="sound-wave text-brand-600"><span></span><span></span><span></span><span></span></div>
        </div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    lucide.createIcons();
    return id;
}

function removeLoadingIndicator(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

async function fetchChatHistory() {
    try {
        const url = activeDocId !== null ? `/api/chat/history?doc_id=${activeDocId}` : `/api/chat/history`;
        const res = await fetch(url);
        const data = await res.json();
        const container = document.getElementById("chat-messages");
        const welcome = document.getElementById("welcome-banner");

        // Clear messages except welcome
        container.querySelectorAll("div.flex.gap-3").forEach(m => m.remove());

        if (data.messages && data.messages.length > 0) {
            if (welcome) welcome.classList.add("hidden");
            data.messages.forEach(msg => appendMessage(msg));
        } else {
            if (welcome) welcome.classList.remove("hidden");
        }
    } catch (err) {
        console.error("Error loading chat history:", err);
    }
}

async function clearChatHistory() {
    if (!confirm("సంభాషణ చరిత్రను క్లియర్ చేయాలనుకుంటున్నారా?")) return;
    try {
        const url = activeDocId !== null ? `/api/chat/clear?doc_id=${activeDocId}` : `/api/chat/clear`;
        await fetch(url, { method: "POST" });
        fetchChatHistory();
    } catch (err) {
        console.error("Error clearing chat:", err);
    }
}

function isLegacyTeluguFont(text) {
    if (!text || text.length < 10) return false;
    let teluguChars = 0;
    for (let i = 0; i < text.length; i++) {
        const code = text.charCodeAt(i);
        if (code >= 0x0C00 && code <= 0x0C7F) teluguChars++;
    }
    if (teluguChars > 20) return false;
    const legacyGlyphs = "„ãÑÖÅÜÕ^~°áê∂`=Q+*&{}|<>[]_…‡‰´˙ˇ†";
    let matches = 0;
    for (let i = 0; i < text.length; i++) {
        if (legacyGlyphs.includes(text[i])) matches++;
    }
    return matches >= 10;
}

async function convertPageWithOCR(docId, pageNumber, btnEl) {
    const originalHtml = btnEl.innerHTML;
    btnEl.innerHTML = `<span class="inline-flex items-center gap-1 text-purple-600"><div class="w-3 h-3 border-2 border-purple-600 border-t-transparent rounded-full animate-spin"></div> AI OCR నడుస్తోంది...</span>`;
    btnEl.disabled = true;

    try {
        const formData = new FormData();
        formData.append("page_number", pageNumber);

        const res = await fetch(`/api/documents/${docId}/ocr-page`, {
            method: "POST",
            body: formData
        });
        const data = await res.json();
        if (data.status === "success" && data.page_text) {
            const pageTextEl = document.getElementById(`page-text-${pageNumber}`);
            if (pageTextEl) {
                pageTextEl.textContent = data.page_text;
            }
            btnEl.outerHTML = `<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">✔ స్వచ్ఛమైన తెలుగు (Clean Telugu)</span>`;
            alert(`పేజీ ${pageNumber} విజయవంతంగా స్వచ్ఛమైన తెలుగులోకి మార్చబడింది!`);
        } else {
            btnEl.innerHTML = originalHtml;
            btnEl.disabled = false;
            alert("ఈ పేజీని OCR చేయడంలో విఫలమైంది.");
        }
    } catch (e) {
        btnEl.innerHTML = originalHtml;
        btnEl.disabled = false;
        alert("OCR ఎర్రర్: " + e.message);
    }
}

// ----------------------------------------------------
// Reader Modal (View Telugu pages & Read page aloud)
// ----------------------------------------------------
async function openReaderModal(docId) {
    const modal = document.getElementById("reader-modal");
    const title = document.getElementById("reader-doc-title");
    const container = document.getElementById("reader-pages-container");
    const countLabel = document.getElementById("reader-page-count");

    container.innerHTML = `<div class="text-center py-10 text-slate-400">లోడ్ అవుతోంది...</div>`;
    modal.classList.remove("hidden");

    try {
        const res = await fetch(`/api/documents/${docId}`);
        const data = await res.json();
        const doc = data.document;

        title.textContent = doc.filename;
        countLabel.textContent = `మొత్తం పేజీలు: ${doc.page_count}`;

        container.innerHTML = "";
        doc.pages.forEach(p => {
            const pageCard = document.createElement("div");
            pageCard.className = "p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3";
            
            const isLegacy = !p.is_ocr && isLegacyTeluguFont(p.page_text);

            pageCard.innerHTML = `
                <div class="flex items-center justify-between border-b border-slate-200 pb-2 flex-wrap gap-2">
                    <div class="flex items-center gap-2">
                        <span class="text-xs font-bold text-slate-700">పేజీ ${p.page_number}</span>
                        ${p.is_ocr ? '<span class="px-1.5 py-0.5 text-[10px] rounded bg-purple-50 text-purple-700 border border-purple-200 font-semibold">Vision OCR</span>' : ''}
                        ${isLegacy ? '<span class="px-1.5 py-0.5 text-[10px] rounded bg-amber-50 text-amber-700 border border-amber-200">పాత DTP ఫాంట్</span>' : ''}
                    </div>
                    <div class="flex items-center gap-2">
                        ${isLegacy ? `
                            <button onclick="convertPageWithOCR(${docId}, ${p.page_number}, this)" class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 text-xs font-semibold transition-colors shadow-2xs">
                                <i data-lucide="sparkles" class="w-3.5 h-3.5"></i>
                                <span>తెలుగులోకి మార్చండి (AI OCR)</span>
                            </button>
                        ` : ''}
                        <button onclick="readPageAloud(${docId}, ${p.page_number})" class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-white border border-slate-200 hover:bg-brand-50 hover:text-brand-700 text-xs text-slate-700 font-medium transition-colors shadow-sm">
                            <i data-lucide="volume-2" class="w-3.5 h-3.5"></i>
                            <span>ఈ పేజీని చదవండి (Read Aloud)</span>
                        </button>
                    </div>
                </div>
                <p id="page-text-${p.page_number}" class="text-xs md:text-sm text-slate-800 whitespace-pre-wrap leading-relaxed font-normal">
                    ${p.page_text ? escapeHtml(p.page_text) : '<span class="text-slate-400 italic">ఈ పేజీలో టెక్స్ట్ కనుగొనబడలేదు</span>'}
                </p>
            `;
            container.appendChild(pageCard);
        });

        lucide.createIcons();
    } catch (err) {
        container.innerHTML = `<div class="text-rose-500 text-xs">డాక్యుమెంట్‌ను లోడ్ చేయడంలో లోపం ఎదురైంది.</div>`;
    }
}

function closeReaderModal() {
    document.getElementById("reader-modal").classList.add("hidden");
}

async function readPageAloud(docId, pageNumber) {
    try {
        const res = await fetch(`/api/documents/${docId}/read`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode: "page", page_number: pageNumber })
        });
        const data = await res.json();
        
        // If text was converted by AI OCR on-the-fly, update the page text in the modal view
        if (data.status === "success" && data.text) {
            const pageTextEl = document.getElementById(`page-text-${pageNumber}`);
            if (pageTextEl) {
                pageTextEl.textContent = data.text;
            }
        }

        if (data.audio_url) {
            playAudio(data.audio_url);
        } else {
            alert("ఈ పేజీ కోసం ఆడియో రూపొందించడంలో విఫలమైంది.");
        }
    } catch (err) {
        console.error("Read page aloud error:", err);
    }
}

async function playSnippetAudio(text) {
    if (!text) return;
    try {
        const res = await fetch("/api/tts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: text, lang: "te" })
        });
        const data = await res.json();
        if (data.audio_url) {
            playAudio(data.audio_url);
        } else {
            alert("ఈ టెక్స్ట్ కోసం ఆడియో రూపొందించడంలో విఫలమైంది.");
        }
    } catch (e) {
        console.error("Snippet audio error:", e);
    }
}

// Helper: Escape HTML
function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;")
              .replace(/</g, "&lt;")
              .replace(/>/g, "&gt;")
              .replace(/"/g, "&quot;")
              .replace(/'/g, "&#039;");
}
