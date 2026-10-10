/* Aarogya Saathi phone simulator. Talks to the same backend a real phone line uses. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const el = {
    mode: $("mode"), screen: $("screen"), status: $("screenStatus"), text: $("screenText"),
    call: $("callBtn"), mic: $("micBtn"), hang: $("hangBtn"), keypad: $("keypad"),
    typeForm: $("typeForm"), typeInput: $("typeInput"), typeSend: $("typeSend"),
    scenarios: $("scenarios"), chips: $("scenarioChips"), mute: $("muteToggle"),
    turns: $("turns"), convoEmpty: $("convoEmpty"), slip: $("slip"), slipEmpty: $("slipEmpty"),
    langRows: $("langRows"), lookupForm: $("lookupForm"), lookupInput: $("lookupInput"), lookupMsg: $("lookupMsg"),
  };

  const S = {
    callId: null, phase: "idle", // idle | language | ready | confirming | answered | emergency | consent | ended
    lang: null, languages: [], scenarios: [], lastTurn: null, health: null,
  };

  const SCRIPT_ATTR = { "as-IN": "as", "bn-IN": "bn", "mni-IN": "mni", "hi-IN": "hi", "brx-IN": "brx", "ne-IN": "ne", "en-IN": "en" };
  const STEP_COLORS = { stt: "#B98A12", translate_in: "#7FA88C", triage: "#B3202A", retrieve: "#4A5F51", llm: "#16301F", translate_out: "#9DBFA6", tts: "#D9B44A" };
  const STEP_NAMES = { stt: "Speech to text", translate_in: "Translate to English", triage: "Safety check", retrieve: "Find health card", llm: "AI answer", translate_out: "Translate back", tts: "Voice" };
  const SOURCE_NAMES = {
    llm: "Live AI, grounded on vetted cards", demo: "Demo answer (scripted)", card_fallback: "Vetted card text (AI not available)",
    emergency: "Emergency script, AI skipped", crisis: "Crisis script, AI skipped",
  };

  // ---------- API ----------
  async function api(path, opts = {}) {
    const res = await fetch(path, { headers: opts.body instanceof FormData ? {} : { "Content-Type": "application/json" }, ...opts });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
    return data;
  }
  const post = (path, body) => api(path, { method: "POST", body: body instanceof FormData ? body : JSON.stringify(body || {}) });

  // ---------- screen + audio ----------
  function show(status, text, mode = "", lang = "en-IN") {
    el.status.textContent = status;
    el.text.textContent = text;
    el.text.lang = SCRIPT_ATTR[lang] || "en";
    el.screen.dataset.mode = mode;
  }

  const audioQueue = [];
  let playing = false;
  function enqueue(item) { audioQueue.push(item); if (!playing) playNext(); }
  function stopAudio() { audioQueue.length = 0; playing = false; if (window.speechSynthesis) speechSynthesis.cancel(); if (currentAudio) currentAudio.pause(); }
  let currentAudio = null;

  function playNext() {
    const item = audioQueue.shift();
    if (!item) { playing = false; if (el.screen.dataset.mode === "speaking") el.screen.dataset.mode = ""; return; }
    playing = true;
    if (el.mute.checked) { playing = false; audioQueue.length = 0; return; }
    if (el.screen.dataset.mode !== "emergency") el.screen.dataset.mode = "speaking";
    if (item.url) {
      currentAudio = new Audio(item.url);
      currentAudio.onended = currentAudio.onerror = playNext;
      currentAudio.play().catch(playNext);
    } else if (item.text && browserVoiceFor(item.lang)) {
      const u = new SpeechSynthesisUtterance(item.text);
      u.lang = browserVoiceFor(item.lang).lang; u.voice = browserVoiceFor(item.lang); u.rate = 0.9;
      u.onend = u.onerror = playNext;
      speechSynthesis.speak(u);
    } else {
      playNext();
    }
  }
  function browserVoiceFor(lang) {
    if (!window.speechSynthesis) return null;
    const meta = S.languages.find((l) => l.code === lang);
    const tag = (meta && meta.browser_voice) || (lang === "en-IN" ? "en-IN" : null);
    if (!tag) return null;
    const voices = speechSynthesis.getVoices();
    return voices.find((v) => v.lang === tag) || voices.find((v) => v.lang.startsWith(tag.split("-")[0])) || null;
  }
  function say(text, lang, voice) { enqueue({ url: voice && voice.audio_url, text, lang }); }

  // ---------- DTMF tones ----------
  let ctx;
  const DTMF = { 1: [697, 1209], 2: [697, 1336], 3: [697, 1477], 4: [770, 1209], 5: [770, 1336], 6: [770, 1477],
    7: [852, 1209], 8: [852, 1336], 9: [852, 1477], "*": [941, 1209], 0: [941, 1336], "#": [941, 1477] };
  function tone(d) {
    try {
      ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
      const g = ctx.createGain(); g.gain.value = 0.06; g.connect(ctx.destination);
      DTMF[d].forEach((f) => { const o = ctx.createOscillator(); o.frequency.value = f; o.connect(g); o.start(); o.stop(ctx.currentTime + 0.14); });
    } catch (_) { /* tones are optional */ }
  }

  // ---------- controls ----------
  function setControls() {
    const inCall = !!S.callId && S.phase !== "ended";
    const canAsk = inCall && ["ready", "answered", "emergency"].includes(S.phase);
    el.call.disabled = inCall;
    el.hang.disabled = !inCall;
    el.mic.disabled = !canAsk;
    el.typeInput.disabled = el.typeSend.disabled = !canAsk;
    el.scenarios.hidden = !canAsk;
    if (canAsk) renderScenarioChips();
  }

  function hintKeys(digits) {
    el.keypad.querySelectorAll(".key").forEach((k) => {
      if (digits.includes(k.dataset.d)) k.dataset.hint = "1"; else delete k.dataset.hint;
    });
    el.keypad.classList.toggle("hint", digits.length > 0);
  }

  // ---------- call flow ----------
  async function startCall() {
    stopAudio();
    try {
      const r = await post("/api/calls/start", { channel: "simulator" });
      S.callId = r.call.id; S.phase = "language"; S.lang = null; S.lastTurn = null;
      el.turns.innerHTML = ""; el.convoEmpty.hidden = false;
      show("Choose a language", `${r.welcome}\n${r.menu}`);
      say(`${r.welcome} ${r.menu}`, "en-IN");
      hintKeys(["1", "2", "3", "4", "5", "6", "7", "8"]);
      setControls();
    } catch (e) { show("Could not connect", e.message); }
  }

  async function chooseLanguage(digit) {
    try {
      const r = await post(`/api/calls/${S.callId}/language`, { digit });
      if (!r.supported) {
        show("Language not available yet", r.prompt.text);
        say(r.prompt.text, "en-IN");
        return;
      }
      S.lang = r.call.language; S.phase = "ready";
      const p = r.prompts;
      show(`${r.capabilities.native_name}`, `${p.confirmed.text}\n${p.ask.text}`, "", p.ask.lang);
      say(p.confirmed.text, p.confirmed.lang, r.voices[0]);
      say(p.ask.text, p.ask.lang, r.voices[1]);
      hintKeys([]);
      setControls();
    } catch (e) { show("Try again", e.message); }
  }

  async function askText(text, viaVoice = false) {
    if (!text.trim()) return;
    show("Thinking", text, "", S.lang);
    el.mic.disabled = el.typeSend.disabled = true;
    try {
      // Speech goes through read-back confirmation; typed text does not need it.
      const r = await post(`/api/calls/${S.callId}/message`, { text, skip_readback: !viaVoice });
      if (r.turn) return renderAnswer(r.turn);
      S.phase = "confirming";
      show("Did I hear you right?", r.prompt.text, "", r.prompt.lang);
      say(r.prompt.text, r.prompt.lang);
      hintKeys(["1", "2"]);
    } catch (e) { show("Try again", e.message); }
    setControls();
  }

  async function sendAudio(blob) {
    show("Listening done", "Recognising speech…", "", S.lang);
    const fd = new FormData(); fd.append("audio", blob, "question.webm");
    try {
      const r = await post(`/api/calls/${S.callId}/transcribe`, fd);
      if (!r.ok) {
        show("Could not hear", `${r.prompt.text}${r.hint ? "\n" + r.hint : ""}`, "", r.prompt.lang);
        say(r.prompt.text, r.prompt.lang);
        if (r.reason === "stt_unavailable") el.typeInput.focus();
        return setControls();
      }
      S.phase = "confirming";
      show("Did I hear you right?", r.prompt.text, "", r.prompt.lang);
      say(r.prompt.text, r.prompt.lang, r.voice);
      hintKeys(["1", "2"]);
    } catch (e) { show("Try again", e.message); }
    setControls();
  }

  async function confirm(correct) {
    try {
      show(correct ? "Thinking" : "Say it again", correct ? "Finding safe information…" : "", "", S.lang);
      const r = await post(`/api/calls/${S.callId}/confirm`, { correct });
      if (r.turn) return renderAnswer(r.turn);
      S.phase = "ready";
      show("Listening", r.prompt.text, "", r.prompt.lang);
      say(r.prompt.text, r.prompt.lang, r.voice);
      hintKeys([]);
    } catch (e) { show("Try again", e.message); }
    setControls();
  }

  async function simpler() {
    try {
      const r = await post(`/api/calls/${S.callId}/simpler`);
      renderAnswer(r.turn);
    } catch (e) { show("Ask a question first", e.message); }
  }

  function repeat() {
    if (!S.lastTurn) return;
    const t = S.lastTurn;
    show("Repeating", t.answer.text, S.phase === "emergency" ? "emergency" : "", t.answer.lang);
    say(t.answer.text, t.answer.lang, t.voice);
  }

  function askConsent() {
    S.phase = "consent";
    const text = "Would you like a short summary slip of this call to show your ASHA worker or doctor? Press 1 for yes, 2 for no.";
    show("Before you go", text);
    say(text, "en-IN");
    hintKeys(["1", "2"]);
    setControls();
  }

  async function endCall(consent = false) {
    if (!S.callId) return;
    stopAudio();
    try {
      const r = await post(`/api/calls/${S.callId}/end`, { consent_slip: consent });
      show("Call ended", `${r.goodbye.text}${r.slip ? `\nSlip code: ${r.slip.code}` : ""}\nTranscripts and audio were cleared.`, "", r.goodbye.lang);
      say(r.goodbye.text, r.goodbye.lang);
      if (r.slip) { renderSlip(r.slip); switchTab("slip"); }
    } catch (e) { show("Call ended", "This call had already ended."); }
    S.callId = null; S.phase = "ended"; hintKeys([]); setControls();
  }

  function onDigit(d) {
    tone(d);
    if (!S.callId) return;
    switch (S.phase) {
      case "language": return chooseLanguage(d);
      case "confirming": if (d === "1") return confirm(true); if (d === "2") return confirm(false); return;
      case "consent": if (d === "1") return endCall(true); if (d === "2") return endCall(false); return;
      case "ready": case "answered": case "emergency":
        if (d === "1") { show("Listening", "Hold the speak button, or type below.", "", S.lang); el.typeInput.focus(); return; }
        if (d === "2") return repeat();
        if (d === "5") return simpler();
        if (d === "3") { S.phase = "language"; show("Choose a language", el.mode.dataset.menu || "Press 1 to 7 to choose a language."); hintKeys(["1", "2", "3", "4", "5", "6", "7", "8"]); return setControls(); }
        if (d === "9") return askConsent();
        if (d === "0" && S.lastTurn) { show("Menu", S.lastTurn.menu.text, "", S.lastTurn.menu.lang); say(S.lastTurn.menu.text, S.lastTurn.menu.lang); }
    }
  }

  // ---------- rendering ----------
  function renderAnswer(turn) {
    S.lastTurn = turn;
    const emergency = ["emergency", "crisis"].includes(turn.triage.level);
    S.phase = emergency ? "emergency" : "answered";
    show(emergency ? "Possible emergency" : "Answer", `${turn.answer.text}\n\n${turn.menu.text}`, emergency ? "emergency" : "", turn.answer.lang);
    say(turn.answer.text, turn.answer.lang, turn.voice);
    hintKeys(emergency ? ["1", "2", "3", "9"] : ["1", "2", "5", "3", "9"]);
    el.convoEmpty.hidden = true;
    el.turns.prepend(turnElement(turn));
    setControls();
  }

  function esc(s) { return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

  function turnElement(t) {
    const li = document.createElement("li");
    li.className = "turn";
    const lvl = t.triage.level;
    const flagText = {
      none: "Safety check: no red flags found.",
      urgent: "Safety check: needs a health worker within a day.",
      emergency: "Safety check: possible emergency. The AI was skipped and the emergency script was spoken.",
      crisis: "Safety check: possible self-harm risk. Crisis support script was spoken.",
    }[lvl];
    const matches = t.triage.matches.map((m) => m.label).join(", ");
    const baseSource = (t.answer.source || "").split("+")[0];
    const sourceLabel = SOURCE_NAMES[baseSource] || baseSource;
    const englishFallback = (t.answer.source || "").includes("english_fallback");
    const steps = Object.entries(t.timings_ms || {}).filter(([k]) => STEP_NAMES[k]);
    const total = steps.reduce((a, [, v]) => a + v, 0) || 1;
    const speechNote = t.voice && t.voice.voice_note && !el.mute.checked ? `<p class="voice-note">${esc(t.voice.voice_note)}</p>` : "";
    li.innerHTML = `
      <div>
        <p class="said" lang="${SCRIPT_ATTR[S.lang] || "en"}">“${esc(t.transcript)}”</p>
        <p class="said-meta">${t.english && S.lang !== "en-IN" ? `English used for reasoning: ${esc(t.english)} <small>(${esc(t.english_source)})</small>` : (S.lang === "en-IN" ? "" : "No translator configured and not a demo question, so the safety check ran on the original words only.")}</p>
      </div>
      <div class="flag ${lvl}"><b>${esc(flagText)}</b>${matches ? `<br>Matched: ${esc(matches)}` : ""}</div>
      <div>
        <p><span class="source ${esc(baseSource)}">${esc(sourceLabel)}</span>${t.level === "simple" ? '<span class="source">Simpler words</span>' : ""}</p>
        <p class="answer" lang="${SCRIPT_ATTR[t.answer.lang] || "en"}">${esc(t.answer.text)}</p>
        ${t.answer.english && t.answer.lang !== "en-IN" ? `<p class="answer-en">In English: ${esc(t.answer.english)}</p>` : ""}
        ${englishFallback ? '<p class="voice-note">Shown in English because translation for this language is not configured.</p>' : ""}
      </div>
      ${t.cards.length ? `<p class="cards">Based on the vetted card ${t.cards.map((c) => `“${esc(c.title)}”, source: ${esc(c.source)}`).join("; and ")}.</p>` : ""}
      ${speechNote}
      ${steps.length ? `<div class="timing" aria-label="Time taken per step">
        <div class="timing-bar">${steps.map(([k, v]) => `<span style="width:${(v / total) * 100}%;background:${STEP_COLORS[k]}" title="${STEP_NAMES[k]}: ${v} ms"></span>`).join("")}</div>
        <div class="timing-legend">${steps.map(([k, v]) => `<span><i style="background:${STEP_COLORS[k]}"></i>${STEP_NAMES[k]} ${v} ms</span>`).join("")}</div>
      </div>` : ""}
      <div class="answer-actions">
        <button type="button" data-act="repeat">Hear again</button>
        ${lvl === "emergency" || lvl === "crisis" ? "" : '<button type="button" data-act="simpler">Explain more simply</button>'}
      </div>`;
    li.querySelector('[data-act="repeat"]').onclick = () => { show("Repeating", t.answer.text, "", t.answer.lang); say(t.answer.text, t.answer.lang, t.voice); };
    const simp = li.querySelector('[data-act="simpler"]');
    if (simp) simp.onclick = () => S.callId && simpler();
    return li;
  }

  function renderSlip(slip) {
    el.slipEmpty.hidden = true;
    el.slip.hidden = false;
    const concerns = slip.concerns.map((c) => `<li><span lang="${SCRIPT_ATTR[S.lang] || "en"}">${esc(c.said)}</span>${c.english && c.english !== c.said ? `<small>${esc(c.english)}</small>` : ""}${c.duration ? `<small>Duration mentioned: ${esc(c.duration)}</small>` : ""}</li>`).join("");
    el.slip.innerHTML = `
      <p>Aarogya Saathi care slip</p>
      <div class="code">${esc(slip.code)}</div>
      <h3 class="urgency-${esc(slip.urgency)}">${esc(slip.recommended_action)}</h3>
      <dl>
        <dt>Created</dt><dd>${esc(slip.created_ist)}</dd>
        <dt>Language</dt><dd>${esc(slip.language)}</dd>
        <dt>Red flags</dt><dd>${slip.red_flags.length ? esc(slip.red_flags.join(", ")) : "None reported"}</dd>
        <dt>Topics</dt><dd>${slip.topics_covered.length ? esc(slip.topics_covered.join(", ")) : "—"}</dd>
        <dt>Caller said</dt><dd><ul>${concerns}</ul></dd>
      </dl>
      <small>${esc(slip.disclaimer)} This slip is deleted automatically after 24 hours.</small>
      <div class="slip-actions"><button type="button" id="printSlip">Print slip</button><button type="button" id="deleteSlip">Delete slip now</button></div>`;
    $("printSlip").onclick = () => window.print();
    $("deleteSlip").onclick = async () => {
      await api(`/api/slips/${slip.code}`, { method: "DELETE" });
      el.slip.hidden = true; el.slipEmpty.hidden = false;
      el.lookupMsg.textContent = `Slip ${slip.code} deleted.`;
    };
  }

  function renderLanguages() {
    const statusText = { full_voice: "Full voice", voice_ready_needs_keys: "Ready once API keys are added", partial: "Partial", unsupported: "Not available yet" };
    el.langRows.innerHTML = S.languages.map((l) => `
      <tr>
        <td><span class="native" lang="${SCRIPT_ATTR[l.code] || "en"}">${esc(l.native_name)}</span><small>${esc(l.name)}, ${esc(l.states.join(", "))}</small>${l.notes ? `<small>${esc(l.notes)}</small>` : ""}</td>
        <td>${l.keypad || "8"}</td>
        <td><span class="badge ${l.level}">${statusText[l.level]}</span></td>
        <td>${l.provider_support.stt.length ? esc(l.provider_support.stt.join(", ")) : "—"}</td>
        <td>${l.provider_support.tts.length ? esc(l.provider_support.tts.join(", ")) : "—"}</td>
      </tr>`).join("");
  }

  function renderScenarioChips() {
    const lang = S.lang;
    el.chips.innerHTML = "";
    S.scenarios.forEach((sc) => {
      const q = sc.questions[lang] || sc.questions["en-IN"];
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip" + (/emergency/.test(sc.title) ? " danger" : "");
      b.textContent = sc.title;
      b.title = q;
      b.onclick = () => askText(q);
      el.chips.appendChild(b);
    });
  }

  function switchTab(name) {
    document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
    ["convo", "slip", "langs"].forEach((t) => { $(`tab-${t}`).hidden = t !== name; });
  }

  // ---------- microphone (hold to speak) ----------
  let recorder = null, chunks = [], recognition = null;
  async function startRecording() {
    if (el.mic.disabled) return;
    stopAudio();
    const sttLive = S.health && !/demo/.test(S.health.providers.stt);
    if (!sttLive) return startBrowserRecognition();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      recorder = new MediaRecorder(stream);
      chunks = [];
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = () => { stream.getTracks().forEach((t) => t.stop()); sendAudio(new Blob(chunks, { type: recorder.mimeType || "audio/webm" })); };
      recorder.start();
      el.mic.classList.add("recording"); el.mic.textContent = "Release to send";
      show("Listening", "Speak now. Release the button when you finish.", "listening", S.lang);
    } catch (_) {
      show("Microphone blocked", "Allow microphone access, or type the question below.", "", "en-IN");
    }
  }
  function stopRecording() {
    el.mic.classList.remove("recording"); el.mic.textContent = "Hold to speak";
    if (recorder && recorder.state === "recording") recorder.stop();
    if (recognition) recognition.stop();
  }
  function startBrowserRecognition() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const meta = S.languages.find((l) => l.code === S.lang);
    if (!SR || !meta || !meta.browser_voice) {
      show("Type instead", "Speech recognition for this language needs the Sarvam API key. Please type the question below for now.", "", "en-IN");
      el.typeInput.focus();
      return;
    }
    recognition = new SR();
    recognition.lang = meta.browser_voice;
    recognition.interimResults = false;
    recognition.onresult = (e) => { const t = e.results[0][0].transcript; recognition = null; askText(t, true); };
    recognition.onerror = () => { recognition = null; show("Could not hear", "Please try again, or type the question.", "", "en-IN"); };
    recognition.start();
    el.mic.classList.add("recording"); el.mic.textContent = "Release to send";
    show("Listening (browser speech)", "Speak now.", "listening", S.lang);
  }

  // ---------- wiring ----------
  el.call.onclick = startCall;
  el.hang.onclick = () => endCall(false);
  el.keypad.addEventListener("click", (e) => { const k = e.target.closest(".key"); if (k) onDigit(k.dataset.d); });
  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT") return;
    if (/^[0-9*#]$/.test(e.key)) {
      const k = el.keypad.querySelector(`[data-d="${e.key}"]`);
      if (k) { k.classList.add("pressed"); setTimeout(() => k.classList.remove("pressed"), 120); }
      onDigit(e.key);
    }
  });
  el.mic.addEventListener("pointerdown", (e) => { e.preventDefault(); startRecording(); });
  el.mic.addEventListener("pointerup", stopRecording);
  el.mic.addEventListener("pointerleave", () => recorder && recorder.state === "recording" && stopRecording());
  el.mic.addEventListener("keydown", (e) => { if ((e.key === " " || e.key === "Enter") && !e.repeat) { e.preventDefault(); startRecording(); } });
  el.mic.addEventListener("keyup", (e) => { if (e.key === " " || e.key === "Enter") stopRecording(); });
  el.typeForm.onsubmit = (e) => { e.preventDefault(); const t = el.typeInput.value; el.typeInput.value = ""; askText(t); };
  el.mute.onchange = () => el.mute.checked && stopAudio();
  document.querySelectorAll(".tabs button").forEach((b) => (b.onclick = () => switchTab(b.dataset.tab)));
  el.lookupForm.onsubmit = async (e) => {
    e.preventDefault();
    const code = el.lookupInput.value.trim().toUpperCase();
    if (!code) return;
    try { renderSlip(await api(`/api/slips/${encodeURIComponent(code)}`)); el.lookupMsg.textContent = ""; }
    catch (err) { el.lookupMsg.textContent = err.message; }
  };

  // ---------- boot ----------
  (async () => {
    try {
      const [health, langs, scen] = await Promise.all([api("/api/health"), api("/api/languages"), api("/api/scenarios")]);
      S.health = health; S.languages = langs.languages; S.scenarios = scen.scenarios;
      el.mode.dataset.menu = langs.menu;
      const p = health.providers;
      const live = !/demo/.test(p.llm);
      el.mode.innerHTML = live
        ? `<strong>Live AI</strong> using ${esc(p.llm)}, speech by ${esc(p.stt)}`
        : `<strong>Demo mode</strong>: scripted answers in English, Hindi and Assamese. Add API keys in .env for live AI.`;
      renderLanguages();
      if (window.speechSynthesis) speechSynthesis.getVoices();
    } catch (e) {
      el.mode.textContent = "Backend not reachable. Start it with: uvicorn app.main:app";
    }
    setControls();
  })();
})();
