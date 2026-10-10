/* Aarogya Saathi phone simulator. Talks to the same backend a real phone line uses.
   The handset follows docs/DESIGN.md: monochrome LCD, per-state softkeys, DTMF tones. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const el = {
    mode: $("mode"), lcd: $("lcd"), body: $("lcdBody"), lang: $("lcdLang"), rec: $("lcdRec"),
    up: $("arrowUp"), down: $("arrowDown"), softLLabel: $("softLLabel"), softRLabel: $("softRLabel"),
    softL: $("softL"), softR: $("softR"), navUp: $("navUp"), navDown: $("navDown"),
    call: $("callBtn"), end: $("endBtn"), keypad: $("keypad"), phone: $("phone"), wrap: $("phoneWrap"),
    typeForm: $("typeForm"), typeInput: $("typeInput"), typeSend: $("typeSend"),
    scenarios: $("scenarios"), chips: $("scenarioChips"), mute: $("muteToggle"),
    turns: $("turns"), convoEmpty: $("convoEmpty"), slip: $("slip"), slipEmpty: $("slipEmpty"),
    langRows: $("langRows"), lookupForm: $("lookupForm"), lookupInput: $("lookupInput"), lookupMsg: $("lookupMsg"),
  };

  const S = {
    callId: null,
    phase: "idle", // idle | calling | language | ready | confirming | answered | emergency | consent | ended
    view: "main",  // main | menu | notice  (sub-screens reached with the right softkey)
    lang: null, prevPhase: null, languages: [], scenarios: [], lastTurn: null, health: null,
    askPrompt: null, menuSel: 0, startedAt: 0, busy: false,
  };

  const SCRIPT_ATTR = { "as-IN": "as", "bn-IN": "bn", "mni-IN": "mni", "hi-IN": "hi", "brx-IN": "brx", "ne-IN": "ne", "en-IN": "en" };
  const STEP_COLORS = { stt: "#46566A", translate_in: "#7A8B5C", triage: "#5E6670", retrieve: "#8A7A4A", llm: "#26331A", translate_out: "#A9B88A", tts: "#3E9B4F" };
  const STEP_NAMES = { stt: "Speech to text", translate_in: "Translate to English", triage: "Safety check", retrieve: "Find health card", llm: "AI answer", translate_out: "Translate back", tts: "Voice" };
  const SOURCE_NAMES = {
    llm: "Live AI, grounded on vetted cards", demo: "Demo answer (scripted)", card_fallback: "Vetted card text (AI not available)",
    emergency: "Emergency script, AI skipped", crisis: "Crisis script, AI skipped",
  };
  const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- API ----------
  async function api(path, opts = {}) {
    const res = await fetch(path, { headers: opts.body instanceof FormData ? {} : { "Content-Type": "application/json" }, ...opts });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
    return data;
  }
  const post = (path, body) => api(path, { method: "POST", body: body instanceof FormData ? body : JSON.stringify(body || {}) });

  // ---------- pixel icons (12×12, drawn as rects) ----------
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
    envelope: ["............", "............", "############", "##........##", "#.#......#.#", "#..#....#..#",
      "#...#..#...#", "#....##....#", "#..........#", "#..........#", "############", "............"],
    battery: ["............", "............", "............", "##########..", "#........#..", "#.##.##..###",
      "#.##.##..###", "#........#..", "##########..", "............", "............", "............"],
  };
  function pix(name, cls = "pix") {
    const rows = ICONS[name];
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

  /** Draw a screen. html is trusted markup built here; `type` is plain text that types in. */
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
      if (reducedMotion() || parts.length < 2) { p.textContent = type; }
      else {
        const step = Math.min(30, 1000 / parts.length);
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
      case "idle": return setSoftkeys("", sub ? "Back" : "Menu");
      case "calling": return setSoftkeys("", "");
      case "language": return setSoftkeys("Select", "Back");
      case "ready": return setSoftkeys(S.recording ? "Release" : "Speak", "Type");
      case "confirming": case "consent": return setSoftkeys("Yes", "No");
      case "answered": return setSoftkeys("Again", sub ? "Back" : "Menu");
      case "emergency": return setSoftkeys(S.lastTurn && S.lastTurn.triage.level === "crisis" ? "Call 14416" : "Call 112", sub ? "Back" : "Menu");
      default: return setSoftkeys("", "");
    }
  }

  function langCode(code) { return code ? code.split("-")[0].toUpperCase() : ""; }
  function setStatusLang() { el.lang.textContent = langCode(S.lang); }

  // backlight: dims after 10 s without a key press, any key wakes it
  let backlightTimer = null;
  function wake() {
    el.lcd.dataset.backlight = "on";
    clearTimeout(backlightTimer);
    backlightTimer = setTimeout(() => { el.lcd.dataset.backlight = "off"; }, 10000);
  }

  function flashAmber() {
    if (reducedMotion()) return;
    el.lcd.classList.remove("flash");
    void el.lcd.offsetWidth; // restart the animation
    el.lcd.classList.add("flash");
    setTimeout(() => el.lcd.classList.remove("flash"), 1100);
  }

  // ---------- screens ----------
  function clock() { const d = new Date(); return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; }
  function screenIdle() {
    S.view = "main";
    lcd({ html: `<div class="center">${pix("heart", "pix big")}<span>AAROGYA</span><span>SAATHI</span><span>health line</span><span>${clock()}</span></div>` });
    softkeysForState();
  }
  function screenCalling() {
    lcd({ html: `<div class="center" style="margin-top:22px">${pix("handset", "pix big")}<span class="dots">Calling</span></div>` });
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
    const p = S.askPrompt;
    lcd({ html: heading("Ask your question"), type: p ? p.text : "Hold Speak, or type below.", lang: p ? p.lang : "en-IN" });
    softkeysForState();
  }

  function langMenuItems() {
    const items = S.languages.filter((l) => l.keypad).sort((a, b) => a.keypad.localeCompare(b.keypad))
      .map((l) => ({ digit: l.keypad, label: l.native_name, code: l.code }));
    items.push({ digit: "8", label: "Not listed", code: "en-IN" });
    return items;
  }
  function screenLanguage() {
    const items = langMenuItems();
    S.menuSel = Math.max(0, Math.min(S.menuSel, items.length - 1));
    const rows = items.map((it, i) => `<li class="${i === S.menuSel ? "selected" : ""}"><b>${it.digit}</b><span lang="${langAttr(it.code)}">${esc(it.label)}</span></li>`).join("");
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
    const lvl = turn.triage.level;
    if (lvl === "emergency" || lvl === "crisis") {
      const head = lvl === "emergency"
        ? `<div class="inv">${pix("alert")}<span>! EMERGENCY 112</span></div>`
        : `<div class="inv"><span>Tele-MANAS 14416</span></div>`;
      lcd({ html: head, type: turn.answer.text, lang: turn.answer.lang, mode: lvl === "emergency" ? "emergency" : "", assertive: lvl === "emergency" });
      if (lvl === "emergency" && animate) flashAmber();
    } else {
      lcd({ html: "", type: turn.answer.text, lang: turn.answer.lang });
    }
    softkeysForState();
  }
  function screenMenu() {
    S.view = "menu";
    const m = S.lastTurn ? S.lastTurn.menu : null;
    lcd({ html: heading("Menu"), type: m ? m.text : "1 ask  2 repeat  5 simpler  3 language  9 end", lang: m ? m.lang : "en-IN",
      mode: S.phase === "emergency" && S.lastTurn.triage.level === "emergency" ? "emergency" : "" });
    if (m) say(m.text, m.lang);
    softkeysForState();
  }
  function screenNotice(title, text, mode = "") {
    S.view = "notice";
    lcd({ html: heading(title), type: text, mode });
    softkeysForState();
  }
  function screenEnded(slip) {
    const secs = Math.round((Date.now() - S.startedAt) / 1000);
    const dur = [Math.floor(secs / 3600), Math.floor(secs / 60) % 60, secs % 60].map((n) => String(n).padStart(2, "0")).join(":");
    const slipPart = slip
      ? `<div style="margin-top:2px">${pix("envelope")} Slip code</div><div class="center"><span class="codebox">${esc(slip.code)}</span><span>Show to ASHA</span></div>`
      : `<p style="margin:4px 0 0">No slip saved.</p><p style="margin:0">Press CALL to start again.</p>`;
    lcd({ html: `<div class="heading">Call ended<br>${dur}</div>${slipPart}` });
    softkeysForState();
  }

  // ---------- sound: DTMF tones, ring-back, blips ----------
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
    } catch (_) { /* tones are optional */ }
  }
  const sfx = {
    key: (d) => beep(DTMF[d], 0, 0.14),
    soft: () => beep([1400], 0, 0.04, 0.04),
    ring: () => { beep([440, 480], 0, 0.35); beep([440, 480], 0.5, 0.35); },
    blip: () => beep([880], 0, 0.06, 0.04),
    alert: () => { [0, 0.22, 0.44].forEach((t) => beep([1046], t, 0.14, 0.07)); },
    end: () => beep([480, 620], 0, 0.45),
  };

  // ---------- voice playback ----------
  const audioQueue = [];
  let playing = false, currentAudio = null, autoScroll = null;
  function enqueue(item) { audioQueue.push(item); if (!playing) playNext(); }
  function stopAudio() {
    audioQueue.length = 0; playing = false; stopAutoScroll();
    if (window.speechSynthesis) speechSynthesis.cancel();
    if (currentAudio) currentAudio.pause();
  }
  function startAutoScroll() {
    stopAutoScroll();
    autoScroll = setInterval(() => { if (el.body.scrollTop + el.body.clientHeight < el.body.scrollHeight - 2) scrollBy(1); }, 2500);
  }
  function stopAutoScroll() { clearInterval(autoScroll); autoScroll = null; }
  function playNext() {
    const item = audioQueue.shift();
    if (!item || el.mute.checked) { playing = false; audioQueue.length = 0; stopAutoScroll(); return; }
    playing = true;
    if (item.scroll) startAutoScroll();
    if (item.url) {
      currentAudio = new Audio(item.url);
      currentAudio.onended = currentAudio.onerror = playNext;
      currentAudio.play().catch(playNext);
    } else if (item.text && browserVoiceFor(item.lang)) {
      const u = new SpeechSynthesisUtterance(item.text);
      const v = browserVoiceFor(item.lang);
      u.lang = v.lang; u.voice = v; u.rate = 0.9;
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
  function say(text, lang, voice, scroll = false) { enqueue({ url: voice && voice.audio_url, text, lang, scroll }); }

  // ---------- controls outside the handset ----------
  function setControls() {
    const inCall = !!S.callId && !["ended", "idle", "calling"].includes(S.phase);
    const canAsk = inCall && ["ready", "answered", "emergency"].includes(S.phase) && !S.busy;
    el.typeInput.disabled = el.typeSend.disabled = !canAsk;
    el.scenarios.hidden = !canAsk;
    if (canAsk) renderScenarioChips();
    softkeysForState();
  }

  // ---------- call flow ----------
  async function startCall() {
    if (S.callId || S.phase === "calling") return;
    stopAudio();
    el.lcd.classList.remove("off");
    S.phase = "calling"; S.lang = null; S.lastTurn = null; S.askPrompt = null; S.prevPhase = null; S.menuSel = 0;
    setStatusLang();
    screenCalling(); sfx.ring();
    const wait = new Promise((r) => setTimeout(r, reducedMotion() ? 300 : 2000));
    try {
      const [r] = await Promise.all([post("/api/calls/start", { channel: "simulator" }), wait]);
      S.callId = r.call.id; S.phase = "language"; S.startedAt = Date.now();
      el.turns.innerHTML = ""; el.convoEmpty.hidden = false;
      screenLanguage();
      say(`${r.welcome} ${r.menu}`, "en-IN");
    } catch (e) {
      S.phase = "idle";
      screenText("No network", e.message);
      softkeysForState();
    }
    setControls();
  }

  async function chooseLanguage(digit) {
    try {
      const r = await post(`/api/calls/${S.callId}/language`, { digit });
      if (!r.supported) {
        screenNotice("No service", r.prompt.text);
        say(r.prompt.text, "en-IN");
        S.view = "main";
        return;
      }
      S.lang = r.call.language; S.phase = "ready"; S.prevPhase = null;
      setStatusLang();
      const p = r.prompts;
      S.askPrompt = p.ask;
      lcd({ html: line(p.confirmed.text, p.confirmed.lang) + `<div class="heading"></div>`, type: p.ask.text, lang: p.ask.lang });
      say(p.confirmed.text, p.confirmed.lang, r.voices[0]);
      say(p.ask.text, p.ask.lang, r.voices[1]);
    } catch (e) { screenText("Try again", e.message); }
    setControls();
  }

  async function askText(text, viaVoice = false) {
    if (!text.trim() || !S.callId) return;
    stopAudio();
    S.busy = true; setControls();
    screenThinking();
    try {
      // Speech goes through read-back confirmation; typed text does not need it.
      const r = await post(`/api/calls/${S.callId}/message`, { text, skip_readback: !viaVoice });
      S.busy = false;
      if (r.turn) return renderAnswer(r.turn);
      showReadback(r.transcript, r.prompt);
      say(r.prompt.text, r.prompt.lang);
    } catch (e) { S.busy = false; screenText("Try again", e.message); }
    setControls();
  }

  function showReadback(transcript, prompt) {
    S.phase = "confirming"; S.view = "main";
    lcd({ html: heading("I heard:") + line(`“${transcript}”`, S.lang) + line("1 = Yes   2 = No") });
    el.body.setAttribute("aria-label", prompt.text);
    softkeysForState();
  }

  async function sendAudio(blob) {
    S.busy = true; setControls();
    screenThinking("Hearing");
    const fd = new FormData(); fd.append("audio", blob, "question.webm");
    try {
      const r = await post(`/api/calls/${S.callId}/transcribe`, fd);
      S.busy = false;
      if (!r.ok) {
        S.phase = "ready";
        screenText("Could not hear", `${r.prompt.text}${r.hint ? "\n" + r.hint : ""}`, r.prompt.lang);
        say(r.prompt.text, r.prompt.lang);
        if (r.reason === "stt_unavailable") el.typeInput.focus();
        return setControls();
      }
      showReadback(r.transcript, r.prompt);
      say(r.prompt.text, r.prompt.lang, r.voice);
    } catch (e) { S.busy = false; S.phase = "ready"; screenText("Try again", e.message); }
    setControls();
  }

  async function confirm(correct) {
    stopAudio();
    try {
      if (correct) screenThinking();
      const r = await post(`/api/calls/${S.callId}/confirm`, { correct });
      if (r.turn) return renderAnswer(r.turn);
      S.phase = "ready";
      S.askPrompt = r.prompt;
      screenReady();
      say(r.prompt.text, r.prompt.lang, r.voice);
    } catch (e) { screenText("Try again", e.message); }
    setControls();
  }

  async function simpler() {
    if (S.phase === "emergency") return;
    stopAudio();
    screenThinking("Simpler words");
    try {
      const r = await post(`/api/calls/${S.callId}/simpler`);
      renderAnswer(r.turn);
    } catch (e) { screenText("Ask first", e.message); setControls(); }
  }

  function repeat() {
    if (!S.lastTurn) return;
    stopAudio();
    const t = S.lastTurn;
    screenAnswer(t, { animate: false });
    say(t.answer.text, t.answer.lang, t.voice, true);
  }

  function askConsent() {
    stopAudio();
    S.phase = "consent"; S.view = "main";
    const text = "Would you like a short summary slip of this call to show your ASHA worker or doctor? Press 1 for yes, 2 for no.";
    lcd({ html: heading("Care slip?", "envelope"), type: text });
    say(text, "en-IN");
    setControls();
  }

  function goLanguageMenu() {
    stopAudio();
    S.prevPhase = S.phase; S.phase = "language"; S.view = "main";
    const idx = langMenuItems().findIndex((it) => it.code === S.lang);
    S.menuSel = idx < 0 ? 0 : idx;
    screenLanguage();
    setControls();
  }

  async function endCall(consent = false) {
    if (!S.callId) {
      if (S.phase !== "idle") { S.phase = "idle"; screenIdle(); setControls(); }
      return;
    }
    stopAudio();
    sfx.end();
    let slip = null;
    try {
      const r = await post(`/api/calls/${S.callId}/end`, { consent_slip: consent });
      slip = r.slip;
      say(r.goodbye.text, r.goodbye.lang);
      if (slip) { renderSlip(slip); switchTab("slip"); }
    } catch (_) { /* the call had already ended on the server */ }
    S.callId = null; S.phase = "ended"; S.view = "main"; S.recording = false;
    el.rec.hidden = true;
    screenEnded(slip);
    setControls();
  }

  /** END key: a real phone hangs up; the screen shrinks to a line and goes off. */
  async function hangUp() {
    if (!S.callId) {
      if (S.phase === "ended") {
        if (!reducedMotion()) el.lcd.classList.add("off");
        setTimeout(() => { el.lcd.classList.remove("off"); S.phase = "idle"; S.lang = null; setStatusLang(); screenIdle(); setControls(); }, reducedMotion() ? 0 : 400);
      }
      return;
    }
    await endCall(false);
  }

  // ---------- input dispatch ----------
  function onDigit(d) {
    sfx.key(d);
    litKeypad();
    if (!S.callId || S.busy) return;
    switch (S.phase) {
      case "language": {
        const items = langMenuItems();
        const i = items.findIndex((it) => it.digit === d);
        if (i >= 0) { S.menuSel = i; screenLanguage(); chooseLanguage(d); }
        return;
      }
      case "confirming": if (d === "1") return confirm(true); if (d === "2") return confirm(false); return;
      case "consent": if (d === "1") return endCall(true); if (d === "2") return endCall(false); return;
      case "ready": if (d === "0") return S.lastTurn ? screenMenu() : screenReady(); return;
      case "answered": case "emergency":
        if (d === "1") { stopAudio(); S.phase = "ready"; screenReady(); return setControls(); }
        if (d === "2") return repeat();
        if (d === "5") return simpler();
        if (d === "3") return goLanguageMenu();
        if (d === "9") return askConsent();
        if (d === "0") return screenMenu();
    }
  }

  function onSoftLeft() {
    sfx.soft();
    if (S.busy) return;
    switch (S.phase) {
      case "language": { const it = langMenuItems()[S.menuSel]; if (it) chooseLanguage(it.digit); return; }
      case "confirming": return confirm(true);
      case "consent": return endCall(true);
      case "answered": stopAudio(); S.phase = "ready"; screenReady(); return setControls();
      case "emergency": {
        const n = S.lastTurn && S.lastTurn.triage.level === "crisis" ? "14416" : "112";
        return screenNotice(`Call ${n}`, `In a real phone, this dials ${n}.`, n === "112" ? "emergency" : "");
      }
      default: wake();
    }
  }

  function onSoftRight() {
    sfx.soft();
    if (S.busy) return;
    if (S.view !== "main") {
      if (S.phase === "idle") return screenIdle();
      if (S.lastTurn && ["answered", "emergency"].includes(S.phase)) return screenAnswer(S.lastTurn, { animate: false });
      S.view = "main"; softkeysForState(); return;
    }
    switch (S.phase) {
      case "idle": return screenNotice("Menu", "Press the green CALL key to reach the health line. It works on any phone.");
      case "language":
        if (S.prevPhase && S.lastTurn) { S.phase = S.prevPhase; S.prevPhase = null; screenAnswer(S.lastTurn, { animate: false }); return setControls(); }
        return endCall(false);
      case "ready": return el.typeInput.focus();
      case "confirming": return confirm(false);
      case "consent": return endCall(false);
      case "answered": case "emergency": return screenMenu();
    }
  }

  function onNav(dir) {
    sfx.soft();
    wake();
    if (S.phase === "language") {
      const n = langMenuItems().length;
      S.menuSel = (S.menuSel + dir + n) % n;
      return screenLanguage();
    }
    stopAutoScroll();
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

  // ---------- rendering the answer + panel ----------
  function renderAnswer(turn) {
    S.lastTurn = turn;
    S.busy = false;
    const emergency = ["emergency", "crisis"].includes(turn.triage.level);
    S.phase = emergency ? "emergency" : "answered";
    screenAnswer(turn);
    if (turn.triage.level === "emergency") sfx.alert(); else sfx.blip();
    say(turn.answer.text, turn.answer.lang, turn.voice, true);
    el.convoEmpty.hidden = true;
    el.turns.prepend(turnElement(turn));
    setControls();
  }

  function timeStamp() { const d = new Date(); return [d.getHours(), d.getMinutes(), d.getSeconds()].map((n) => String(n).padStart(2, "0")).join(":"); }

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
    const BLOCKS = 48;
    const speechNote = t.voice && t.voice.voice_note && !el.mute.checked ? `<p class="voice-note">${esc(t.voice.voice_note)}</p>` : "";
    li.innerHTML = `
      <p class="turn-time" style="margin:0">${timeStamp()} · ${esc(langCode(S.lang))}</p>
      <div>
        <p class="said" lang="${langAttr(S.lang)}">“${esc(t.transcript)}”</p>
        <p class="said-meta">${t.english && S.lang !== "en-IN" ? `English used for reasoning: ${esc(t.english)} <small>(${esc(t.english_source)})</small>` : (S.lang === "en-IN" ? "" : "No translator configured and not a demo question, so the safety check ran on the original words only.")}</p>
      </div>
      <div class="flag ${lvl}"><b>${esc(flagText)}</b>${matches ? `<br>Matched: ${esc(matches)}` : ""}</div>
      <div>
        <p style="margin:0 0 .35rem"><span class="source ${esc(baseSource)}">${esc(sourceLabel)}</span>${t.level === "simple" ? '<span class="source">Simpler words</span>' : ""}</p>
        <p class="answer" lang="${langAttr(t.answer.lang)}">${esc(t.answer.text)}</p>
        ${t.answer.english && t.answer.lang !== "en-IN" ? `<p class="answer-en">In English: ${esc(t.answer.english)}</p>` : ""}
        ${englishFallback ? '<p class="voice-note">Shown in English because translation for this language is not configured.</p>' : ""}
      </div>
      ${t.cards.length ? `<p class="cards">Based on the vetted card ${t.cards.map((c) => `“${esc(c.title)}”, source: ${esc(c.source)}`).join("; and ")}.</p>` : ""}
      ${speechNote}
      ${steps.length ? `<div class="timing" aria-label="Time taken per step">
        <div class="timing-bar">${steps.map(([k, v]) => `<span style="--c:${STEP_COLORS[k]};width:${Math.max(1, Math.round((v / total) * BLOCKS)) * 6}px" title="${STEP_NAMES[k]}: ${v} ms"></span>`).join("")}</div>
        <div class="timing-legend">${steps.map(([k, v]) => `<span><i style="--c:${STEP_COLORS[k]}"></i>${STEP_NAMES[k]} ${v} ms</span>`).join("")}</div>
      </div>` : ""}
      <div class="answer-actions">
        <button type="button" data-act="repeat">Hear again</button>
        ${lvl === "emergency" || lvl === "crisis" ? "" : '<button type="button" data-act="simpler">Explain more simply</button>'}
      </div>`;
    li.querySelector('[data-act="repeat"]').onclick = () => { stopAudio(); screenAnswer(t, { animate: false }); say(t.answer.text, t.answer.lang, t.voice, true); };
    const simp = li.querySelector('[data-act="simpler"]');
    if (simp) simp.onclick = () => S.callId && ["answered", "ready"].includes(S.phase) && simpler();
    return li;
  }

  function renderSlip(slip) {
    el.slipEmpty.hidden = true;
    el.slip.hidden = false;
    const concerns = slip.concerns.map((c) => `<li><span lang="${langAttr(S.lang)}">${esc(c.said)}</span>${c.english && c.english !== c.said ? `<small>${esc(c.english)}</small>` : ""}${c.duration ? `<small>Duration: ${esc(c.duration)}</small>` : ""}</li>`).join("");
    el.slip.innerHTML = `
      <p class="rcpt-head">AAROGYA SAATHI<br>CARE SLIP</p>
      <hr>
      <div class="code">${esc(slip.code)}</div>
      <p style="text-align:center;margin:0"><small>Show this code to your ASHA worker or doctor</small></p>
      <hr>
      <h3 class="urgency-${esc(slip.urgency)}">${esc(slip.recommended_action)}</h3>
      <hr>
      <dl>
        <dt>Created</dt><dd>${esc(slip.created_ist)}</dd>
        <dt>Language</dt><dd>${esc(slip.language)}</dd>
        <dt>Red flags</dt><dd>${slip.red_flags.length ? esc(slip.red_flags.join(", ")) : "None reported"}</dd>
        <dt>Topics</dt><dd>${slip.topics_covered.length ? esc(slip.topics_covered.join(", ")) : "—"}</dd>
      </dl>
      <hr>
      <p style="margin:0 0 .3rem">Caller said:</p>
      <ul>${concerns}</ul>
      <hr>
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
    const coverage = {
      full_voice: [4, "Full voice"], partial: [1, "Partial"],
      voice_ready_needs_keys: [2, "Ready once API keys are added"], unsupported: [0, "No service"],
    };
    el.langRows.innerHTML = S.languages.map((l) => {
      const [bars, label] = coverage[l.level] || [0, l.level];
      return `
      <tr>
        <td><span class="native" lang="${langAttr(l.code)}">${esc(l.native_name)}</span><small>${esc(l.name)}, ${esc(l.states.join(", "))}</small>${l.notes ? `<small>${esc(l.notes)}</small>` : ""}</td>
        <td>${l.keypad || "8"}</td>
        <td><span class="signal${bars ? "" : " none"}">${signalSvg(bars)}${esc(label)}</span></td>
        <td>${l.provider_support.stt.length ? esc(l.provider_support.stt.join(", ")) : "—"}</td>
        <td>${l.provider_support.tts.length ? esc(l.provider_support.tts.join(", ")) : "—"}</td>
      </tr>`;
    }).join("");
  }

  function renderScenarioChips() {
    el.chips.innerHTML = "";
    S.scenarios.forEach((sc) => {
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
    ["convo", "slip", "langs"].forEach((t) => { $(`tab-${t}`).hidden = t !== name; });
  }

  // ---------- microphone (hold Speak) ----------
  let recorder = null, chunks = [], recognition = null;
  const canSpeak = () => S.callId && !S.busy && ["ready", "answered", "emergency"].includes(S.phase);
  function setRecording(on) {
    S.recording = on;
    el.rec.hidden = !on;
    softkeysForState();
  }
  async function startRecording() {
    if (!canSpeak() || S.recording) return;
    stopAudio();
    S.phase = "ready";
    const sttLive = S.health && !/demo/.test(S.health.providers.stt);
    if (!sttLive) return startBrowserRecognition();
    setRecording(true);
    screenListening();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!S.recording) { stream.getTracks().forEach((t) => t.stop()); return screenReady(); } // released before permission
      recorder = new MediaRecorder(stream);
      chunks = [];
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = () => { stream.getTracks().forEach((t) => t.stop()); sendAudio(new Blob(chunks, { type: recorder.mimeType || "audio/webm" })); };
      recorder.start();
    } catch (_) {
      setRecording(false);
      screenText("Mic blocked", "Allow microphone access, or type the question below.");
    }
  }
  function stopRecording() {
    if (!S.recording) return;
    setRecording(false);
    if (recorder && recorder.state === "recording") recorder.stop();
    else if (recognition) recognition.stop();
    else screenReady();
  }
  function startBrowserRecognition() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const meta = S.languages.find((l) => l.code === S.lang);
    if (!SR || !meta || !meta.browser_voice) {
      screenText("Type instead", "Speech recognition for this language needs the Sarvam API key. Please type the question below for now.");
      el.typeInput.focus();
      return;
    }
    recognition = new SR();
    recognition.lang = meta.browser_voice;
    recognition.interimResults = false;
    recognition.onresult = (e) => { const t = e.results[0][0].transcript; recognition = null; askText(t, true); };
    recognition.onerror = () => { recognition = null; setRecording(false); screenText("Could not hear", "Please try again, or type the question."); };
    recognition.onend = () => { if (recognition) { recognition = null; setRecording(false); if (S.phase === "ready" && !S.busy) screenReady(); } };
    recognition.start();
    setRecording(true);
    screenListening();
  }

  // ---------- wiring ----------
  el.call.onclick = () => { pressFlash(el.call); startCall(); };
  el.end.onclick = () => { pressFlash(el.end); hangUp(); };
  el.keypad.addEventListener("click", (e) => { const k = e.target.closest(".key"); if (k) onDigit(k.dataset.d); });
  el.navUp.onclick = () => onNav(-1);
  el.navDown.onclick = () => onNav(1);
  el.softR.onclick = onSoftRight;

  // Left softkey doubles as hold-to-speak in the "ready" state.
  let holdStarted = false, suppressClick = false; // the click that follows a hold must not also trigger the softkey
  el.softL.addEventListener("pointerdown", (e) => {
    suppressClick = false;
    if (S.phase === "ready" && canSpeak()) { e.preventDefault(); holdStarted = true; sfx.soft(); startRecording(); }
  });
  const releaseHold = () => { if (holdStarted) { holdStarted = false; suppressClick = true; stopRecording(); } };
  el.softL.addEventListener("pointerup", releaseHold);
  el.softL.addEventListener("pointercancel", releaseHold);
  el.softL.addEventListener("pointerleave", releaseHold);
  el.softL.addEventListener("click", () => {
    if (suppressClick) { suppressClick = false; return; }
    if (S.phase !== "ready") onSoftLeft();
  });
  el.softL.addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === " ") && S.phase === "ready") { e.preventDefault(); e.stopPropagation(); if (!e.repeat) startRecording(); }
  });
  el.softL.addEventListener("keyup", (e) => { if ((e.key === "Enter" || e.key === " ") && S.recording) { e.preventDefault(); e.stopPropagation(); stopRecording(); } });

  // Physical keyboard: 0–9 * #, Enter = Call, Escape = End, hold Space = Speak, arrows = scroll.
  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.target.tagName === "BUTTON" && (e.key === "Enter" || e.key === " ")) return; // let focused buttons act
    if (/^[0-9*#]$/.test(e.key)) { pressFlash(el.keypad.querySelector(`[data-d="${e.key}"]`)); onDigit(e.key); return; }
    if (e.key === "Enter") { e.preventDefault(); pressFlash(el.call); return startCall(); }
    if (e.key === "Escape") { e.preventDefault(); pressFlash(el.end); return hangUp(); }
    if (e.key === "ArrowUp" || e.key === "ArrowDown") { e.preventDefault(); const up = e.key === "ArrowUp"; pressFlash(up ? el.navUp : el.navDown); return onNav(up ? -1 : 1); }
    if (e.key === "ArrowLeft") { e.preventDefault(); pressFlash(el.softL); return S.phase === "ready" ? undefined : onSoftLeft(); }
    if (e.key === "ArrowRight") { e.preventDefault(); pressFlash(el.softR); return onSoftRight(); }
    if (e.key === " ") { e.preventDefault(); if (!e.repeat) { pressFlash(el.softL); startRecording(); } }
  });
  document.addEventListener("keyup", (e) => { if (e.key === " " && S.recording && e.target.tagName !== "INPUT") { e.preventDefault(); stopRecording(); } });
  document.addEventListener("pointerdown", () => wake(), { passive: true });

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

  // Fit the whole handset on small screens (transform does not affect layout, so the wrapper reserves the space).
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

  // ---------- boot ----------
  screenIdle();
  fitPhone();
  setInterval(() => { if (S.phase === "idle" && S.view === "main") screenIdle(); }, 30000);
  (async () => {
    try {
      const [health, langs, scen] = await Promise.all([api("/api/health"), api("/api/languages"), api("/api/scenarios")]);
      S.health = health; S.languages = langs.languages; S.scenarios = scen.scenarios;
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
