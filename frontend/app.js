/* Aarogya Saathi web app: browser microphone → backend (STT → safety → LLM → translation → TTS) → audio. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const el = {
    status: $("status"), offline: $("offline"), configBanner: $("configBanner"),
    langStep: $("langStep"), langGrid: $("langGrid"), unavailableBox: $("unavailableBox"), unavailableList: $("unavailableList"),
    talkStep: $("talkStep"), changeLang: $("changeLang"), mute: $("mute"), emergencyBtn: $("emergencyBtn"),
    turns: $("turns"), mic: $("mic"), micLabel: $("micLabel"), micHelp: $("micHelp"), meter: $("meter"),
    typeForm: $("typeForm"), typeInput: $("typeInput"), findBtn: $("findBtn"),
    facilityPanel: $("facilityPanel"), facClose: $("facClose"), gpsBtn: $("gpsBtn"), placeForm: $("placeForm"),
    placeInput: $("placeInput"), facResults: $("facResults"), player: $("player"),
  };
  const S = { conv: null, lang: null, langs: [], health: null, state: "idle", emergencyContext: false };
  const ATTR = { "as-IN": "as", "bn-IN": "bn", "mni-IN": "mni", "hi-IN": "hi", "brx-IN": "brx", "ne-IN": "ne", "en-IN": "en" };
  const attr = (code) => ATTR[code] || "en";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // Interface words in the user's language (hand-written; please have native speakers review).
  const T = {
    "en-IN": { tap: "Tap to speak", listening: "Listening… tap to stop", working: "Getting your answer…", speaking: "Speaking… tap to stop",
      type: "Or type your question", send: "Send", emergency: "Emergency help", nearby: "Find a nearby hospital", useLocation: "Use my location",
      place: "Village, town, PIN code or landmark", search: "Search", replay: "Play again", stop: "Stop", simpler: "Simpler words",
      youSaid: "You said", redo: "Not what you said? Speak again", change: "Change language", call112: "Call 112", mute: "Mute voice",
      why: "Your location is used only to find nearby health facilities. It is not stored." },
    "hi-IN": { tap: "बोलने के लिए दबाएँ", listening: "सुन रहा हूँ… रुकने के लिए दबाएँ", working: "जवाब तैयार हो रहा है…", speaking: "बोल रहा हूँ… रोकने के लिए दबाएँ",
      type: "या अपना सवाल यहाँ लिखें", send: "भेजें", emergency: "आपातकालीन मदद", nearby: "पास का अस्पताल खोजें", useLocation: "मेरी लोकेशन इस्तेमाल करें",
      place: "गाँव, शहर, पिन कोड या पहचान की जगह", search: "खोजें", replay: "फिर से सुनें", stop: "रोकें", simpler: "और आसान शब्दों में",
      youSaid: "आपने कहा", redo: "गलत सुना? फिर से बोलें", change: "भाषा बदलें", call112: "112 पर कॉल करें", mute: "आवाज़ बंद",
      why: "आपकी लोकेशन सिर्फ़ पास की स्वास्थ्य सुविधाएँ खोजने के लिए इस्तेमाल होती है, सहेजी नहीं जाती।" },
    "as-IN": { tap: "ক'বলৈ টিপক", listening: "শুনি আছোঁ… বন্ধ কৰিবলৈ টিপক", working: "উত্তৰ প্ৰস্তুত হৈ আছে…", speaking: "কৈ আছোঁ… ৰখাবলৈ টিপক",
      type: "বা আপোনাৰ প্ৰশ্ন ইয়াত লিখক", send: "পঠিয়াওক", emergency: "জৰুৰী সহায়", nearby: "ওচৰৰ হাস্পতাল বিচাৰক", useLocation: "মোৰ লোকেশ্বন ব্যৱহাৰ কৰক",
      place: "গাঁও, চহৰ, পিন ক'ড বা চিনাকি ঠাই", search: "বিচাৰক", replay: "আকৌ শুনক", stop: "ৰখাওক", simpler: "আৰু সহজ ভাষাত",
      youSaid: "আপুনি ক'লে", redo: "ভুল শুনিলে? আকৌ কওক", change: "ভাষা সলনি কৰক", call112: "112 ত ফোন কৰক", mute: "মাত বন্ধ",
      why: "আপোনাৰ লোকেশ্বন কেৱল ওচৰৰ স্বাস্থ্য সেৱা বিচাৰিবলৈ ব্যৱহাৰ হয়, সংৰক্ষণ কৰা নহয়।" },
    "bn-IN": { tap: "বলতে চাপুন", listening: "শুনছি… থামাতে চাপুন", working: "উত্তর তৈরি হচ্ছে…", speaking: "বলছি… থামাতে চাপুন",
      type: "অথবা প্রশ্নটি এখানে লিখুন", send: "পাঠান", emergency: "জরুরি সাহায্য", nearby: "কাছের হাসপাতাল খুঁজুন", useLocation: "আমার লোকেশন ব্যবহার করুন",
      place: "গ্রাম, শহর, পিন কোড বা পরিচিত জায়গা", search: "খুঁজুন", replay: "আবার শুনুন", stop: "থামান", simpler: "আরও সহজ ভাষায়",
      youSaid: "আপনি বললেন", redo: "ভুল শুনেছি? আবার বলুন", change: "ভাষা বদলান", call112: "112 নম্বরে ফোন করুন", mute: "শব্দ বন্ধ",
      why: "আপনার লোকেশন শুধু কাছের স্বাস্থ্যকেন্দ্র খুঁজতে ব্যবহার হয়, সংরক্ষণ করা হয় না।" },
  };
  const t = (k) => (T[S.lang] && T[S.lang][k]) || T["en-IN"][k];
  const uiLang = () => attr(S.lang && T[S.lang] ? S.lang : "en-IN");
  const current = () => S.langs.find((l) => l.code === S.lang);
  function applyWords() {
    document.querySelectorAll("[data-t]").forEach((n) => { n.textContent = t(n.dataset.t); n.lang = uiLang(); });
    document.querySelectorAll("[data-tp]").forEach((n) => { n.placeholder = t(n.dataset.tp); n.lang = uiLang(); });
    el.changeLang.textContent = `${current() ? current().native_name : ""} · ${t("change")}`;
    setState(S.state);
  }

  // ---------- API with timeouts ----------
  async function api(path, opts = {}, timeoutMs = 60000) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const res = await fetch(path, { signal: ctrl.signal, headers: opts.body instanceof FormData ? {} : { "Content-Type": "application/json" }, ...opts });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Server error (${res.status})`);
      return data;
    } catch (e) {
      if (e.name === "AbortError") throw new Error("The server took too long. Check your connection and try again.");
      if (e instanceof TypeError) throw new Error("Could not reach the server. Check your internet connection.");
      throw e;
    } finally { clearTimeout(timer); }
  }
  const post = (path, body, ms) => api(path, { method: "POST", body: body instanceof FormData ? body : JSON.stringify(body || {}) }, ms);

  // ---------- language picker ----------
  function renderLanguages() {
    const usable = S.langs.filter((l) => l.status !== "unavailable");
    el.langGrid.innerHTML = usable.map((l) => `
      <button type="button" class="lang" data-code="${l.code}" ${l.selectable ? "" : "disabled"}>
        <span class="native" lang="${attr(l.code)}">${esc(l.native_name)}</span>
        <span class="eng">${esc(l.name)}</span>
        <span class="cap">${esc(l.summary)}</span>
        ${l.verified.passed ? `<span class="vf yes">Verified live ${esc(l.verified.date)}</span>` : (l.selectable ? '<span class="vf">Not yet verified live</span>' : "")}
      </button>`).join("");
    el.langGrid.querySelectorAll(".lang").forEach((b) => (b.onclick = () => chooseLanguage(b.dataset.code)));
    const gone = S.langs.filter((l) => l.status === "unavailable");
    el.unavailableList.innerHTML = gone.map((l) => `<li><b>${esc(l.name)}</b> (${esc(l.native_name)}): ${esc(l.notes)}</li>`).join("");
    el.unavailableBox.hidden = !gone.length;
  }

  async function chooseLanguage(code) {
    try {
      const r = await post("/api/conversations", { language: code });
      S.conv = r.id; S.lang = code;
      try { localStorage.setItem("saathi-lang", code); } catch (_) { /* optional */ }
      el.turns.innerHTML = "";
      el.langStep.hidden = true; el.talkStep.hidden = false;
      const cap = current();
      el.mic.disabled = !cap.speech_input;
      applyWords();
      el.micHelp.textContent = cap.speech_input ? "" : "Speech recognition is not set up for this language. Please type.";
    } catch (e) { el.configBanner.hidden = false; el.configBanner.textContent = e.message; }
  }
  el.changeLang.onclick = () => {
    stopAudio();
    if (S.conv) api(`/api/conversations/${S.conv}`, { method: "DELETE" }).catch(() => {});
    S.conv = null; el.talkStep.hidden = true; el.facilityPanel.hidden = true; el.langStep.hidden = false;
  };

  // ---------- the big button's states ----------
  function setState(state) {
    S.state = state;
    el.mic.dataset.state = state;
    const label = t({ idle: "tap", listening: "listening", working: "working", speaking: "speaking" }[state]);
    el.micLabel.textContent = label;
    el.micLabel.lang = uiLang();
    el.mic.setAttribute("aria-label", label);
    el.mic.setAttribute("aria-busy", String(state === "working"));
  }

  // ---------- audio playback ----------
  function play(voice) {
    if (!voice || !voice.audio_url || el.mute.checked) return;
    el.player.src = voice.audio_url;
    el.player.play().then(() => setState("speaking")).catch(() => setState("idle"));
  }
  function stopAudio() {
    el.player.pause();
    if (S.state === "speaking") setState("idle");
  }
  el.player.onended = el.player.onerror = () => { if (S.state === "speaking") setState("idle"); };
  el.mute.onchange = () => {
    if (el.mute.checked) stopAudio();
    try { localStorage.setItem("saathi-mute", el.mute.checked ? "1" : ""); } catch (_) { /* optional */ }
  };

  // ---------- microphone → 16 kHz mono WAV ----------
  let rec = null;
  async function startListening() {
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      el.micHelp.textContent = "This browser cannot record audio. Please type your question.";
      return;
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    } catch (_) {
      el.micHelp.textContent = "Microphone permission was refused. Allow the microphone in your browser settings, or type your question.";
      return;
    }
    const chunks = [];
    const mr = new MediaRecorder(stream);
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const analyser = ctx.createAnalyser();
    ctx.createMediaStreamSource(stream).connect(analyser);
    const buf = new Uint8Array(analyser.fftSize);
    const started = Date.now();
    const tick = setInterval(() => {
      analyser.getByteTimeDomainData(buf);
      let peak = 0;
      for (const v of buf) peak = Math.max(peak, Math.abs(v - 128));
      el.meter.style.setProperty("--level", (1 + peak / 128).toFixed(2));
      const secs = Math.round((Date.now() - started) / 1000);
      el.micHelp.textContent = `● ${secs}s`;
      if (secs >= 60) stopListening();
    }, 100);
    mr.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    mr.onstop = async () => {
      clearInterval(tick);
      stream.getTracks().forEach((tr) => tr.stop());
      ctx.close();
      el.micHelp.textContent = "";
      if (Date.now() - started < 700) { setState("idle"); el.micHelp.textContent = "Tap once, speak, then tap again to finish."; return; }
      try { sendSpeech(await toWav(new Blob(chunks, { type: mr.mimeType || "audio/webm" }))); }
      catch (_) { setState("idle"); el.micHelp.textContent = "Could not read the recording. Please try again or type."; }
    };
    rec = mr;
    mr.start();
    setState("listening");
  }
  function stopListening() {
    if (rec && rec.state === "recording") { rec.stop(); setState("working"); }
    rec = null;
  }

  // Small, uniform uploads for slow links: 16 kHz mono 16-bit PCM WAV, accepted by both STT providers.
  async function toWav(blob) {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const decoded = await ctx.decodeAudioData(await blob.arrayBuffer());
    ctx.close();
    const rate = 16000;
    const off = new OfflineAudioContext(1, Math.ceil(decoded.duration * rate), rate);
    const src = off.createBufferSource();
    src.buffer = decoded; src.connect(off.destination); src.start();
    const pcm = (await off.startRendering()).getChannelData(0);
    const out = new DataView(new ArrayBuffer(44 + pcm.length * 2));
    const w = (o, s) => [...s].forEach((c, i) => out.setUint8(o + i, c.charCodeAt(0)));
    w(0, "RIFF"); out.setUint32(4, 36 + pcm.length * 2, true); w(8, "WAVE"); w(12, "fmt ");
    out.setUint32(16, 16, true); out.setUint16(20, 1, true); out.setUint16(22, 1, true);
    out.setUint32(24, rate, true); out.setUint32(28, rate * 2, true); out.setUint16(32, 2, true); out.setUint16(34, 16, true);
    w(36, "data"); out.setUint32(40, pcm.length * 2, true);
    for (let i = 0; i < pcm.length; i++) out.setInt16(44 + i * 2, Math.max(-1, Math.min(1, pcm[i])) * 0x7fff, true);
    return new Blob([out], { type: "audio/wav" });
  }

  el.mic.onclick = () => {
    if (S.state === "listening") return stopListening();
    if (S.state === "speaking") return stopAudio();
    if (S.state === "idle") startListening();
  };

  // ---------- asking ----------
  async function sendSpeech(wav) {
    setState("working");
    const fd = new FormData();
    fd.append("audio", wav, "question.wav");
    try {
      const r = await post(`/api/conversations/${S.conv}/speech`, fd, 90000);
      if (r.error) { addProblem(r.error, r.hint); setState("idle"); return; }
      showTurn(r.turn);
    } catch (e) { addProblem({ message: e.message }); setState("idle"); }
  }
  async function ask(text, simpler = false) {
    stopAudio();
    setState("working");
    try {
      const turn = simpler ? await post(`/api/conversations/${S.conv}/simpler`, {}, 90000)
        : await post(`/api/conversations/${S.conv}/ask`, { text }, 90000);
      showTurn(turn);
    } catch (e) { addProblem({ message: e.message }); setState("idle"); }
  }
  el.typeForm.onsubmit = (e) => {
    e.preventDefault();
    const v = el.typeInput.value.trim();
    el.typeInput.value = "";
    if (v && S.state !== "working") ask(v);
  };

  // ---------- rendering ----------
  function add(html, cls) {
    const n = document.createElement("li");
    n.className = cls; n.innerHTML = html;
    el.turns.appendChild(n);
    n.scrollIntoView({ block: "nearest", behavior: "smooth" });
    return n;
  }
  function addProblem(err, hint) {
    add(`<span class="label">PROBLEM</span><p class="text" style="font-size:1.05rem">${esc(err.message)}</p>
      ${hint ? `<p class="note" lang="${attr(hint.lang)}">${esc(hint.text)}</p>` : ""}`, "card problem");
  }

  function showTurn(turn) {
    const q = turn.question;
    const you = add(`<span class="label">${esc(t("youSaid"))}${turn.level === "simple" ? ` · ${esc(t("simpler"))}` : ""}</span><p lang="${attr(q.lang)}">${esc(q.text)}</p>
      ${q.stt ? `<button type="button" class="link-btn redo">${esc(t("redo"))}</button>` : ""}`, "you");
    const redo = you.querySelector(".redo");
    if (redo) redo.onclick = () => { stopAudio(); startListening(); };

    if (turn.error && !turn.answer) {
      addProblem(turn.error);
      if (turn.notes.length) add(`<p class="note">${esc(turn.notes.join(" "))}</p>`, "card problem");
      setState("idle");
      return;
    }
    const a = turn.answer, tri = turn.triage;
    const isEm = ["emergency", "crisis"].includes(tri.level);
    const why = tri.matches.map((m) => m.label).join(", ");
    const secs = (Object.values(turn.timings_ms).reduce((x, y) => x + y, 0) / 1000).toFixed(1);
    const meta = isEm
      ? `Safety check: ${esc(why)}. ${tri.source === "rules" ? "Found by the safety rules; the AI was not used." : "Flagged by the AI safety check."}`
      : `AI answer (${esc(a.model)})${q.lang !== "en-IN" && a.lang === q.lang ? " · translated by Sarvam" : ""} · ${secs} s`;
    const card = add(`
      <span class="label">${isEm ? (tri.level === "crisis" ? "SUPPORT" : "! EMERGENCY") : "AAROGYA SAATHI"}</span>
      ${tri.level === "urgent" ? '<span class="tag urgent">See a health worker within a day</span>' : ""}
      <p class="text" lang="${attr(a.lang)}">${esc(a.text)}</p>
      ${a.language_note ? `<p class="note">${esc(a.language_note)}</p>` : ""}
      ${turn.medicine.request ? `<p class="note">Aarogya Saathi does not prescribe medicines or doses. Ask a doctor, nurse or pharmacist.${turn.medicine.dose_removed ? " A dose in the AI's answer was removed." : ""}</p>` : ""}
      ${turn.voice && turn.voice.note ? `<p class="note">${esc(turn.voice.note)}</p>` : ""}
      ${turn.notes.length ? `<p class="note">${esc(turn.notes.join(" "))}</p>` : ""}
      <div class="actions">
        ${isEm ? `<a class="call" href="tel:112">${esc(t("call112"))}</a>` : ""}
        ${turn.offer_facilities ? `<button type="button" data-act="find">${esc(t("nearby"))}</button>` : ""}
        ${turn.voice && turn.voice.audio_url ? `<button type="button" data-act="replay">${esc(t("replay"))}</button><button type="button" data-act="stop">${esc(t("stop"))}</button>` : ""}
        ${!isEm ? `<button type="button" data-act="simpler">${esc(t("simpler"))}</button>` : ""}
      </div>
      <p class="meta">${meta}</p>`, `card ${isEm ? "emergency" : "answer"}`);
    const acts = { find: () => openFacilities(true), replay: () => play(turn.voice), stop: stopAudio, simpler: () => ask("", true) };
    card.querySelectorAll("[data-act]").forEach((b) => { b.onclick = acts[b.dataset.act]; });
    setState("idle");
    play(turn.voice);
    if (turn.offer_facilities) openFacilities(true, a.location_prompt, false);
  }

  // ---------- emergency button: instant, no AI ----------
  el.emergencyBtn.onclick = async () => {
    stopAudio();
    try {
      const r = await api(`/api/emergency?lang=${encodeURIComponent(S.lang || "en-IN")}`, {}, 20000);
      const c = add(`<span class="label">! EMERGENCY</span><p class="text" lang="${attr(r.message.lang)}">${esc(r.message.text)}</p>
        ${r.voice.note ? `<p class="note">${esc(r.voice.note)}</p>` : ""}
        <div class="actions"><a class="call" href="tel:112">${esc(t("call112"))}</a><a href="tel:108">108</a>
        <button type="button" data-act="find">${esc(t("nearby"))}</button></div>`, "card emergency");
      c.querySelector("[data-act=find]").onclick = () => openFacilities(true);
      play(r.voice);
      openFacilities(true, r.location_prompt, false);
    } catch (_) {
      add('<span class="label">! EMERGENCY</span><p class="text">Call 112 now.</p><div class="actions"><a class="call" href="tel:112">Call 112</a></div>', "card emergency");
    }
  };

  // ---------- nearby facilities (location only on request) ----------
  function openFacilities(emergency, prompt, scroll = true) {
    S.emergencyContext = !!emergency;
    el.facilityPanel.hidden = false;
    if (prompt) el.facResults.innerHTML = `<p class="why" lang="${attr(prompt.lang)}">${esc(prompt.text)}</p>`;
    if (scroll) el.facilityPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  el.findBtn.onclick = () => openFacilities(false);
  el.facClose.onclick = () => { el.facilityPanel.hidden = true; };
  el.gpsBtn.onclick = () => {
    if (!navigator.geolocation) { el.facResults.innerHTML = '<p class="why">This device cannot share its location. Type a place name instead.</p>'; return; }
    el.facResults.innerHTML = '<p class="why">Asking for your location…</p>';
    navigator.geolocation.getCurrentPosition(
      (p) => searchFacilities({ lat: p.coords.latitude, lon: p.coords.longitude, accuracy_m: Math.round(p.coords.accuracy) }),
      (err) => {
        el.facResults.innerHTML = `<p class="why">${err.code === 1 ? "Location permission was refused." : "Your location could not be found."} Type your village, town, PIN code or a landmark instead.</p>`;
        el.placeInput.focus();
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
  };
  el.placeForm.onsubmit = (e) => { e.preventDefault(); const v = el.placeInput.value.trim(); if (v) searchFacilities({ text: v }); };

  const KIND = { hospital: "Hospital", health_centre: "Health centre", clinic: "Clinic" };
  async function searchFacilities(body) {
    el.facResults.innerHTML = '<p class="why">Searching…</p>';
    try {
      const r = await post("/api/facilities/search", { ...body, emergency: S.emergencyContext }, 45000);
      const nums = `<div class="numbers">${r.emergency_numbers.map((n) => `<a href="tel:${esc(n.number)}"><b>${esc(n.number)}</b>${esc(n.label)}</a>`).join("")}</div>`;
      const place = r.place ? `<p class="fac-place">Near: <b>${esc(r.place.name)}</b>${r.place.detail ? `, ${esc(r.place.detail)}` : ""} <span class="small">(${esc(r.place.method)}${r.place.approximate ? ", approximate" : ""})</span></p>` : "";
      const problems = [r.error && r.error.message, r.limitation].filter(Boolean).map((m) => `<p class="why">${esc(m)}</p>`).join("");
      const list = r.facilities.map((f) => `
        <li class="fac">
          <span class="kind">${esc(KIND[f.kind] || f.kind)}</span>
          <h3>${esc(f.name)}<span class="km">${f.distance_km} km</span></h3>
          <p class="${f.emergency === "yes" ? "em-yes" : ""}">${esc(f.emergency_label)}</p>
          ${f.address ? `<p>${esc(f.address)}</p>` : ""}
          <p>${esc(f.phone_label)}</p>
          <div class="actions">${f.phone ? `<a href="tel:${esc(f.phone.replace(/[^\d+]/g, ""))}">Call ${esc(f.phone)}</a>` : ""}
            <a href="${esc(f.directions_url)}" target="_blank" rel="noopener">Directions</a></div>
          <p class="small">${esc(f.data_label)}</p>
        </li>`).join("");
      el.facResults.innerHTML = `<p class="notice">${esc(r.notice)}</p>${nums}${place}${problems}
        ${list ? `<ol class="fac-list">${list}</ol><p class="small">${esc(r.distance_note)}</p>` : ""}
        ${r.attribution ? `<p class="small">${esc(r.attribution)}</p>` : ""}`;
    } catch (e) { el.facResults.innerHTML = `<p class="why">${esc(e.message)}</p>`; }
  }

  // ---------- boot ----------
  const online = () => { el.offline.hidden = navigator.onLine; };
  window.addEventListener("online", online);
  window.addEventListener("offline", online);
  online();
  try { el.mute.checked = localStorage.getItem("saathi-mute") === "1"; } catch (_) { /* optional */ }
  (async () => {
    try {
      const [health, langs] = await Promise.all([api("/api/health"), api("/api/languages")]);
      S.health = health.providers; S.langs = langs.languages;
      const p = S.health;
      el.status.textContent = p.llm.configured ? "AI ready" : "AI not set up";
      el.status.classList.toggle("bad", !p.llm.configured);
      const needs = [p.llm.needs, p.translation.needs].filter(Boolean);
      el.configBanner.hidden = !needs.length;
      el.configBanner.textContent = needs.length ? `Server setup needed: ${needs.join(" ")}` : "";
      renderLanguages();
      let saved = null;
      try { saved = localStorage.getItem("saathi-lang"); } catch (_) { /* optional */ }
      if (saved && S.langs.some((l) => l.code === saved && l.selectable)) await chooseLanguage(saved);
    } catch (e) {
      el.status.textContent = "Offline";
      el.status.classList.add("bad");
      el.configBanner.hidden = false;
      el.configBanner.textContent = `Cannot reach the Aarogya Saathi server. ${e.message}`;
    }
    applyWords();
  })();
})();
