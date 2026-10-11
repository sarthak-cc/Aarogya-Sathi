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
    hospitalEmpty: $("hospitalEmpty"),
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
    gpsPending: false,
    facSearchPending: false,
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
  el.body.addEventListener("scroll", updateArrows);
  function scrollBy(dir) {
    const lh = 28;
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
      readyHelp: "– दबाकर बोलना शुरू करें<br>– दोबारा दबाकर भेजें<br>4: नज़दीकी अस्पताल | 6: कैमरा<br>*: मेनू | END: रोकें",
      listeningTitle: "सुन रहे हैं",
      listeningMsg: "अपना सवाल बोलिए…",
      listeningDashSend: "भेजने के लिए – दबाएँ",
      processingTitle: "प्रक्रिया जारी",
      processingWait: "कृपया प्रतीक्षा करें",
      responseTitle: "उत्तर",
      nextPrompt: "अगला सवाल बोलने के लिए – दबाएँ",
      scrollDownHint: "आगे पढ़ने के लिए ▼ दबाएँ",
      micDeniedTitle: "माइक बंद है",
      micDeniedMsg: "माइक्रोफ़ोन की अनुमति नहीं मिली।\nनीचे दिए गए बॉक्स में सवाल टाइप करें।",
      menuSpoken: "हिंदी के लिए 1 दबाएँ। अंग्रेजी के लिए 2 दबाएँ। असमिया के लिए 3 दबाएँ। नज़दीकी अस्पताल के लिए 4 दबाएँ। कैमरा के लिए 6 दबाएँ। बोलने के लिए डैश बटन दबाएँ। मेनू दोबारा सुनने के लिए स्टार दबाएँ। रोकने के लिए एंड बटन दबाएँ।",
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
      readyHelp: "– টিপি কথা কওক<br>– আকৌ টিপি প্ৰেৰণ কৰক<br>4: ওচৰৰ চিকিৎসালয় | 6: কেমেৰা<br>*: মেনু | END: বন্ধ",
      listeningTitle: "শুনি থকা হৈছে",
      listeningMsg: "আপোনাৰ প্ৰশ্নটো কওক…",
      listeningDashSend: "প্ৰেৰণ কৰিবলৈ – টিপক",
      processingTitle: "প্ৰক্ৰিয়া চলিছে",
      processingWait: "অনুগ্ৰহ কৰি অপেক্ষা কৰক",
      responseTitle: "উত্তৰ",
      nextPrompt: "পৰৱৰ্তী প্ৰশ্নৰ বাবে – টিপক",
      scrollDownHint: "অধিক পঢ়িবলৈ ▼ টিপক",
      micDeniedTitle: "মাইক সংযোগ নাই",
      micDeniedMsg: "মাইক্ৰ'ফোন ব্যৱহাৰৰ অনুমতি নাই।\nতলৰ বাকচত প্ৰশ্নটো লিখক।",
      menuSpoken: "হিন্দীৰ বাবে 1 টিপক। ইংৰাজীৰ বাবে 2 টিপক। অসমীয়াৰ বাবে 3 টিপক। ওচৰৰ হাস্পতালৰ বাবে 4 টিপক। কেমেৰাৰ বাবে 6 টিপক। কথা ক'বলৈ ডেশ্ব টিপক। মেনু আকৌ শুনিবলৈ ষ্টাৰ টিপক। বন্ধ কৰিবলৈ এণ্ড টিপক।",
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
      readyHelp: "Press – (dash) to speak<br>Press – again to send<br>4: Hospitals | 6: Camera<br>*: Main Menu | END: Stop",
      listeningTitle: "LISTENING",
      listeningMsg: "Speak your question…",
      listeningDashSend: "Press – (dash) to send",
      processingTitle: "PROCESSING",
      processingWait: "Please wait",
      responseTitle: "RESPONSE",
      nextPrompt: "Press – (dash) to speak next",
      scrollDownHint: "Press ▼ to read more",
      micDeniedTitle: "Mic Blocked",
      micDeniedMsg: "Microphone access was denied.\nYou can type your question in the input box below.",
      menuSpoken: "Press 1 for Hindi. Press 2 for English. Press 3 for Assamese. Press 4 for nearby hospitals. Press 6 for the camera. Press dash to speak. Press star to replay the main menu. Press END to stop and return to the main menu.",
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
        <li><b>6</b> Camera</li>
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
      setTimeout(() => {
        if (el.body.scrollHeight > el.body.clientHeight + 4) {
          const hint = document.createElement("div");
          hint.className = "lcd-scroll-hint";
          hint.textContent = i18n.scrollDownHint || "Press ▼ to read more";
          el.body.appendChild(hint);
          updateArrows();
        }
      }, 50);
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

  function cleanMock(str) {
    if (!str) return "";
    return String(str).replace(/\(mock(?:\s+[a-z]{2}-[A-Z]{2})?\)\s*:?\s*/gi, "").trim();
  }

  // ---------- Voice playback ----------
  let currentAudioVoice = null;

  function stopAudio() {
    if (el.player) {
      el.player.pause();
      try { el.player.currentTime = 0; } catch (_) {}
      el.player.removeAttribute("src");
    }
  }

  function clearAutoplayPrompt() {
    if (el.body) {
      const existingLcd = el.body.querySelector(".lcd-tap-hear");
      if (existingLcd) existingLcd.remove();
    }
    const pulsingBtn = document.querySelector(".tap-to-hear-pulse");
    if (pulsingBtn) {
      pulsingBtn.textContent = "Hear again";
      pulsingBtn.classList.remove("tap-to-hear-pulse");
    }
  }

  function showAutoplayPrompt(voice, langCode, targetCard) {
    if (!voice || !voice.audio_url || el.mute.checked) return;
    const l = langCode || (S.lastTurn && S.lastTurn.answer && S.lastTurn.answer.lang) || S.lang || "en-IN";
    const tapLabels = {
      "hi-IN": "सुनें (Tap to hear)",
      "as-IN": "শুনক (Tap to hear)",
      "en-IN": "Tap to hear",
      "bn-IN": "শুনুন (Tap to hear)",
    };
    const label = tapLabels[l] || tapLabels[S.lang] || "Tap to hear";

    // 1. Highlight button on Call log card
    const card = targetCard || (el.turns ? el.turns.querySelector("li.turn") : null);
    if (card) {
      const hearBtn = card.querySelector('[data-act="hear"], [data-act="repeat"]');
      if (hearBtn) {
        hearBtn.innerHTML = `▶ <strong>${esc(label)}</strong>`;
        hearBtn.classList.add("tap-to-hear-pulse");
      }
    }

    // 2. Add clickable button on Nokia LCD
    if (el.body && !el.body.querySelector(".lcd-tap-hear")) {
      const hint = document.createElement("div");
      hint.className = "lcd-tap-hear";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = `▶ ${label}`;
      btn.onclick = (e) => {
        e.stopPropagation();
        playVoice(voice);
        clearAutoplayPrompt();
      };
      hint.appendChild(btn);
      el.body.appendChild(hint);
      updateArrows();
    }
  }

  function playVoice(voice, { onBlocked, onPlay } = {}) {
    if (!voice || !voice.audio_url) return;
    currentAudioVoice = voice;
    if (el.mute.checked) return;
    stopAudio();

    const audioSrc = voice.audio_url.startsWith("http")
      ? voice.audio_url
      : (window.location.origin + (voice.audio_url.startsWith("/") ? "" : "/") + voice.audio_url);

    el.player.src = audioSrc;
    try { el.player.load(); } catch (_) {}

    const p = el.player.play();
    if (p && typeof p.then === "function") {
      p.then(() => {
        if (onPlay) onPlay();
        clearAutoplayPrompt();
      }).catch((err) => {
        console.warn("Audio playback blocked by browser policy:", err);
        if (onBlocked) onBlocked(err);
        else showAutoplayPrompt(voice);
      });
    }
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
    camLabels();
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
    if (S.lastTurn && S.lastTurn.question && S.lastTurn.question.text === camT("heading")) {
      return repeat();
    }
    if (!S.convId || !S.lastTurn || S.busy) return;
    stopAudio();
    clearAutoplayPrompt();
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
    clearAutoplayPrompt();
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

  function showGpsError(msg) {
    if (el.hospitalEmpty) el.hospitalEmpty.hidden = true;
    el.hospitalsList.innerHTML = `
      <div class="notice" style="border-left:4px solid #E67E22;margin-bottom:1rem">
        <b>GPS Notice</b>
        <p style="margin:4px 0 0">${esc(msg)}</p>
      </div>
      <div class="notice emergency" style="margin-bottom:1rem">
        <b>For immediate medical emergencies, call directly:</b>
      </div>
      <ul class="numbers">
        <li><span class="num">112</span>National Emergency</li>
        <li><span class="num">108</span>Ambulance Service</li>
        <li><span class="num">104</span>Health Helpline</li>
      </ul>
    `;
  }

  function useGps() {
    if (S.gpsPending) return;
    if (!navigator.geolocation) {
      showGpsError("Geolocation is not supported by your browser. Please type your location or PIN code.");
      return screenLocation("No GPS found. Type place or PIN.");
    }
    if (window.isSecureContext === false && location.protocol !== "https:" && location.hostname !== "localhost" && location.hostname !== "127.0.0.1") {
      showGpsError("Browser security requires an HTTPS connection for GPS location. Please type your town or 6-digit PIN code above.");
      return screenLocation("HTTPS needed for GPS. Type place.");
    }

    S.gpsPending = true;
    if (el.hospitalEmpty) el.hospitalEmpty.hidden = true;
    if (el.facGpsBtn) {
      el.facGpsBtn.disabled = true;
      el.facGpsBtn.textContent = "Locating…";
    }
    el.hospitalsList.innerHTML = `
      <div class="notice">
        <b>Detecting your location via GPS…</b>
        <p style="margin:4px 0 0;font-size:0.85rem;color:var(--muted)">Please allow location access if prompted by your browser.</p>
      </div>
    `;
    screenProcessing("Getting GPS");

    function onPos(pos) {
      S.gpsPending = false;
      if (el.facGpsBtn) {
        el.facGpsBtn.disabled = false;
        el.facGpsBtn.textContent = "GPS";
      }
      submitFacilitiesSearch({
        lat: pos.coords.latitude,
        lon: pos.coords.longitude,
        accuracy_m: pos.coords.accuracy,
        emergency: S.phase === "emergency",
      });
    }

    function onErr(err, isRetry = false) {
      if (!isRetry && err && err.code === 3) {
        // High accuracy timed out - try once with normal accuracy
        navigator.geolocation.getCurrentPosition(
          onPos,
          (retryErr) => onErr(retryErr, true),
          { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
        );
        return;
      }
      S.gpsPending = false;
      if (el.facGpsBtn) {
        el.facGpsBtn.disabled = false;
        el.facGpsBtn.textContent = "GPS";
      }
      let msg = "Could not detect your location. Please type your town or 6-digit PIN code.";
      let screenMsg = "Location off. Type place or PIN.";
      if (err) {
        if (err.code === 1) { // PERMISSION_DENIED
          msg = "Location permission was denied. Please allow location access in your browser settings, or type your town/PIN code above.";
          screenMsg = "GPS denied. Type place.";
        } else if (err.code === 2) { // POSITION_UNAVAILABLE
          msg = "Location signal unavailable. Please type your town, district, or 6-digit PIN code.";
          screenMsg = "Signal lost. Type place.";
        } else if (err.code === 3) { // TIMEOUT
          msg = "GPS request timed out. Please click GPS to retry or type your town/PIN code above.";
          screenMsg = "GPS timed out. Type place.";
        }
      }
      showGpsError(msg);
      screenLocation(screenMsg);
    }

    navigator.geolocation.getCurrentPosition(
      onPos,
      (err) => onErr(err, false),
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 }
    );
  }

  async function submitFacilitiesSearch(body) {
    if (S.facSearchPending) return;
    S.facSearchPending = true;
    S.busy = true; setControls();
    if (el.hospitalEmpty) el.hospitalEmpty.hidden = true;
    if (el.facSearchBtn) el.facSearchBtn.disabled = true;
    const targetLabel = body.text ? `“${body.text}”` : "your coordinates";
    el.hospitalsList.innerHTML = `
      <div class="notice">
        <b>Searching for facilities near ${esc(targetLabel)}…</b>
      </div>
    `;
    screenProcessing("Searching");
    try {
      const r = await post("/api/facilities/search", body);
      S.facSearchPending = false;
      S.busy = false; S.pinBuf = "";
      if (el.facSearchBtn) el.facSearchBtn.disabled = false;
      S.phase = "help"; S.help = r;
      screenHelp(r);
      sfx.blip();
      el.convoEmpty.hidden = true;
      el.turns.prepend(helpElement(r));
      renderHospitalsTab(r);
      switchTab("hospitals");
    } catch (e) {
      S.facSearchPending = false;
      S.busy = false; S.phase = "location";
      if (el.facSearchBtn) el.facSearchBtn.disabled = false;
      screenNotice("Error", e.message);
      el.hospitalsList.innerHTML = `
        <div class="notice" style="border-left:4px solid var(--alert);margin-bottom:1rem">
          <b>Search failed</b>
          <p style="margin:4px 0 0">${esc(e.message || "Could not reach the server. Please check your connection.")}</p>
        </div>
        <ul class="numbers">
          <li><span class="num">112</span>National Emergency</li>
          <li><span class="num">108</span>Ambulance Service</li>
        </ul>
      `;
    }
    setControls();
  }

  // ---------- Keypad & Button Actions ----------
  async function onCall() {
    pressFlash(el.call);
    sfx.soft();
    wake();
    if (S.busy || C.open) return;

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
    if (C.open) return closeCamera();
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

    if (C.open) closeCamera();
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
    if (C.open) { if (d === "*") onStar(); return; } // camera open: only * (menu) and END act

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
      case "6": return openCamera();
      case "*": return onStar();
      case "#": return onHash();
      case "0": return triggerEmergency();
    }
  }

  async function onSoftLeft() {
    pressFlash(el.softL);
    sfx.soft();
    wake();
    if (S.busy || C.open) return;

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
    if (C.open) return closeCamera();
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
    const cardEl = turnElement(turn);
    el.convoEmpty.hidden = true;
    el.turns.prepend(cardEl);
    if (turn.voice) {
      playVoice(turn.voice, {
        onBlocked: () => {
          showAutoplayPrompt(turn.voice, turn.answer && turn.answer.lang, cardEl);
        }
      });
    }
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
    const questionText = cleanMock(t.question ? t.question.text : (t.transcript || "Question"));
    const steps = Object.entries(t.timings_ms || {}).filter(([k]) => STEP_NAMES[k]);
    const total = steps.reduce((a, [, v]) => a + v, 0) || 1;
    const BLOCKS = 48;

    li.innerHTML = `
      <p class="turn-time" style="margin:0">${timeStamp()} · ${esc(langCode(S.lang))}</p>
      <div>
        <p class="said" lang="${langAttr(S.lang)}">“${esc(questionText)}”</p>
        ${t.english && S.lang !== "en-IN" ? `
          <details class="said-pivot">
            <summary>English translation</summary>
            <p class="said-meta" style="margin:2px 0 0">English pivot: ${esc(cleanMock(t.english))}</p>
          </details>` : ""}
      </div>
      <div class="flag ${lvl}"><b>${esc(flagText)}</b>${matches ? `<br>Matched: ${esc(matches)}` : ""}</div>
      ${t.medicine && t.medicine.request ? `<div class="flag med"><b>Medicine Safety:</b> Prescriptions and dosage requests are strictly filtered. General safety guidance provided.</div>` : ""}
      <div>
        <p style="margin:0 0 .35rem"><span class="source">${esc(t.answer.source || "Live AI")}</span>${t.voice && t.voice.provider ? `<span class="source" style="background:#EAF3EC;color:#2F7D45">${esc(t.voice.provider)}</span>` : ""}</p>
        <p class="answer" lang="${langAttr(t.answer.lang || S.lang)}">${esc(cleanMock(t.answer.text))}</p>
        ${t.answer.english && t.answer.lang !== "en-IN" ? `
          <details class="said-pivot" style="margin-top:6px">
            <summary>English text</summary>
            <p class="answer-en" style="margin:2px 0 0">English: ${esc(cleanMock(t.answer.english))}</p>
          </details>` : ""}
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

    li.querySelector('[data-act="repeat"]').onclick = () => {
      clearAutoplayPrompt();
      repeat();
    };
    li.querySelector('[data-act="simpler"]').onclick = () => { simpler(); };
    const hBtn = li.querySelector('[data-act="hospital"]');
    if (hBtn) hBtn.onclick = () => goLocation();
    return li;
  }


  function facilityItem(f, first) {
    const dirLink = f.directions_url ? `<a href="${esc(f.directions_url)}" target="_blank" rel="noopener noreferrer" class="fac-dir">Directions ↗</a>` : "";
    const mapLink = f.map_url ? `<a href="${esc(f.map_url)}" target="_blank" rel="noopener noreferrer" class="fac-map">Map ↗</a>` : "";
    const emergBadge = f.emergency === "yes" ? '<span class="source emergency" style="font-size:0.75rem;padding:2px 6px">Emergency 24x7</span>' : "";
    return `<li class="facility${first ? " nearest" : ""}">
      <p class="fac-name">
        <b>${esc(f.name)}</b>
        ${f.distance_km != null ? `<span class="km">${f.distance_km} km</span>` : ""}
        ${first ? ' <span class="source">Suggested</span>' : ""}
        ${emergBadge}
      </p>
      <p class="fac-meta">${[f.address, f.district, f.state].filter(Boolean).map(esc).join(", ")}</p>
      <p class="fac-meta">
        ${f.phone ? `Phone: <a href="tel:${esc(f.phone)}">${esc(f.phone)}</a> · ` : ""}
        ${f.verified ? '<span class="verify ok">Verified</span>' : '<span class="verify no">Community data</span>'}
        ${dirLink}${mapLink}
      </p>
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
    if (el.hospitalEmpty) el.hospitalEmpty.hidden = true;
    const facs = r.facilities || [];
    const placeName = (r.place && r.place.name) || (r.place && r.place.lat ? `${r.place.lat.toFixed(3)}, ${r.place.lon.toFixed(3)}` : "you");

    if (facs.length > 0) {
      const limHtml = r.limitation ? `<p class="fac-meta" style="margin-top:6px;color:#6E5200">ℹ ${esc(r.limitation)}</p>` : "";
      el.hospitalsList.innerHTML = `
        <div class="notice" style="margin-bottom:1rem">
          <b>Found ${facs.length} facilities near ${esc(placeName)}</b>
          ${limHtml}
        </div>
        <ol class="facilities">${facs.map((f, i) => facilityItem(f, i === 0)).join("")}</ol>
        <div style="margin-top:1.25rem;padding-top:0.75rem;border-top:1px solid var(--rule)">
          <p class="cards" style="margin-bottom:0.5rem">Emergency Helplines</p>
          <ul class="numbers">
            <li><span class="num">112</span>National Emergency</li>
            <li><span class="num">108</span>Ambulance Service</li>
            <li><span class="num">104</span>Health Information</li>
            <li><span class="num">14416</span>Tele-MANAS Mental Health</li>
          </ul>
        </div>
      `;
      return;
    }

    if (r.error) {
      el.hospitalsList.innerHTML = `
        <div class="notice" style="border-left:4px solid var(--alert);margin-bottom:1rem">
          <b>Live hospital lookup temporarily unavailable</b>
          <p style="margin:4px 0 0">${esc((r.error && r.error.message) || r.limitation || "Could not reach live OpenStreetMap servers.")}</p>
          <p style="margin:6px 0 0;font-size:0.85rem;color:var(--muted)">Try searching a nearby major town (e.g. Guwahati, Dispur, Silchar, Dibrugarh) or enter a 6-digit PIN code.</p>
        </div>
        <div class="notice emergency" style="margin-bottom:1rem">
          <b>For immediate emergency assistance, call directly:</b>
        </div>
        <ul class="numbers">
          <li><span class="num">112</span>National Emergency (Police, Fire, Ambulance)</li>
          <li><span class="num">108</span>Ambulance Service (Assam & North East)</li>
          <li><span class="num">104</span>Health Information Helpline</li>
          <li><span class="num">14416</span>Tele-MANAS Mental Health</li>
        </ul>
      `;
      return;
    }

    el.hospitalsList.innerHTML = `
      <div class="notice" style="margin-bottom:1rem">
        <b>No facilities found near ${esc(placeName)}</b>
        <p style="margin:4px 0 0">${esc(r.limitation || "No medical facilities found within the search radius in the available data.")}</p>
        <p style="margin:6px 0 0;font-size:0.85rem;color:var(--muted)">Try searching a nearby town, district headquarters, or a 6-digit PIN code.</p>
      </div>
      <ul class="numbers">
        <li><span class="num">112</span>National Emergency</li>
        <li><span class="num">108</span>Ambulance Service</li>
        <li><span class="num">104</span>Health Helpline</li>
      </ul>
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

  // ---------- Camera prototype: flip to the rear, preview, flash, capture, analyze ----------
  // Lifecycle: open → requesting → live (or upload) → captured → analyzing → result (flip front) | cancel.
  // The camera runs only while the rear is shown; every exit path calls closeCamera().
  const CAM_T = {
    "en-IN": { ready: "CAMERA READY", requesting: "REQUESTING CAMERA", denied: "CAMERA PERMISSION NEEDED", flashOn: "FLASH ON",
      flashOff: "FLASH OFF", captured: "IMAGE CAPTURED", toAnalyze: "READY TO ANALYZE", analyzing: "ANALYZING...", done: "RESPONSE READY",
      unavailable: "CAMERA UNAVAILABLE", failed: "ANALYSIS FAILED", cancelled: "CANCELLED", flash: "Flash", capture: "Capture",
      upload: "Upload photo", switchCam: "Switch", retake: "Retake", analyze: "Analyze", cancel: "Cancel", back: "Back to phone",
      open: "Camera", note: "Add a few words (optional)",
      privacy: "Analyze sends this one photo to Groq AI for analysis. Aarogya Saathi does not save it.",
      flashNote: "The flash is a simulated light for this prototype.", torchNote: "Simulated light, and the phone's torch is on.",
      noCamera: "No camera found. You can upload a photo instead.", deniedMsg: "Camera permission was refused. Allow it in browser settings, or upload a photo.",
      insecure: "The camera needs https:// or localhost. You can upload a photo instead.", heading: "PHOTO CHECK" },
    "hi-IN": { ready: "कैमरा तैयार", requesting: "कैमरा अनुमति माँगी जा रही है", denied: "कैमरा अनुमति चाहिए", flashOn: "फ़्लैश चालू",
      flashOff: "फ़्लैश बंद", captured: "फ़ोटो ली गई", toAnalyze: "जाँच के लिए तैयार", analyzing: "जाँच हो रही है...", done: "जवाब तैयार",
      unavailable: "कैमरा उपलब्ध नहीं", failed: "जाँच विफल", cancelled: "रद्द किया गया", flash: "फ़्लैश", capture: "फ़ोटो लें",
      upload: "फ़ोटो चुनें", switchCam: "कैमरा बदलें", retake: "फिर से लें", analyze: "जाँचें", cancel: "रद्द करें", back: "फ़ोन पर लौटें",
      open: "कैमरा", note: "कुछ शब्द लिखें (वैकल्पिक)",
      privacy: "जाँचें दबाने पर यही एक फ़ोटो Groq AI को भेजी जाएगी। आरोग्य साथी इसे सहेजता नहीं है।",
      flashNote: "यह फ़्लैश इस प्रोटोटाइप की नकली रोशनी है।", torchNote: "नकली रोशनी, और फ़ोन की टॉर्च भी चालू है।",
      noCamera: "कैमरा नहीं मिला। आप फ़ोटो चुनकर भेज सकते हैं।", deniedMsg: "कैमरा की अनुमति नहीं मिली। ब्राउज़र सेटिंग में अनुमति दें, या फ़ोटो चुनें।",
      insecure: "कैमरा के लिए https:// या localhost ज़रूरी है। आप फ़ोटो चुन सकते हैं।", heading: "फ़ोटो जाँच" },
    "as-IN": { ready: "কেমেৰা সাজু", requesting: "কেমেৰাৰ অনুমতি বিচৰা হৈছে", denied: "কেমেৰাৰ অনুমতি লাগে", flashOn: "ফ্লেশ্ব অন",
      flashOff: "ফ্লেশ্ব অফ", captured: "ফটো লোৱা হ'ল", toAnalyze: "বিশ্লেষণৰ বাবে সাজু", analyzing: "বিশ্লেষণ চলি আছে...", done: "উত্তৰ সাজু",
      unavailable: "কেমেৰা উপলব্ধ নহয়", failed: "বিশ্লেষণ বিফল", cancelled: "বাতিল কৰা হ'ল", flash: "ফ্লেশ্ব", capture: "ফটো লওক",
      upload: "ফটো বাছক", switchCam: "কেমেৰা সলনি", retake: "পুনৰ লওক", analyze: "বিশ্লেষণ কৰক", cancel: "বাতিল কৰক", back: "ফোনলৈ উভতি যাওক",
      open: "কেমেৰা", note: "কেইটামান শব্দ লিখক (ইচ্ছাধীন)",
      privacy: "বিশ্লেষণ টিপিলে এই এখন ফটোহে Groq AI লৈ পঠিওৱা হ'ব। আৰোগ্য সাথীয়ে ইয়াক সংৰক্ষণ নকৰে।",
      flashNote: "এই ফ্লেশ্ব প্ৰ'ট'টাইপৰ অনুকৰণ পোহৰ।", torchNote: "অনুকৰণ পোহৰ, আৰু ফোনৰ টৰ্চো অন আছে।",
      noCamera: "কেমেৰা পোৱা নগ'ল। আপুনি ফটো বাছি পঠিয়াব পাৰে।", deniedMsg: "কেমেৰাৰ অনুমতি পোৱা নগ'ল। ব্ৰাউজাৰ ছেটিঙত অনুমতি দিয়ক, বা ফটো বাছক।",
      insecure: "কেমেৰাৰ বাবে https:// বা localhost লাগে। আপুনি ফটো বাছিব পাৰে।", heading: "ফটো পৰীক্ষা" },
  };
  const camT = (k) => ((CAM_T[S.lang] || CAM_T["en-IN"])[k]) || CAM_T["en-IN"][k];
  const C = { open: false, stream: null, facing: "environment", flash: false, torch: false, blob: null, shotUrl: null,
    busy: false, abort: null, devices: 0 };
  const cam = {
    flipper: $("flipper"), front: $("phone"), back: $("phoneBack"), col: document.querySelector(".phone-col"),
    led: $("led"), cone: $("cone"), vf: $("viewfinder"), video: $("camVideo"), shot: $("camShot"), status: $("camStatus"),
    controls: $("camControls"), live: $("camLive"), flashBtn: $("camFlash"), capture: $("camCapture"), upload: $("camUpload"),
    switchBtn: $("camSwitch"), retake: $("camRetake"), analyze: $("camAnalyze"), cancel: $("camCancel"), file: $("camFile"),
    note: $("camNote"), noteLabel: $("camNoteLabel"), privacy: $("camPrivacy"), flashNote: $("camFlashNote"),
    openBtn: $("cameraOpenBtn"), openLabel: $("cameraOpenLabel"),
  };

  function camStatus(key, { bad = false, detail = "" } = {}) {
    const text = camT(key);
    cam.status.textContent = text;
    cam.live.textContent = detail ? `${text} · ${detail}` : text;
    cam.live.classList.toggle("bad", bad);
  }
  function camLabels() {
    cam.flashBtn.textContent = `${camT("flash")}: ${C.flash ? "ON" : "OFF"}`;
    cam.capture.textContent = camT("capture"); cam.upload.textContent = camT("upload");
    cam.switchBtn.textContent = camT("switchCam"); cam.retake.textContent = camT("retake");
    cam.analyze.textContent = camT("analyze"); cam.cancel.textContent = C.busy ? camT("cancel") : camT("back");
    cam.noteLabel.textContent = camT("note"); cam.privacy.textContent = camT("privacy");
    cam.flashNote.textContent = C.torch ? camT("torchNote") : camT("flashNote");
    cam.openLabel.textContent = camT("open");
    [cam.controls, cam.openBtn].forEach((n) => { n.lang = langAttr(S.lang); });
  }
  function camButtons() {
    const live = !!C.stream, shot = !!C.blob;
    cam.capture.hidden = shot; cam.capture.disabled = !live || C.busy;
    cam.upload.hidden = shot; cam.upload.disabled = C.busy;
    cam.switchBtn.hidden = shot || !live || C.devices < 2; cam.switchBtn.disabled = C.busy;
    cam.retake.hidden = !shot; cam.retake.disabled = C.busy;
    cam.analyze.hidden = !shot; cam.analyze.disabled = C.busy;
    cam.note.disabled = C.busy;
    cam.flashBtn.setAttribute("aria-pressed", String(C.flash));
    camLabels();
  }

  function positionCone() { // start the light cone at the LED; layout offsets ignore the flip/scale transforms
    const m = cam.led.offsetParent; // .cam-module
    if (!m) return;
    cam.back.style.setProperty("--led-x", `${m.offsetLeft + cam.led.offsetLeft + cam.led.offsetWidth / 2}px`);
    cam.back.style.setProperty("--led-y", `${m.offsetTop + cam.led.offsetTop + cam.led.offsetHeight / 2}px`);
  }

  function flip(toBack) {
    cam.flipper.classList.toggle("flipped", toBack);
    cam.back.toggleAttribute("inert", !toBack); cam.back.setAttribute("aria-hidden", String(!toBack));
    cam.front.toggleAttribute("inert", toBack); cam.front.setAttribute("aria-hidden", String(toBack));
    cam.controls.hidden = !toBack;
    cam.col.classList.toggle("camera-mode", toBack);
  }

  async function openCamera() {
    if (C.open || S.busy) return;
    if (S.recording) stopRecording({ abort: true });
    stopAudio();
    C.open = true; C.blob = null; C.flash = false; setFlash(false);
    S.prevPhase = S.phase; S.phase = "camera";
    showShot(null);
    flip(true);
    requestAnimationFrame(positionCone);
    camButtons();
    cam.flashBtn.focus({ preventScroll: true });
    await startStream();
  }

  async function startStream() {
    stopStream();
    if (!window.isSecureContext) { camStatus("unavailable", { bad: true, detail: camT("insecure") }); return camButtons(); }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { camStatus("unavailable", { bad: true, detail: camT("noCamera") }); return camButtons(); }
    camStatus("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: C.facing }, width: { ideal: 1280 }, height: { ideal: 960 } }, audio: false });
      if (!C.open || C.blob) { stream.getTracks().forEach((t) => t.stop()); return; } // closed or captured while asking
      C.stream = stream;
      cam.video.srcObject = stream; cam.video.hidden = false;
      await cam.video.play().catch(() => {});
      try { C.devices = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput").length; } catch (_) { C.devices = 1; }
      camStatus("ready");
      if (C.flash) applyTorch(true);
    } catch (e) {
      const denied = e && (e.name === "NotAllowedError" || e.name === "SecurityError");
      camStatus(denied ? "denied" : "unavailable", { bad: true, detail: denied ? camT("deniedMsg") : camT("noCamera") });
    }
    camButtons();
  }

  function stopStream() {
    if (C.stream) C.stream.getTracks().forEach((t) => t.stop());
    C.stream = null; C.torch = false;
    cam.video.pause(); cam.video.srcObject = null; cam.video.hidden = true;
  }

  // Simulated flash (always) + real torch only where the browser and camera say they support it.
  function setFlash(on) {
    C.flash = on;
    cam.led.classList.toggle("on", on); cam.cone.classList.toggle("on", on); cam.vf.classList.toggle("lit", on);
    if (C.open) { camStatus(on ? "flashOn" : "flashOff"); applyTorch(on); }
    camButtons();
  }
  async function applyTorch(on) {
    const track = C.stream && C.stream.getVideoTracks()[0];
    const caps = track && track.getCapabilities ? track.getCapabilities() : {};
    if (!caps.torch) { C.torch = false; return camLabels(); }
    try { await track.applyConstraints({ advanced: [{ torch: on }] }); C.torch = on; } catch (_) { C.torch = false; }
    camLabels();
  }

  function showShot(blob) {
    if (C.shotUrl) URL.revokeObjectURL(C.shotUrl);
    C.shotUrl = blob ? URL.createObjectURL(blob) : null;
    cam.shot.hidden = !blob;
    if (blob) cam.shot.src = C.shotUrl; else cam.shot.removeAttribute("src");
  }

  function capture() {
    if (!C.stream || C.busy || !cam.video.videoWidth) return;
    const w = cam.video.videoWidth, h = cam.video.videoHeight, k = Math.min(1, 1280 / Math.max(w, h));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(w * k); canvas.height = Math.round(h * k);
    canvas.getContext("2d").drawImage(cam.video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (!blob || !C.open) return;
      C.blob = blob;
      stopStream(); // review a still photo; the camera is off while reviewing
      showShot(blob);
      camStatus("toAnalyze");
      camButtons();
      cam.analyze.focus({ preventScroll: true });
    }, "image/jpeg", 0.9);
  }

  function onFile() {
    const f = cam.file.files && cam.file.files[0];
    cam.file.value = "";
    if (!f || !C.open) return;
    if (!/^image\/(jpeg|png|webp)$/.test(f.type)) { camStatus("failed", { bad: true, detail: "JPEG, PNG or WebP only." }); return; }
    stopStream();
    C.blob = f; showShot(f);
    camStatus("toAnalyze"); camButtons();
    cam.analyze.focus({ preventScroll: true });
  }

  function retake() {
    if (C.busy) return;
    C.blob = null; showShot(null); camButtons();
    startStream();
  }

  async function analyzePhoto() {
    if (!C.blob || C.busy) return; // one request at a time
    C.busy = true; C.abort = new AbortController();
    camStatus("analyzing"); camButtons();
    const fd = new FormData();
    fd.append("image", C.blob, C.blob.name || "photo.jpg");
    fd.append("language", S.lang);
    if (cam.note.value.trim()) fd.append("note", cam.note.value.trim());
    let r;
    try {
      const res = await fetch("/api/vision/analyze", { method: "POST", body: fd, signal: C.abort.signal });
      r = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof r.detail === "string" ? r.detail : `Server error (${res.status})`);
    } catch (e) {
      C.busy = false; C.abort = null;
      if (e.name === "AbortError") return; // cancelled by the user; closeCamera already ran
      camStatus("failed", { bad: true, detail: e instanceof TypeError ? "Network error. Check the connection." : e.message });
      return camButtons();
    }
    C.busy = false; C.abort = null;
    if (!r.ok) {
      camStatus("failed", { bad: true, detail: (r.error && r.error.message) || "" });
      return camButtons();
    }
    camStatus("done");
    closeCamera({ keepStatus: true });
    renderPhotoResult(r);
  }

  function closeCamera({ keepStatus = false } = {}) {
    if (C.abort) { C.abort.abort(); C.abort = null; }
    C.busy = false;
    stopStream();
    setFlash(false);
    C.blob = null; showShot(null);
    cam.note.value = "";
    if (!C.open) return;
    C.open = false;
    flip(false);
    if (!keepStatus) camStatus("cancelled");
    S.phase = S.lastTurn && S.prevPhase === "answered" ? "answered" : (S.langSelected ? "ready" : "select_language");
    if (!keepStatus) { if (S.langSelected) screenReady(); else screenMainMenu({ speak: false }); }
    setControls();
    cam.openBtn.focus({ preventScroll: true });
  }

  function renderPhotoResult(r) {
    const v = r.vision, a = r.answer, isEm = r.triage && r.triage.level === "emergency";
    S.phase = isEm ? "emergency" : "answered";
    S.lastTurn = { answer: a, voice: r.voice, triage: r.triage, question: { text: camT("heading") }, timings_ms: r.timings_ms };
    const head = isEm ? `<div class="inv">${pix("alert")}<span>! ${esc(camT("heading"))}</span></div>` : heading(camT("heading"));
    const displayText = cleanMock((a && a.text) ? a.text : (v ? v.observation : ""));
    lcd({ html: head, type: displayText, lang: a.lang, mode: isEm ? "emergency" : "response", assertive: isEm });

    setTimeout(() => {
      if (el.body && el.body.scrollHeight > el.body.clientHeight + 4) {
        const i18n = I18N[a.lang] || I18N[S.lang] || I18N["en-IN"];
        const hint = document.createElement("div");
        hint.className = "lcd-scroll-hint";
        hint.textContent = i18n.scrollDownHint || "Press ▼ to read more";
        el.body.appendChild(hint);
        updateArrows();
      }
    }, 50);

    if (isEm) { flashAmber(); sfx.alert(); } else sfx.blip();
    softkeysForState(); setControls();

    const cardEl = photoElement(r);
    el.convoEmpty.hidden = true;
    el.turns.prepend(cardEl);

    if (r.voice && r.voice.audio_url) {
      playVoice(r.voice, {
        onBlocked: () => {
          showAutoplayPrompt(r.voice, a.lang || S.lang, cardEl);
        }
      });
    }
  }

  function photoElement(r) {
    const li = document.createElement("li");
    li.className = "turn photo";
    const v = r.vision, a = r.answer, lvl = (r.triage && r.triage.level) || "none";
    const list = (items) => items && items.length ? `<ul class="photo-list" lang="${langAttr(a.lang)}">${items.map((x) => `<li>${esc(cleanMock(x))}</li>`).join("")}</ul>` : "";
    const flagText = { none: "Photo check: no urgent signs reported by the AI.", urgent: "Photo check: see a health worker within a day.",
      emergency: "Possible emergency. Call 112 now." }[lvl] || "";
    li.innerHTML = `
      <p class="turn-time" style="margin:0">${timeStamp()} · ${esc(langCode(S.lang))} · PHOTO</p>
      <div class="flag ${lvl}"><b>${esc(flagText)}</b>${r.triage && r.triage.source ? `<br><small>Source: ${r.triage.source === "rules" ? "safety rules" : "AI photo check"}</small>` : ""}</div>
      ${v ? `
        <div><b>What the photo shows</b><p class="answer" lang="${langAttr(a.lang)}">${esc(cleanMock(v.observation))}</p></div>
        ${v.possible_explanations.length ? `<div><b>Possible explanations (not a diagnosis)</b>${list(v.possible_explanations)}</div>` : ""}
        ${v.recommended_next_steps.length ? `<div><b>What you can do</b>${list(v.recommended_next_steps)}</div>` : ""}
        ${v.follow_up_questions.length ? `<div><b>Questions</b>${list(v.follow_up_questions)}</div>` : ""}
        ${v.image_quality === "insufficient" ? '<p class="voice-note">The photo was not clear enough to assess. Try again in good light, closer.</p>' : ""}
        <p class="voice-note" lang="${langAttr(a.lang)}">${esc(cleanMock(v.disclaimer))}</p>` : `<p class="answer" lang="${langAttr(a.lang)}">${esc(cleanMock(a.text))}</p>`}
      ${a.language_note ? `<p class="voice-note">${esc(cleanMock(a.language_note))}</p>` : ""}
      ${r.voice && r.voice.note ? `<p class="voice-note">${esc(cleanMock(r.voice.note))}</p>` : ""}
      <p class="voice-note">${esc(r.privacy)}${a.model ? ` · ${esc(a.model)}` : ""}</p>
      <div class="answer-actions">
        ${r.voice && r.voice.audio_url ? '<button type="button" data-act="hear">Hear again</button>' : ""}
        ${r.offer_facilities ? '<button type="button" class="find-help" data-act="hospital">Find nearest hospital</button>' : ""}
      </div>`;
    const hear = li.querySelector('[data-act="hear"]');
    if (hear) {
      hear.onclick = () => {
        clearAutoplayPrompt();
        playVoice(r.voice);
      };
    }
    const hosp = li.querySelector('[data-act="hospital"]'); if (hosp) hosp.onclick = () => goLocation();
    return li;
  }


  cam.openBtn.onclick = () => openCamera();
  cam.flashBtn.onclick = () => setFlash(!C.flash);
  cam.capture.onclick = capture;
  cam.upload.onclick = () => { if (!C.busy) cam.file.click(); };
  cam.file.onchange = onFile;
  cam.switchBtn.onclick = () => { if (C.busy) return; C.facing = C.facing === "environment" ? "user" : "environment"; startStream(); };
  cam.retake.onclick = retake;
  cam.analyze.onclick = analyzePhoto;
  cam.cancel.onclick = () => closeCamera();
  // Never keep the camera running in the background; resume the preview when the tab returns.
  document.addEventListener("visibilitychange", () => {
    if (!C.open || C.busy) return;
    if (document.hidden) { stopStream(); camButtons(); }
    else if (!C.blob && !C.stream) startStream();
  });
  window.addEventListener("resize", () => C.open && positionCone());
  camLabels();

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
  el.facSearchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const q = el.facSearchInput.value.trim();
      if (q) submitFacilitiesSearch({ text: q, emergency: false });
    }
  });
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
