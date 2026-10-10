/* Aarogya Saathi - Retro Nokia Handset UI
   Talks to the live Aarogya Saathi backend (LLM, Sarvam STT/TTS, OSM Facilities).
   Handset follows docs/DESIGN.md: monochrome LCD, keypad lighting, DTMF tones, call log. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const el = {
    mode: $("mode"), lcd: $("lcd"), body: $("lcdBody"), lang: $("lcdLang"), rec: $("lcdRec"),
    up: $("arrowUp"), down: $("arrowDown"), softLLabel: $("softLLabel"), softRLabel: $("softRLabel"),
    softL: $("softL"), softR: $("softR"), navUp: $("navUp"), navDown: $("navDown"),
    call: $("callBtn"), end: $("endBtn"), keypad: $("keypad"), phone: $("phone"), wrap: $("phoneWrap"),
    typeForm: $("typeForm"), typeInput: $("typeInput"), typeSend: $("typeSend"), typeLabel: $("typeLabel"),
    scenarios: $("scenarios"), chips: $("scenarioChips"), scenarioLabel: $("scenarioLabel"), mute: $("muteToggle"),
    turns: $("turns"), convoEmpty: $("convoEmpty"), langRows: $("langRows"), player: $("player"),
    facSearchInput: $("facSearchInput"), facSearchBtn: $("facSearchBtn"), facGpsBtn: $("facGpsBtn"), hospitalsList: $("hospitalsList"),
  };

  const S = {
    convId: null,
    phase: "idle", // idle | calling | language | ready | answered | emergency | location | help | ended
    view: "main",  // main | menu | notice
    lang: "as-IN",
    languages: [],
    lastTurn: null,
    health: null,
    menuSel: 0,
    startedAt: 0,
    busy: false,
    recording: false,
    help: null,
    pinBuf: "",
  };

  const SCRIPT_ATTR = { "as-IN": "as", "bn-IN": "bn", "mni-IN": "mni", "hi-IN": "hi", "brx-IN": "brx", "ne-IN": "ne", "en-IN": "en" };
  const STEP_COLORS = { speech_to_text: "#46566A", translate_in: "#7A8B5C", safety_rules: "#5E6670", llm: "#26331A", translate_out: "#A9B88A", voice: "#3E9B4F" };
  const STEP_NAMES = { speech_to_text: "Speech to text", translate_in: "Translate to English", safety_rules: "Safety rules", llm: "AI answer", translate_out: "Translate back", voice: "Voice" };

  const SAMPLE_QUESTIONS = [
    { title: "Fever for two days", questions: {
      "as-IN": "মোৰ দুদিন ধৰি জ্বৰ হৈছে, কি কৰিম?",
      "hi-IN": "मुझे दो दिन से बुखार है, क्या करूँ?",
      "en-IN": "I have had a fever for two days. What should I do?",
      "bn-IN": "আমার দুদিন ধরে জ্বর, কী করব?",
      "ne-IN": "मलाई दुई दिनदेखि ज्वरो छ, के गर्ने?" } },
    { title: "Severe chest pain (Emergency)", questions: {
      "as-IN": "মোৰ দেউতাৰ বুকুৰ বিষ হৈছে আৰু বহুত ঘাম ওলাইছে।",
      "hi-IN": "मेरे पिता के सीने में दर्द है और बहुत पसीना आ रहा है।",
      "en-IN": "My father has severe chest pain and is sweating heavily.",
      "bn-IN": "আমার বাবার বুকে তীব্র ব্যথা এবং প্রচুর ঘাম হচ্ছে।",
      "ne-IN": "मेरो बुबाको छातीमा धेरै दुखाइ छ र पसिना आइरहेको छ।" } },
    { title: "Ask about paracetamol", questions: {
      "as-IN": "জ্বৰৰ বাবে পেৰাচিতামল কেনেকৈ খাব লাগে?",
      "hi-IN": "बुखार के लिए पैरासिटामोल कैसे लेनी चाहिए?",
      "en-IN": "How should paracetamol be taken for fever?",
      "bn-IN": "জ্বরের জন্য প্যারাসিটামল কীভাবে নেওয়া উচিত?",
      "ne-IN": "ज्वरोको लागि प्यारासिटामोल कसरी लिने?" } },
  ];

  const LOCATION_CHIPS = ["Jalukbari, Guwahati", "781014", "Dispur", "Silchar", "Dibrugarh", "Tezpur"];

  const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- API ----------
  async function api(path, opts = {}) {
    const res = await fetch(path, {
      headers: opts.body instanceof FormData ? {} : { "Content-Type": "application/json" },
      ...opts,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || data.message || `Request failed (${res.status})`);
    return data;
  }
  const post = (path, body) => api(path, { method: "POST", body: body instanceof FormData ? body : JSON.stringify(body || {}) });

  // ---------- pixel icons (12×12) ----------
  const ICONS = {
    heart: ["............", ".###....###.", "#####..#####", "#####..#####", "###......###", "###......###",
      ".####..####.", "..###..###..", "...######...", "....####....", ".....##.....", "............"],
    handset: [".##.........", "####........", "####........", ".###........", "..##........", "..###.......",
      "...###......", "....###.....", ".....####.##", "......######", ".......#####", ".........##."],
    mic: ["....####....", "...######...", "...######...", "...######...", "...######...", ".#.######.#.",
      ".#..####..#.", "..#......#..", "...######...", ".....##.....", ".....##.....", "...######..."],
    hourglass: ["############", ".#........#.", ".#.######.#.", "..#.####.#..", "...#.##.#...", "....#..#....",
      "....#..#....", "...#....#...", "..#......#..", ".#........#.", ".#........#.", "############"],
    alert: [".....##.....", "....####....", "....#..#....", "...##..##...", "...#.##.#...", "..##.##.##..",
      "..#..##..#..", ".##..##..##.", ".#........#.", "##...##...##", "#..........#", "############"],
    battery: ["............", "............", "............", "##########..", "#........#..", "#.##.##..###",
      "#.##.##..###", "#........#..", "##########..", "............", "............", "............"],
  };
  function pix(name, cls = "pix") {
    const rows = ICONS[name] || ICONS.heart;
    let rects = "";
    rows.forEach((row, y) => { for (let x = 0; x < 12; x++) if (row[x] === "#") rects += `<rect x="${x}" y="${y}" width="1" height="1"/>`; });
    return `<svg class="${cls}" viewBox="0 0 12 12" aria-hidden="true">${rects}</svg>`;
  }
  function signalSvg(level, cls = "") {
    let r = "";
    for (let i = 0; i < 4; i++) {
      const h = 3 * (i + 1);
      r += `<rect class="${i < level ? "lit" : "unlit"}" x="${i * 3}" y="${12 - h}" width="2" height="${h}"/>`;
    }
    return `<svg class="${cls}" viewBox="0 0 12 12" aria-hidden="true" shape-rendering="crispEdges">${r}</svg>`;
  }
  $("icoSignal").innerHTML = signalSvg(4).replace(/class="unlit"/g, 'opacity=".2"');
  $("icoBattery").innerHTML = pix("battery");

  // ---------- LCD ----------
  let typeTimer = null;
  function esc(s) { return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
  const langAttr = (code) => SCRIPT_ATTR[code] || "en";

  function lcd({ html = "", type = null, lang = "en-IN", mode = "", assertive = false } = {}) {
    clearInterval(typeTimer);
    el.lcd.dataset.mode = mode;
    el.lcd.setAttribute("aria-live", assertive ? "assertive" : "polite");
    el.body.innerHTML = html;
    el.body.scrollTop = 0;
    if (type != null) {
      const p = document.createElement("p");
      p.style.margin = "0";
      p.lang = langAttr(lang);
      el.body.appendChild(p);
      const parts = window.Intl && Intl.Segmenter ? [...new Intl.Segmenter().segment(type)].map((s) => s.segment) : [...type];
      if (reducedMotion() || parts.length < 2) {
        p.textContent = type;
      } else {
        const step = Math.min(25, 1000 / parts.length);
        const per = Math.max(1, Math.ceil(parts.length / (1000 / Math.max(step, 16))));
        let i = 0;
        typeTimer = setInterval(() => {
          i = Math.min(parts.length, i + per);
          p.textContent = parts.slice(0, i).join("");
          if (i >= parts.length) { clearInterval(typeTimer); updateArrows(); }
        }, Math.max(step, 16));
      }
    }
    updateArrows();
    wake();
  }
  function line(text, lang = "en-IN", cls = "") { return `<p style="margin:0" class="${cls}" lang="${langAttr(lang)}">${esc(text)}</p>`; }
  function heading(text, icon = "") { return `<div class="heading">${icon ? pix(icon) + " " : ""}${esc(text)}</div>`; }

  function updateArrows() {
    const b = el.body;
    el.up.hidden = b.scrollTop <= 0;
    el.down.hidden = b.scrollTop + b.clientHeight >= b.scrollHeight - 2;
  }
  function scrollBy(dir) {
    const lh = 26;
    el.body.scrollTop += dir * lh;
    updateArrows();
  }

  function setSoftkeys(left, right) {
    el.softLLabel.textContent = left || "";
    el.softRLabel.textContent = right || "";
    el.softL.setAttribute("aria-label", left ? `Left softkey, ${left}` : "Left softkey");
    el.softR.setAttribute("aria-label", right ? `Right softkey, ${right}` : "Right softkey");
  }
  function softkeysForState() {
    const sub = S.view !== "main";
    switch (S.phase) {
      case "idle": return setSoftkeys("Call", sub ? "Back" : "Menu");
      case "calling": return setSoftkeys("", "");
      case "language": return setSoftkeys("Select", "Back");
      case "ready": return setSoftkeys(S.recording ? "Release" : "Speak", "Type");
      case "answered": return setSoftkeys("Again", sub ? "Back" : "Menu");
      case "emergency": return setSoftkeys("Call 112", sub ? "Back" : "Hospital");
      case "location": return setSoftkeys(S.recording ? "Release" : "GPS", "Back");
      case "help": return setSoftkeys("Call 108", "Back");
      default: return setSoftkeys("", "");
    }
  }

  function langCode(code) { return code ? code.split("-")[0].toUpperCase() : ""; }
  function setStatusLang() { el.lang.textContent = langCode(S.lang); }

  let backlightTimer = null;
  function wake() {
    el.lcd.dataset.backlight = "on";
    clearTimeout(backlightTimer);
    backlightTimer = setTimeout(() => { el.lcd.dataset.backlight = "off"; }, 10000);
  }

  function flashAmber() {
    if (reducedMotion()) return;
    el.lcd.classList.remove("flash");
    void el.lcd.offsetWidth;
    el.lcd.classList.add("flash");
    setTimeout(() => el.lcd.classList.remove("flash"), 1100);
  }

  // ---------- Screens ----------
  function clock() { const d = new Date(); return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; }
  function screenIdle() {
    S.view = "main";
    lcd({ html: `<div class="center">${pix("heart", "pix big")}<span>AAROGYA</span><span>SAATHI</span><span>health line</span><span>${clock()}</span></div>` });
    softkeysForState();
  }
  function screenCalling() {
    lcd({ html: `<div class="center" style="margin-top:22px">${pix("handset", "pix big")}<span class="dots">Connecting</span></div>` });
    softkeysForState();
  }
  function screenText(title, text, lang = "en-IN", icon = "") {
    lcd({ html: title ? heading(title, icon) : "", type: text, lang });
  }
  function screenThinking(text) {
    lcd({ html: `<div class="center" style="margin-top:10px"><span class="hourglass">${pix("hourglass", "pix big")}</span><span>${esc(text || "Thinking")}</span></div>` });
  }
  function screenListening() {
    lcd({ html: `<div class="center"><div class="eq">${"<i></i>".repeat(8)}</div>${pix("mic")}<span>Listening…</span></div>` });
  }
  function screenReady() {
    S.view = "main";
    const curLang = S.languages.find((l) => l.code === S.lang);
    const nativeName = curLang ? curLang.native_name : S.lang;
    lcd({ html: heading(`Line ready (${nativeName})`), type: "Hold Speak, or type below. Press 4 for nearest hospital.", lang: S.lang });
    softkeysForState();
  }

  function langMenuItems() {
    const list = S.languages.filter((l) => l.selectable !== false);
    return list.map((l, i) => ({
      digit: String(i + 1),
      label: l.native_name,
      code: l.code,
      name: l.name,
    }));
  }
  function screenLanguage() {
    const items = langMenuItems();
    S.menuSel = Math.max(0, Math.min(S.menuSel, items.length - 1));
    const rows = items.map((it, i) => `<li class="${i === S.menuSel ? "selected" : ""}"><b>${it.digit}</b><span lang="${langAttr(it.code)}">${esc(it.label)} (${esc(it.name)})</span></li>`).join("");
    clearInterval(typeTimer);
    el.lcd.dataset.mode = "";
    el.body.innerHTML = `${heading("Choose language")}<ul class="menu" aria-label="Languages">${rows}</ul>`;
    const sel = el.body.querySelector(".selected");
    if (sel) {
      const top = sel.offsetTop - el.body.offsetTop, bottom = top + sel.offsetHeight;
      if (top < el.body.scrollTop + 26) el.body.scrollTop = Math.max(0, top - 26);
      else if (bottom > el.body.scrollTop + el.body.clientHeight) el.body.scrollTop = bottom - el.body.clientHeight;
    }
    updateArrows(); wake();
    softkeysForState();
  }

  function screenAnswer(turn, { animate = true } = {}) {
    S.view = "main";
    const lvl = (turn.triage && turn.triage.level) || "none";
    if (lvl === "emergency") {
      const head = `<div class="inv">${pix("alert")}<span>! EMERGENCY 112</span></div>`;
      lcd({ html: head, type: turn.answer.text, lang: turn.answer.lang, mode: "emergency", assertive: true });
      if (animate) flashAmber();
    } else {
      lcd({ html: "", type: turn.answer.text, lang: turn.answer.lang });
    }
    softkeysForState();
  }

  function screenMenu() {
    S.view = "menu";
    lcd({ html: heading("Menu"), type: "1 Ask  2 Repeat  3 Language  4 Hospital  5 Simpler  9 End  0 Emergency", lang: "en-IN" });
    softkeysForState();
  }

  function screenNotice(title, text, mode = "") {
    S.view = "notice";
    lcd({ html: heading(title), type: text, mode });
    softkeysForState();
  }

  function screenLocation(extra = "") {
    S.view = "main";
    const p = "Where are you? Say or type your village, town, PIN code or press GPS.";
    const pin = S.pinBuf ? line(`PIN: ${S.pinBuf.padEnd(6, "_")}`) : "";
    lcd({ html: heading("Find Hospital") + pin + (extra ? line(extra) : ""), type: S.pinBuf ? null : p, lang: "en-IN" });
    softkeysForState();
  }

  function shortName(n) {
    return String(n || "").replace(/\s*\(.*?\)/g, "").replace(/ Medical College( and Hospital)?/, " MC").replace(/ and Hospital/, "").slice(0, 16);
  }
  function screenHelp(r) {
    S.view = "main";
    const list = (r.facilities || []).slice(0, 3);
    const rows = list.map((f, i) => `<li><b>${i + 1}</b>${f.distance_km ? f.distance_km + "km " : ""}${esc(shortName(f.name))}</li>`).join("");
    const head = r.emergency ? `<div class="inv">${pix("alert")}<span>Nearest help</span></div>` : heading("Nearest hospitals");
    lcd({ html: `${head}<ul class="menu">${rows || "<li>No results</li>"}</ul>${line("Call 108 ambulance · 112")}`, mode: r.emergency ? "emergency" : "" });
    softkeysForState();
  }
  function screenFacility(f) {
    S.view = "notice";
    const bits = [
      f.distance_km ? `${f.distance_km} km` : null,
      f.address || (f.district ? `${f.district}, ${f.state}` : null),
      f.phone ? `Phone: ${f.phone}` : null,
      f.verified ? "Verified 24x7" : "Community listed"
    ].filter(Boolean);
    lcd({ html: heading(shortName(f.name)), type: bits.join("\n") });
    softkeysForState();
  }

  function screenEnded() {
    const secs = Math.round((Date.now() - S.startedAt) / 1000);
    const dur = [Math.floor(secs / 3600), Math.floor(secs / 60) % 60, secs % 60].map((n) => String(n).padStart(2, "0")).join(":");
    lcd({ html: `<div class="heading">Call ended<br>${dur}</div><p style="margin:8px 0 0">Thank you for calling.</p><p style="margin:0">Press CALL to connect again.</p>` });
    softkeysForState();
  }

  // ---------- Sound effects (Web Audio API) ----------
  let ctx;
  const DTMF = { 1: [697, 1209], 2: [697, 1336], 3: [697, 1477], 4: [770, 1209], 5: [770, 1336], 6: [770, 1477],
    7: [852, 1209], 8: [852, 1336], 9: [852, 1477], "*": [941, 1209], 0: [941, 1336], "#": [941, 1477] };
  function beep(freqs, start, dur, gain = 0.06) {
    if (el.mute.checked) return;
    try {
      ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
      const t = ctx.currentTime + start;
      const g = ctx.createGain(); g.gain.value = gain; g.connect(ctx.destination);
      freqs.forEach((f) => { const o = ctx.createOscillator(); o.frequency.value = f; o.connect(g); o.start(t); o.stop(t + dur); });
    } catch (_) {}
  }
  const sfx = {
    key: (d) => DTMF[d] && beep(DTMF[d], 0, 0.12),
    soft: () => beep([1400], 0, 0.04, 0.04),
    ring: () => { beep([440, 480], 0, 0.35); beep([440, 480], 0.5, 0.35); },
    blip: () => beep([880], 0, 0.06, 0.04),
    alert: () => { [0, 0.22, 0.44].forEach((t) => beep([1046], t, 0.14, 0.07)); },
    end: () => beep([480, 620], 0, 0.45),
  };

  // ---------- Voice playback ----------
  function stopAudio() {
    if (el.player) {
      el.player.pause();
      el.player.removeAttribute("src");
    }
  }
  function playVoice(voice) {
    if (!voice || !voice.audio_url || el.mute.checked) return;
    stopAudio();
    el.player.src = voice.audio_url;
    el.player.play().catch(() => {});
  }

  // ---------- Controls ----------
  function setControls() {
    const inCall = !!S.convId && !["ended", "idle", "calling"].includes(S.phase);
    const canAsk = inCall && ["ready", "answered", "emergency", "location"].includes(S.phase) && !S.busy;
    el.typeInput.disabled = el.typeSend.disabled = !canAsk;
    el.typeInput.placeholder = S.phase === "location" ? "Village, town, district, PIN code" : "e.g. My child has a fever.";
    el.typeLabel.textContent = S.phase === "location" ? "Type your location" : "Type instead";
    el.scenarios.hidden = !canAsk;
    if (canAsk) renderScenarioChips();
    softkeysForState();
  }

  // ---------- Conversation Lifecycle ----------
  async function startCall() {
    if (S.convId || S.phase === "calling") return;
    stopAudio();
    el.lcd.classList.remove("off");
    S.phase = "calling"; S.lastTurn = null; S.menuSel = 0;
    setStatusLang();
    screenCalling(); sfx.ring();
    try {
      const r = await post("/api/conversations", { language: S.lang });
      S.convId = r.id;
      S.startedAt = Date.now();
      S.phase = "ready";
      screenReady();
    } catch (e) {
      S.phase = "idle";
      screenText("No network", e.message || "Failed to connect");
      softkeysForState();
    }
    setControls();
  }

  async function switchLanguage(code) {
    S.lang = code;
    setStatusLang();
    if (S.convId) {
      try { await api(`/api/conversations/${S.convId}`, { method: "DELETE" }); } catch (_) {}
      S.convId = null;
    }
    await startCall();
  }

  async function askText(text) {
    if (!text.trim() || !S.convId) return;
    stopAudio();
    S.busy = true; setControls();
    screenThinking("Thinking");
    try {
      const turn = await post(`/api/conversations/${S.convId}/ask`, { text, simple: false });
      renderAnswer(turn);
    } catch (e) {
      S.busy = false; screenText("Error", e.message); setControls();
    }
  }

  async function simpler() {
    if (!S.convId || !S.lastTurn) return;
    stopAudio();
    S.busy = true; setControls();
    screenThinking("Simpler words");
    try {
      const turn = await post(`/api/conversations/${S.convId}/simpler`, {});
      renderAnswer(turn);
    } catch (e) {
      S.busy = false; screenText("Error", e.message); setControls();
    }
  }

  function repeat() {
    if (!S.lastTurn) return;
    stopAudio();
    screenAnswer(S.lastTurn, { animate: false });
    if (S.lastTurn.voice) playVoice(S.lastTurn.voice);
  }

  async function endCall() {
    if (!S.convId) {
      if (S.phase !== "idle") { S.phase = "idle"; screenIdle(); setControls(); }
      return;
    }
    stopAudio();
    sfx.end();
    try {
      await api(`/api/conversations/${S.convId}`, { method: "DELETE" });
    } catch (_) {}
    S.convId = null; S.phase = "ended"; S.view = "main"; S.recording = false;
    el.rec.hidden = true;
    screenEnded();
    setControls();
  }

  async function triggerEmergency() {
    stopAudio();
    sfx.alert();
    screenThinking("Emergency");
    try {
      const r = await api(`/api/emergency?lang=${encodeURIComponent(S.lang)}`);
      S.phase = "emergency";
      const fakeTurn = {
        transcript: "EMERGENCY HELP",
        triage: { level: "emergency", matches: [{ label: "Emergency assistance requested" }] },
        answer: { text: r.message.text, lang: r.message.lang, source: "emergency_guidance" },
        voice: r.voice,
        timings_ms: {},
      };
      renderAnswer(fakeTurn);
    } catch (e) {
      screenText("Emergency", "Call 112 for ambulance & police immediately.");
    }
  }

  // ---------- Microphone / Audio recording (16 kHz mono WAV) ----------
  let rec = null;
  async function toWav(blob) {
    const actx = new (window.AudioContext || window.webkitAudioContext)();
    const decoded = await actx.decodeAudioData(await blob.arrayBuffer());
    actx.close();
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

  async function startRecording() {
    if (!S.convId || S.busy || S.recording) return;
    stopAudio();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      const mr = new MediaRecorder(stream);
      const chunks = [];
      mr.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
      mr.onstop = async () => {
        stream.getTracks().forEach((tr) => tr.stop());
        S.recording = false; el.rec.hidden = true; softkeysForState();
        if (chunks.length) {
          try {
            const wavBlob = await toWav(new Blob(chunks, { type: mr.mimeType || "audio/webm" }));
            await sendSpeechAudio(wavBlob);
          } catch (err) {
            screenText("Audio error", err.message);
          }
        }
      };
      rec = mr;
      mr.start();
      S.recording = true; el.rec.hidden = false;
      screenListening();
      softkeysForState();
    } catch (_) {
      screenText("Mic blocked", "Allow microphone access, or type your question.");
    }
  }

  function stopRecording() {
    if (rec && rec.state === "recording") {
      rec.stop();
    }
    rec = null;
  }

  async function sendSpeechAudio(wavBlob) {
    S.busy = true; setControls();
    screenThinking("Transcribing");
    const fd = new FormData();
    fd.append("audio", wavBlob, "question.wav");
    fd.append("simple", "false");
    try {
      const r = await post(`/api/conversations/${S.convId}/speech`, fd);
      if (r.error) {
        screenText("Not understood", r.hint ? r.hint.text : r.error.message, S.lang);
        S.busy = false; setControls();
        return;
      }
      if (r.turn) {
        renderAnswer(r.turn);
      }
    } catch (e) {
      S.busy = false; screenText("Error", e.message); setControls();
    }
  }

  // ---------- Facilities / Hospital Search ----------
  function goLocation() {
    stopAudio();
    S.phase = "location"; S.pinBuf = "";
    screenLocation();
    setControls();
  }

  function useGps() {
    if (!navigator.geolocation) return screenLocation("No GPS found. Say or type a place.");
    screenThinking("Getting GPS");
    navigator.geolocation.getCurrentPosition(
      (pos) => submitFacilitiesSearch({ lat: pos.coords.latitude, lon: pos.coords.longitude, emergency: S.phase === "emergency" }),
      () => screenLocation("Location off. Type a place or PIN."),
      { timeout: 10000, maximumAge: 60000 },
    );
  }

  async function submitFacilitiesSearch(body) {
    S.busy = true; setControls();
    screenThinking("Searching");
    try {
      const r = await post("/api/facilities/search", body);
      S.busy = false; S.pinBuf = "";
      S.phase = "help"; S.help = r;
      screenHelp(r);
      sfx.blip();
      el.convoEmpty.hidden = true;
      el.turns.prepend(helpElement(r));
      renderHospitalsTab(r);
      switchTab("hospitals");
    } catch (e) {
      S.busy = false; S.phase = "location"; screenText("Error", e.message);
    }
    setControls();
  }

  // ---------- Keypad & Softkey Dispatch ----------
  function onDigit(d) {
    sfx.key(d);
    litKeypad();
    if (S.busy) return;

    if (S.phase === "language") {
      const items = langMenuItems();
      const match = items.find((it) => it.digit === d);
      if (match) {
        switchLanguage(match.code);
      }
      return;
    }

    if (S.phase === "location") {
      if (d === "*") { S.pinBuf = ""; return screenLocation(); }
      if (/\d/.test(d) && S.pinBuf.length < 6) {
        S.pinBuf += d; screenLocation();
        if (S.pinBuf.length === 6) submitFacilitiesSearch({ text: S.pinBuf, emergency: false });
      }
      return;
    }

    if (S.phase === "help") {
      const list = (S.help && S.help.facilities) || [];
      const n = Number(d);
      if (n >= 1 && n <= Math.min(3, list.length)) return screenFacility(list[n - 1]);
      if (d === "4") return goLocation();
      if (d === "9") return endCall();
      return;
    }

    switch (d) {
      case "1": if (S.convId) { stopAudio(); S.phase = "ready"; screenReady(); return setControls(); } break;
      case "2": return repeat();
      case "3": S.phase = "language"; return screenLanguage();
      case "4": return goLocation();
      case "5": return simpler();
      case "9": return endCall();
      case "0": return triggerEmergency();
    }
  }

  function onSoftLeft() {
    sfx.soft();
    if (S.busy) return;
    switch (S.phase) {
      case "idle": return startCall();
      case "language": {
        const items = langMenuItems();
        const it = items[S.menuSel];
        if (it) switchLanguage(it.code);
        return;
      }
      case "answered": stopAudio(); S.phase = "ready"; screenReady(); return setControls();
      case "emergency": screenNotice("Call 112", "In a real phone, this dials 112 emergency services.", "emergency"); return;
      case "location": return useGps();
      case "help": screenNotice("Call 108", "Call 108 for ambulance in North East India.", "emergency"); return;
      default: wake();
    }
  }

  function onSoftRight() {
    sfx.soft();
    if (S.busy) return;
    if (S.view !== "main") {
      if (S.phase === "idle") return screenIdle();
      if (S.phase === "help") return screenHelp(S.help);
      if (S.lastTurn) return screenAnswer(S.lastTurn, { animate: false });
      S.view = "main"; softkeysForState(); return;
    }
    switch (S.phase) {
      case "idle": return screenMenu();
      case "language": S.phase = "ready"; return screenReady();
      case "ready": return el.typeInput.focus();
      case "answered": return screenMenu();
      case "emergency": return goLocation();
      case "location": case "help":
        S.phase = S.lastTurn ? "answered" : "ready";
        if (S.lastTurn) screenAnswer(S.lastTurn, { animate: false }); else screenReady();
        return setControls();
    }
  }

  function onNav(dir) {
    sfx.soft();
    wake();
    if (S.phase === "language") {
      const items = langMenuItems();
      S.menuSel = (S.menuSel + dir + items.length) % items.length;
      return screenLanguage();
    }
    scrollBy(dir);
  }

  function litKeypad() {
    el.keypad.classList.add("lit");
    clearTimeout(litKeypad.t);
    litKeypad.t = setTimeout(() => el.keypad.classList.remove("lit"), 150);
  }
  function pressFlash(btn) {
    if (!btn) return;
    btn.classList.add("pressed");
    setTimeout(() => btn.classList.remove("pressed"), 120);
  }

  // ---------- Turn Rendering & Call Log ----------
  function timeStamp() {
    const d = new Date();
    return [d.getHours(), d.getMinutes(), d.getSeconds()].map((n) => String(n).padStart(2, "0")).join(":");
  }

  function renderAnswer(turn) {
    S.lastTurn = turn;
    S.busy = false;
    const isEmerg = (turn.triage && turn.triage.level === "emergency");
    S.phase = isEmerg ? "emergency" : "answered";
    screenAnswer(turn);
    if (isEmerg) sfx.alert(); else sfx.blip();
    if (turn.voice) playVoice(turn.voice);
    el.convoEmpty.hidden = true;
    el.turns.prepend(turnElement(turn));
    setControls();
  }

  function turnElement(t) {
    const li = document.createElement("li");
    li.className = "turn";
    const lvl = (t.triage && t.triage.level) || "none";
    const flagText = {
      none: "Safety check: routine question.",
      urgent: "Safety check: consult a healthcare professional.",
      emergency: "Safety check: medical emergency. Call 112 immediately.",
    }[lvl] || "Safety check complete.";

    const matches = (t.triage && t.triage.matches) ? t.triage.matches.map((m) => m.label).join(", ") : "";
    const questionText = t.question ? t.question.text : (t.transcript || "Question");
    const steps = Object.entries(t.timings_ms || {}).filter(([k]) => STEP_NAMES[k]);
    const total = steps.reduce((a, [, v]) => a + v, 0) || 1;
    const BLOCKS = 48;

    li.innerHTML = `
      <p class="turn-time" style="margin:0">${timeStamp()} · ${esc(langCode(S.lang))}</p>
      <div>
        <p class="said" lang="${langAttr(S.lang)}">“${esc(questionText)}”</p>
        ${t.english && S.lang !== "en-IN" ? `<p class="said-meta">English pivot for reasoning: ${esc(t.english)}</p>` : ""}
      </div>
      <div class="flag ${lvl}"><b>${esc(flagText)}</b>${matches ? `<br>Matched: ${esc(matches)}` : ""}</div>
      ${t.medicine && t.medicine.request ? `<div class="flag med"><b>Medicine Safety:</b> Prescriptions and dosage requests are strictly filtered. General safety guidance provided.</div>` : ""}
      <div>
        <p style="margin:0 0 .35rem"><span class="source">${esc(t.answer.source || "Live AI")}</span>${t.voice && t.voice.provider ? `<span class="source" style="background:#EAF3EC;color:#2F7D45">${esc(t.voice.provider)}</span>` : ""}</p>
        <p class="answer" lang="${langAttr(t.answer.lang || S.lang)}">${esc(t.answer.text)}</p>
        ${t.answer.english && t.answer.lang !== "en-IN" ? `<p class="answer-en">English: ${esc(t.answer.english)}</p>` : ""}
      </div>
      ${steps.length ? `<div class="timing" aria-label="Latency breakdown">
        <div class="timing-bar">${steps.map(([k, v]) => `<span style="--c:${STEP_COLORS[k] || "#888"};width:${Math.max(2, Math.round((v / total) * BLOCKS)) * 6}px" title="${STEP_NAMES[k]}: ${v} ms"></span>`).join("")}</div>
        <div class="timing-legend">${steps.map(([k, v]) => `<span><i style="--c:${STEP_COLORS[k] || "#888"}"></i>${STEP_NAMES[k]} ${v} ms</span>`).join("")}</div>
      </div>` : ""}
      <div class="answer-actions">
        <button type="button" data-act="repeat">Hear again</button>
        <button type="button" data-act="simpler">Explain more simply</button>
        ${lvl === "emergency" ? '<button type="button" class="find-help" data-act="hospital">Find nearest hospital</button>' : ""}
      </div>`;

    li.querySelector('[data-act="repeat"]').onclick = () => { repeat(); };
    li.querySelector('[data-act="simpler"]').onclick = () => { simpler(); };
    const hBtn = li.querySelector('[data-act="hospital"]');
    if (hBtn) hBtn.onclick = () => goLocation();
    return li;
  }

  function facilityItem(f, first) {
    return `<li class="facility${first ? " nearest" : ""}">
      <p class="fac-name"><b>${esc(f.name)}</b> ${f.distance_km ? `<span class="km">${f.distance_km} km</span>` : ""}${first ? ' <span class="source">Suggested</span>' : ""}</p>
      <p class="fac-meta">${[f.address, f.district, f.state].filter(Boolean).map(esc).join(", ")}</p>
      <p class="fac-meta">${f.phone ? `Phone: <a href="tel:${esc(f.phone)}">${esc(f.phone)}</a> · ` : ""}${f.verified ? '<span class="verify ok">Verified 24x7</span>' : '<span class="verify no">Community listing</span>'}</p>
    </li>`;
  }

  function helpElement(r) {
    const li = document.createElement("li");
    li.className = "turn help";
    const place = r.place ? `${esc(r.place.name || "")} (${esc(r.place.method || "search")})` : "Searched location";
    const facs = (r.facilities || []).slice(0, 5);
    li.innerHTML = `
      <p class="turn-time" style="margin:0">${timeStamp()} · NEAREST HOSPITALS</p>
      <div class="notice"><b>Location: ${place}</b></div>
      <ul class="numbers">
        <li><span class="num">112</span>National Emergency</li>
        <li><span class="num">108</span>Ambulance Service</li>
        <li><span class="num">104</span>Health Information</li>
        <li><span class="num">14416</span>Tele-MANAS Mental Health</li>
      </ul>
      <div><p class="cards" style="margin:0 0 .4rem">Nearby Health Facilities (${facs.length} found)</p>
        <ol class="facilities">${facs.map((f, i) => facilityItem(f, i === 0)).join("")}</ol>
      </div>`;
    return li;
  }

  function renderHospitalsTab(r) {
    const facs = r.facilities || [];
    el.hospitalsList.innerHTML = `
      <div class="notice" style="margin-bottom:1rem"><b>Found ${facs.length} facilities near ${esc((r.place && r.place.name) || "you")}</b></div>
      <ol class="facilities">${facs.map((f, i) => facilityItem(f, i === 0)).join("")}</ol>
    `;
  }

  function renderLanguages() {
    el.langRows.innerHTML = S.languages.map((l) => {
      const bars = l.speech_output && l.speech_output.length ? 4 : (l.speech_input ? 2 : 0);
      const isVoice = bars === 4;
      return `
      <tr>
        <td><span class="native" lang="${langAttr(l.code)}">${esc(l.native_name)}</span><small>${esc(l.name)}, ${esc(l.states ? l.states.join(", ") : "")}</small></td>
        <td>${esc(l.keypad || "—")}</td>
        <td><span class="signal${bars ? "" : " none"}">${signalSvg(bars)}${isVoice ? "Full voice" : (bars ? "Voice in" : "Text")}</span></td>
        <td>${l.speech_input ? "Yes" : "Text"}</td>
        <td>${l.speech_output ? esc(l.speech_output.join(", ")) : "Text"}</td>
      </tr>`;
    }).join("");
  }

  function renderScenarioChips() {
    el.chips.innerHTML = "";
    el.scenarioLabel.textContent = S.phase === "location" ? "Demo locations" : "Sample questions";
    if (S.phase === "location") {
      LOCATION_CHIPS.forEach((place) => {
        const b = document.createElement("button");
        b.type = "button"; b.className = "chip"; b.textContent = place;
        b.onclick = () => submitFacilitiesSearch({ text: place, emergency: false });
        el.chips.appendChild(b);
      });
      return;
    }
    SAMPLE_QUESTIONS.forEach((sc) => {
      const q = sc.questions[S.lang] || sc.questions["en-IN"];
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip" + (/emergency/i.test(sc.title) ? " danger" : "");
      b.textContent = sc.title;
      b.title = q;
      b.onclick = () => askText(q);
      el.chips.appendChild(b);
    });
  }

  function switchTab(name) {
    document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
    ["convo", "hospitals", "langs"].forEach((t) => { $(`tab-${t}`).hidden = t !== name; });
  }

  // ---------- Wiring & Event Listeners ----------
  el.call.onclick = () => { pressFlash(el.call); startCall(); };
  el.end.onclick = () => { pressFlash(el.end); endCall(); };
  el.keypad.addEventListener("click", (e) => {
    const k = e.target.closest(".key");
    if (k && k.dataset.d) onDigit(k.dataset.d);
  });
  el.navUp.onclick = () => onNav(-1);
  el.navDown.onclick = () => onNav(1);
  el.softR.onclick = onSoftRight;

  // Left softkey: hold or click to speak
  let holdStarted = false, suppressClick = false;
  el.softL.addEventListener("pointerdown", (e) => {
    suppressClick = false;
    if (S.phase === "ready" && !S.busy && S.convId) {
      e.preventDefault();
      holdStarted = true;
      sfx.soft();
      startRecording();
    }
  });
  const releaseHold = () => {
    if (holdStarted) {
      holdStarted = false;
      suppressClick = true;
      stopRecording();
    }
  };
  el.softL.addEventListener("pointerup", releaseHold);
  el.softL.addEventListener("pointercancel", releaseHold);
  el.softL.addEventListener("pointerleave", releaseHold);
  el.softL.addEventListener("click", () => {
    if (suppressClick) { suppressClick = false; return; }
    if (S.phase !== "ready") onSoftLeft();
  });

  // Physical keyboard support
  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.target.tagName === "BUTTON" && (e.key === "Enter" || e.key === " ")) return;
    if (/^[0-9*#]$/.test(e.key)) {
      const btn = el.keypad.querySelector(`[data-d="${e.key}"]`);
      pressFlash(btn);
      onDigit(e.key);
      return;
    }
    if (e.key === "Enter") { e.preventDefault(); pressFlash(el.call); return startCall(); }
    if (e.key === "Escape") { e.preventDefault(); pressFlash(el.end); return endCall(); }
    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      e.preventDefault();
      const up = e.key === "ArrowUp";
      pressFlash(up ? el.navUp : el.navDown);
      return onNav(up ? -1 : 1);
    }
    if (e.key === "ArrowLeft") { e.preventDefault(); pressFlash(el.softL); return S.phase === "ready" ? undefined : onSoftLeft(); }
    if (e.key === "ArrowRight") { e.preventDefault(); pressFlash(el.softR); return onSoftRight(); }
    if (e.key === " ") {
      e.preventDefault();
      if (!e.repeat && S.phase === "ready") {
        pressFlash(el.softL);
        startRecording();
      }
    }
  });
  document.addEventListener("keyup", (e) => {
    if (e.key === " " && S.recording && e.target.tagName !== "INPUT") {
      e.preventDefault();
      stopRecording();
    }
  });
  document.addEventListener("pointerdown", () => wake(), { passive: true });

  el.typeForm.onsubmit = (e) => {
    e.preventDefault();
    const t = el.typeInput.value.trim();
    el.typeInput.value = "";
    if (!t) return;
    if (S.phase === "location") submitFacilitiesSearch({ text: t, emergency: false });
    else askText(t);
  };

  el.facSearchBtn.onclick = () => {
    const q = el.facSearchInput.value.trim();
    if (q) submitFacilitiesSearch({ text: q, emergency: false });
  };
  el.facGpsBtn.onclick = () => useGps();
  el.mute.onchange = () => { if (el.mute.checked) stopAudio(); };
  document.querySelectorAll(".tabs button").forEach((b) => (b.onclick = () => switchTab(b.dataset.tab)));

  function fitPhone() {
    const h = el.phone.offsetHeight;
    el.wrap.style.setProperty("--phone-h", `${h}px`);
    if (window.innerWidth < 640) {
      const s = Math.min(1, (window.innerWidth - 32) / 300, (window.innerHeight - 24) / h);
      el.wrap.style.setProperty("--scale", s.toFixed(3));
    } else {
      el.wrap.style.removeProperty("--scale");
    }
  }
  window.addEventListener("resize", fitPhone);

  // ---------- Boot ----------
  screenIdle();
  fitPhone();
  setInterval(() => { if (S.phase === "idle" && S.view === "main") screenIdle(); }, 30000);

  (async () => {
    try {
      const [health, langs] = await Promise.all([api("/api/health"), api("/api/languages")]);
      S.health = health;
      S.languages = langs.languages || [];
      const selectable = S.languages.filter((l) => l.selectable !== false);
      selectable.forEach((l, i) => { l.keypad = String(i + 1); });

      const p = health.providers || {};
      const sttName = (p.speech_to_text && p.speech_to_text.providers) ? p.speech_to_text.providers.join(", ") : "None";
      const ttsName = (p.text_to_speech && p.text_to_speech.providers) ? p.text_to_speech.providers.join(", ") : "None";
      el.mode.innerHTML = `<strong>Live AI</strong>: ${esc(p.llm && p.llm.model ? p.llm.model : "Connected")} · STT: ${esc(sttName)} · Voice: ${esc(ttsName)}`;
      renderLanguages();
    } catch (e) {
      el.mode.textContent = "Backend not reachable. Start it with: uvicorn app.main:app";
    }
    setStatusLang();
    setControls();
  })();
})();
