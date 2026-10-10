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
    phase: "select_language", // select_language | ready | listening | processing | playing_response | emergency | location | help
    view: "menu",
    lang: "hi-IN",
    langSelected: false,
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
    switch (S.phase) {
      case "idle":
      case "select_language":
      case "menu":
        return setSoftkeys(S.langSelected ? "Speak" : "Select", "Menu");
      case "ready":
        return setSoftkeys("Speak", "Menu");
      case "listening":
        return setSoftkeys("Stop", "Cancel");
      case "processing":
        return setSoftkeys("", "");
      case "playing_response":
      case "answered":
        return setSoftkeys("Speak", "Menu");
      case "emergency":
        return setSoftkeys("Call 112", "Hospital");
      case "location":
        return setSoftkeys("GPS", "Menu");
      case "help":
        return setSoftkeys("Call 108", "Menu");
      default:
        return setSoftkeys("", "");
    }
  }

  function langCode(code) { return code ? code.split("-")[0].toUpperCase() : ""; }
  function setStatusLang() { el.lang.textContent = S.langSelected ? langCode(S.lang) : "--"; }

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

  // ---------- Screens & Localization ----------
  const I18N = {
    "hi-IN": {
      name: "Hindi",
      native: "हिंदी",
      menuTitle: "भाषा चुनें",
      pressDashToSpeak: "बोलने के लिए – (डैश) दबाएँ",
      pressStarMenu: "मेनू सुनने के लिए * दबाएँ",
      pressEndStop: "रोकने के लिए END दबाएँ",
      readyTitle: "तैयार",
      langLabel: "भाषा:",
      readyHelp: "– दबाकर बोलना शुरू करें<br>– दोबारा दबाकर भेजें<br>4: नज़दीकी अस्पताल<br>*: मेनू | END: रोकें",
      listeningTitle: "सुन रहे हैं",
      listeningMsg: "अपना सवाल बोलिए…",
      listeningDashSend: "भेजने के लिए – दबाएँ",
      processingTitle: "प्रक्रिया जारी",
      processingWait: "कृपया प्रतीक्षा करें",
      responseTitle: "उत्तर",
      nextPrompt: "अगला सवाल बोलने के लिए – दबाएँ",
      micDeniedTitle: "माइक बंद है",
      micDeniedMsg: "माइक्रोफ़ोन की अनुमति नहीं मिली।\nनीचे दिए गए बॉक्स में सवाल टाइप करें।",
      menuSpoken: "हिंदी के लिए 1 दबाएँ। अंग्रेजी के लिए 2 दबाएँ। असमिया के लिए 3 दबाएँ। नज़दीकी अस्पताल के लिए 4 दबाएँ। बोलने के लिए डैश बटन दबाएँ। मेनू दोबारा सुनने के लिए स्टार दबाएँ। रोकने के लिए एंड बटन दबाएँ।",
    },
    "as-IN": {
      name: "Assamese",
      native: "অসমীয়া",
      menuTitle: "ভাষা বাছক",
      pressDashToSpeak: "ক'বলৈ – (ডেশ্ব) টিপক",
      pressStarMenu: "মেনু শুনিবলৈ * টিপক",
      pressEndStop: "বন্ধ কৰিবলৈ END টিপক",
      readyTitle: "প্ৰস্তুত",
      langLabel: "ভাষা:",
      readyHelp: "– টিপি কথা কওক<br>– আকৌ টিপি প্ৰেৰণ কৰক<br>4: ওচৰৰ চিকিৎসালয়<br>*: মেনু | END: বন্ধ",
      listeningTitle: "শুনি থকা হৈছে",
      listeningMsg: "আপোনাৰ প্ৰশ্নটো কওক…",
      listeningDashSend: "প্ৰেৰণ কৰিবলৈ – টিপক",
      processingTitle: "প্ৰক্ৰিয়া চলিছে",
      processingWait: "অনুগ্ৰহ কৰি অপেক্ষা কৰক",
      responseTitle: "উত্তৰ",
      nextPrompt: "পৰৱৰ্তী প্ৰশ্নৰ বাবে – টিপক",
      micDeniedTitle: "মাইক সংযোগ নাই",
      micDeniedMsg: "মাইক্ৰ'ফোন ব্যৱহাৰৰ অনুমতি নাই।\nতলৰ বাকচত প্ৰশ্নটো লিখক।",
      menuSpoken: "হিন্দীৰ বাবে 1 টিপক। ইংৰাজীৰ বাবে 2 টিপক। অসমীয়াৰ বাবে 3 টিপক। ওচৰৰ হাস্পতালৰ বাবে 4 টিপক। কথা ক'বলৈ ডেশ্ব টিপক। মেনু আকৌ শুনিবলৈ ষ্টাৰ টিপক। বন্ধ কৰিবলৈ এণ্ড টিপক।",
    },
    "en-IN": {
      name: "English",
      native: "English",
      menuTitle: "SELECT LANGUAGE",
      pressDashToSpeak: "Press – (dash) to speak",
      pressStarMenu: "Press * to replay menu",
      pressEndStop: "Press END to stop",
      readyTitle: "READY",
      langLabel: "Language:",
      readyHelp: "Press – (dash) to speak<br>Press – again to send<br>4: Nearby Hospitals<br>*: Main Menu | END: Stop",
      listeningTitle: "LISTENING",
      listeningMsg: "Speak your question…",
      listeningDashSend: "Press – (dash) to send",
      processingTitle: "PROCESSING",
      processingWait: "Please wait",
      responseTitle: "RESPONSE",
      nextPrompt: "Press – (dash) to speak next",
      micDeniedTitle: "Mic Blocked",
      micDeniedMsg: "Microphone access was denied.\nYou can type your question in the input box below.",
      menuSpoken: "Press 1 for Hindi. Press 2 for English. Press 3 for Assamese. Press 4 for nearby hospitals. Press dash to speak. Press star to replay the main menu. Press END to stop and return to the main menu.",
    },
  };

  const menuVoiceCache = {};

  async function speakMainMenu() {
    stopAudio();
    if (el.mute.checked) return;
    const l = S.langSelected ? S.lang : "hi-IN";
    const i18n = I18N[l] || I18N["en-IN"];
    const textToSpeak = i18n.menuSpoken;
    try {
      if (!menuVoiceCache[l]) {
        menuVoiceCache[l] = await post("/api/speak", { text: textToSpeak, lang: l });
      }
      if (menuVoiceCache[l] && menuVoiceCache[l].audio_url) {
        playVoice(menuVoiceCache[l]);
      }
    } catch (_) {}
  }

  function screenMainMenu({ speak = false } = {}) {
    stopAudio();
    S.view = "menu";
    S.phase = "select_language";
    const l = S.langSelected ? S.lang : "hi-IN";
    const i18n = I18N[l] || I18N["hi-IN"];
    const curName = S.langSelected ? (i18n.name || "Hindi") : "None";
    const html = `
      ${heading(i18n.menuTitle || "SELECT LANGUAGE")}
      <ul class="menu" style="margin:2px 0 4px">
        <li><b>1</b> Hindi (हिंदी)</li>
        <li><b>2</b> English</li>
        <li><b>3</b> Assamese (অসমীয়া)</li>
        <li><b>4</b> Hospitals</li>
      </ul>
      <div style="font-size:0.75rem; line-height:1.2; opacity:0.95">
        ${i18n.pressDashToSpeak} (${esc(curName)})<br>
        ${i18n.pressStarMenu}<br>
        ${i18n.pressEndStop}
      </div>
    `;
    lcd({ html, mode: "select-language", lang: l });
    softkeysForState();
    setControls();
    if (speak) {
      speakMainMenu();
    }
  }

  function clock() { const d = new Date(); return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; }
  function screenIdle() {
    screenMainMenu({ speak: false });
  }
  function screenText(title, text, lang = "en-IN", icon = "") {
    lcd({ html: title ? heading(title, icon) : "", type: text, lang });
  }
  function screenThinking(text) {
    screenProcessing(text);
  }
  function screenProcessing(text = "Processing") {
    S.phase = "processing";
    const l = S.langSelected ? S.lang : "en-IN";
    const i18n = I18N[l] || I18N["en-IN"];
    const html = `
      ${heading(i18n.processingTitle || "PROCESSING")}
      <div class="center" style="margin-top:8px">
        <span class="hourglass">${pix("hourglass", "pix big")}</span>
        <span style="font-weight:bold; margin-top:4px">${esc(text)}…</span>
        <span style="font-size:0.75rem; margin-top:4px; opacity:0.85">${i18n.processingWait || "Please wait"}</span>
      </div>
    `;
    lcd({ html, mode: "processing", lang: l });
    softkeysForState();
    setControls();
  }
  function screenListening() {
    S.view = "main";
    S.phase = "listening";
    const l = S.langSelected ? S.lang : "en-IN";
    const i18n = I18N[l] || I18N["en-IN"];
    const html = `
      ${heading(i18n.listeningTitle || "LISTENING")}
      <div class="center" style="margin-top:4px">
        <div class="eq">${"<i></i>".repeat(8)}</div>
        ${pix("mic")}
        <span style="font-weight:bold; margin-top:2px">${i18n.listeningMsg || "Listening…"}</span>
        <span style="font-size:0.75rem; margin-top:2px; opacity:0.9">${i18n.listeningDashSend || "Press – (dash) to send"}</span>
      </div>
    `;
    lcd({ html, mode: "listening", lang: l });
    softkeysForState();
    setControls();
  }
  function screenReady() {
    S.view = "main";
    S.phase = "ready";
    const l = S.langSelected ? S.lang : "hi-IN";
    const i18n = I18N[l] || I18N["hi-IN"];
    const html = `
      ${heading(i18n.readyTitle || "READY")}
      <p style="margin:4px 0 2px"><b>${i18n.langLabel}</b> ${esc(i18n.name)} (${esc(i18n.native)})</p>
      <div style="margin-top:4px; font-size:0.75rem; line-height:1.2; opacity:0.95">
        ${i18n.readyHelp}
      </div>
    `;
    lcd({ html, mode: "ready", lang: l });
    softkeysForState();
    setControls();
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
    screenMainMenu({ speak: false });
  }

  function screenAnswer(turn, { animate = true } = {}) {
    S.view = "main";
    S.phase = "playing_response";
    const lvl = (turn.triage && turn.triage.level) || "none";
    if (lvl === "emergency") {
      const head = `<div class="inv">${pix("alert")}<span>! EMERGENCY 112</span></div>`;
      lcd({ html: head, type: turn.answer.text, lang: turn.answer.lang, mode: "emergency", assertive: true });
      if (animate) flashAmber();
    } else {
      const l = (turn.answer && turn.answer.lang) || S.lang || "en-IN";
      const i18n = I18N[l] || I18N["en-IN"];
      const head = `<div class="heading">${esc(i18n.responseTitle || "RESPONSE")}</div><div style="font-size:0.75rem;opacity:0.85;margin-bottom:2px">${esc(i18n.nextPrompt || "Press – (dash) to speak next")}</div>`;
      lcd({ html: head, type: turn.answer.text, lang: turn.answer.lang, mode: "response" });
    }
    softkeysForState();
    setControls();
  }

  function screenMenu() {
    screenMainMenu({ speak: false });
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
    const canType = !S.busy && ["ready", "playing_response", "answered", "location", "select_language"].includes(S.phase);
    el.typeInput.disabled = el.typeSend.disabled = !canType;
    el.typeInput.placeholder = S.phase === "location" ? "Village, town, district, PIN code" : "Type your question here…";
    el.typeLabel.textContent = S.phase === "location" ? "Type your location" : "Type instead";
    el.scenarios.hidden = !canType;
    if (canType) renderScenarioChips();
    softkeysForState();
  }

  // ---------- Language & Conversation Lifecycle ----------
  function selectLanguage(code) {
    stopAudio();
    S.lang = code;
    S.langSelected = true;
    setStatusLang();
    if (S.convId) {
      try { api(`/api/conversations/${S.convId}`, { method: "DELETE" }); } catch (_) {}
      S.convId = null;
    }
    screenReady();
  }

  async function startSpeaking() {
    if (S.recording || S.busy) return;
    stopAudio();

    if (!S.convId) {
      screenProcessing("Connecting");
      try {
        const r = await post("/api/conversations", { language: S.lang });
        S.convId = r.id;
        S.startedAt = Date.now();
      } catch (e) {
        screenNotice("Connection Error", e.message || "Failed to start session.");
        return;
      }
    }

    await startRecording();
  }

  async function askText(text) {
    if (!text.trim() || S.busy) return;
    stopAudio();
    if (!S.convId) {
      try {
        const r = await post("/api/conversations", { language: S.lang });
        S.convId = r.id;
        S.startedAt = Date.now();
      } catch (e) {
        screenNotice("Error", e.message || "Failed to start conversation.");
        return;
      }
    }
    S.busy = true; setControls();
    screenProcessing("Thinking");
    try {
      const turn = await post(`/api/conversations/${S.convId}/ask`, { text, simple: false });
      renderAnswer(turn);
    } catch (e) {
      S.busy = false; screenNotice("Error", e.message); setControls();
    }
  }

  async function simpler() {
    if (!S.convId || !S.lastTurn || S.busy) return;
    stopAudio();
    S.busy = true; setControls();
    screenProcessing("Simpler words");
    try {
      const turn = await post(`/api/conversations/${S.convId}/simpler`, {});
      renderAnswer(turn);
    } catch (e) {
      S.busy = false; screenNotice("Error", e.message); setControls();
    }
  }

  function repeat() {
    if (!S.lastTurn) return;
    stopAudio();
    screenAnswer(S.lastTurn, { animate: false });
    if (S.lastTurn.voice) playVoice(S.lastTurn.voice);
  }

  async function triggerEmergency() {
    stopAudio();
    sfx.alert();
    screenProcessing("Emergency");
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
      screenNotice("Emergency", "Call 112 for ambulance & police immediately.", "emergency");
    }
  }

  // ---------- Microphone / Audio recording (16 kHz mono WAV) ----------
  let rec = null;
  let recStream = null;
  let abortRecording = false;

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
    if (S.recording || S.busy) return;
    stopAudio();
    abortRecording = false;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      recStream = stream;
      const mr = new MediaRecorder(stream);
      const chunks = [];
      mr.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
      mr.onstop = async () => {
        if (recStream) {
          recStream.getTracks().forEach((tr) => tr.stop());
          recStream = null;
        }
        S.recording = false;
        el.rec.hidden = true;
        softkeysForState();

        if (abortRecording) {
          abortRecording = false;
          return;
        }

        if (chunks.length > 0) {
          try {
            screenProcessing("Processing audio");
            const wavBlob = await toWav(new Blob(chunks, { type: mr.mimeType || "audio/webm" }));
            await sendSpeechAudio(wavBlob);
          } catch (err) {
            S.busy = false;
            screenNotice("Audio Error", err.message);
            setControls();
          }
        } else {
          screenNotice("No Audio", "No sound detected. Press CALL or # to try again.");
          setControls();
        }
      };
      rec = mr;
      mr.start();
      S.recording = true;
      el.rec.hidden = false;
      screenListening();
      softkeysForState();
    } catch (_) {
      S.recording = false;
      el.rec.hidden = true;
      const l = S.langSelected ? S.lang : "en-IN";
      const i18n = I18N[l] || I18N["en-IN"];
      screenNotice(i18n.micDeniedTitle || "Mic Blocked", i18n.micDeniedMsg || "Microphone access was denied.\nYou can type your question in the input box below.");
      el.typeInput.disabled = false;
      el.typeSend.disabled = false;
      el.typeInput.focus();
    }
  }

  function stopRecording({ abort = false } = {}) {
    if (abort) {
      abortRecording = true;
    }
    if (rec && rec.state === "recording") {
      rec.stop();
    } else {
      S.recording = false;
      el.rec.hidden = true;
    }
    rec = null;
  }

  async function sendSpeechAudio(wavBlob) {
    if (S.busy) return;
    S.busy = true;
    setControls();
    screenProcessing("Transcribing speech");
    const fd = new FormData();
    fd.append("audio", wavBlob, "question.wav");
    fd.append("simple", "false");
    try {
      const r = await post(`/api/conversations/${S.convId}/speech`, fd);
      if (r.error) {
        screenNotice("Not understood", r.hint ? r.hint.text : r.error.message);
        S.busy = false; setControls();
        return;
      }
      if (r.turn) {
        renderAnswer(r.turn);
      }
    } catch (e) {
      S.busy = false; screenNotice("Error", e.message); setControls();
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
    screenProcessing("Getting GPS");
    navigator.geolocation.getCurrentPosition(
      (pos) => submitFacilitiesSearch({ lat: pos.coords.latitude, lon: pos.coords.longitude, emergency: S.phase === "emergency" }),
      () => screenLocation("Location off. Type a place or PIN."),
      { timeout: 10000, maximumAge: 60000 },
    );
  }

  async function submitFacilitiesSearch(body) {
    S.busy = true; setControls();
    screenProcessing("Searching");
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
      S.busy = false; S.phase = "location"; screenNotice("Error", e.message);
    }
    setControls();
  }

  // ---------- Keypad & Button Actions ----------
  async function onCall() {
    pressFlash(el.call);
    sfx.soft();
    wake();
    if (S.busy) return;

    // If language has not been selected, announce the language menu instead.
    if (!S.langSelected) {
      screenMainMenu({ speak: true });
      return;
    }

    // Keep green CALL button's existing call/session behavior unchanged (connects line, does not toggle recording)
    if (!S.convId) {
      screenProcessing("Connecting");
      try {
        const r = await post("/api/conversations", { language: S.lang });
        S.convId = r.id;
        S.startedAt = Date.now();
        screenReady();
      } catch (e) {
        screenNotice("Error", e.message || "Failed to connect");
      }
    } else {
      screenReady();
    }
  }

  function onEnd() {
    pressFlash(el.end);
    sfx.end();
    wake();

    // Red END button: cancel/stop and return-to-menu control
    if (S.recording) {
      stopRecording({ abort: true });
    }

    // Stop ongoing menu/audio playback safely, and return to main menu
    stopAudio();
    S.busy = false;
    screenMainMenu({ speak: false });
  }

  function onStar() {
    const btn = el.keypad.querySelector('[data-d="*"]');
    pressFlash(btn);
    sfx.key("*");
    wake();

    // Stop recording without submitting incomplete audio
    if (S.recording) {
      stopRecording({ abort: true });
    }
    stopAudio();
    S.busy = false;
    screenMainMenu({ speak: true });
  }

  function onHash() {
    const btn = el.keypad.querySelector('[data-d="#"]');
    pressFlash(btn);
    sfx.key("#");
    wake();
    // Do not assign recording toggle to #
  }

  function onDigit(d) {
    sfx.key(d);
    litKeypad();
    wake();
    if (S.busy) return;

    // While recording, ignore number inputs so recording is not interrupted
    if (S.recording) {
      if (d === "*") return onStar();
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
      if (d === "*") return onStar();
      return;
    }

    switch (d) {
      case "1": return selectLanguage("hi-IN");
      case "2": return selectLanguage("en-IN");
      case "3": return selectLanguage("as-IN");
      case "4": return goLocation();
      case "5": return simpler();
      case "*": return onStar();
      case "#": return onHash();
      case "0": return triggerEmergency();
    }
  }

  async function onSoftLeft() {
    pressFlash(el.softL);
    sfx.soft();
    wake();
    if (S.busy) return;

    // Press dash again to stop recording, finalize audio, and submit it to speech endpoint
    if (S.recording) {
      stopRecording({ abort: false });
      return;
    }

    if (S.phase === "location") return useGps();
    if (S.phase === "emergency") return screenNotice("Call 112", "In a real phone, this dials 112 emergency services.", "emergency");
    if (S.phase === "help") return screenNotice("Call 108", "Call 108 for ambulance in North East India.", "emergency");

    // Press dash once to start microphone recording (or start next recording after response)
    if (!S.langSelected) {
      screenMainMenu({ speak: true });
      return;
    }

    await startSpeaking();
  }

  function onSoftRight() {
    sfx.soft();
    if (S.busy) return;
    if (S.recording) {
      return onStar();
    }
    return screenMainMenu({ speak: false });
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
  el.call.onclick = onCall;
  el.end.onclick = onEnd;
  el.keypad.addEventListener("click", (e) => {
    const k = e.target.closest(".key");
    if (k && k.dataset.d) onDigit(k.dataset.d);
  });
  el.navUp.onclick = () => onNav(-1);
  el.navDown.onclick = () => onNav(1);
  el.softL.onclick = onSoftLeft;
  el.softR.onclick = onSoftRight;

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
    if (e.key === "Enter") { e.preventDefault(); return onCall(); }
    if (e.key === "Escape") { e.preventDefault(); return onEnd(); }
    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      e.preventDefault();
      const up = e.key === "ArrowUp";
      pressFlash(up ? el.navUp : el.navDown);
      return onNav(up ? -1 : 1);
    }
    if (e.key === "ArrowLeft" || e.key === "-" || e.key === " ") {
      e.preventDefault();
      if (!e.repeat) return onSoftLeft();
    }
    if (e.key === "ArrowRight") { e.preventDefault(); pressFlash(el.softR); return onSoftRight(); }
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
  screenMainMenu({ speak: false });
  fitPhone();
  setInterval(() => { if (S.phase === "select_language" && S.view === "menu") screenMainMenu({ speak: false }); }, 60000);

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
