# Aarogya Saathi: Retro Keypad Phone Design Spec

## 1. Concept

**"The phone your grandmother already owns."**
The whole product promise is that health help works on a cheap keypad phone. So the UI *is* that phone: a chunky early-2000s candy-bar handset with a green-backlit monochrome LCD, rubbery keys and DTMF beeps. Judges understand the pitch before anyone speaks.

The retro look lives **on the handset only**. The panel around it (conversation log, care slip, languages) stays calm and readable, so the engineering is easy to inspect.

### Principles
1. **The phone is the hero.** One bold object, everything else is quiet.
2. **Authentic constraints.** The LCD shows only what a real feature phone could: monochrome, pixel text, a few lines, a scroll arrow. No gradients, photos or emoji on the screen.
3. **Readable first, retro second.** Pixel fonts for short Latin labels only. Health answers in Assamese/Hindi always use a proper script font (pixel fonts don't support Indic scripts).
4. **Every press answers back.** Key moves down, keypad backlight flickers, DTMF tone plays, screen updates.
5. **Inspired by, not a copy.** A generic retro handset of our own design. No Nokia name, logo, or exact 3310/1100 silhouette. The bezel says **SAATHI**.

---

## 2. Colour tokens

### Handset
| Token | Hex | Use |
|---|---|---|
| `--shell` | `#2E3A48` | Phone body (dark slate plastic) |
| `--shell-hi` | `#46566A` | Top-edge highlight, bezel rim |
| `--shell-lo` | `#1C242E` | Bottom shadow, seams |
| `--key` | `#DADFE4` | Rubber key face |
| `--key-ink` | `#1E2630` | Key numbers |
| `--key-sub` | `#5B6673` | T9 letters (abc, def…) |
| `--key-call` | `#3E9B4F` | Call / answer key |
| `--key-end` | `#C8372D` | End key |
| `--key-glow` | `#9FE07A` | Keypad backlight when pressed (subtle) |

### LCD
| Token | Hex | Use |
|---|---|---|
| `--lcd-bg` | `#C5D3A0` | Backlight on |
| `--lcd-bg-dim` | `#A9B88A` | Backlight off (idle after 10 s) |
| `--lcd-ink` | `#26331A` | Pixels |
| `--lcd-ghost` | `rgba(38, 51, 26, 0.08)` | Pixel-grid / unlit pixels |
| `--lcd-amber` | `#E8C468` | Emergency backlight flash |

### Page (around the phone)
| Token | Hex | Use |
|---|---|---|
| `--desk` | `#EDEBE4` | Page background (warm grey desk) |
| `--paper` | `#FBFAF6` | Panel / receipt paper |
| `--text` | `#1F2328` | Body text |
| `--muted` | `#5E6670` | Secondary text |
| `--rule` | `#D6D2C8` | Borders |
| `--alert` | `#B3202A` | Emergency / red flags only |
| `--ok` | `#2F7D45` | "No red flags" |

Red means **danger** everywhere. It is never decorative.

---

## 3. Typography

| Role | Font | Notes |
|---|---|---|
| LCD Latin text, status bar, menus | **VT323** (Google Fonts) | 22–26px. Never below 20px. |
| LCD Indic text (Assamese, Bengali, Manipuri) | **Noto Sans Bengali**, weight 600 | Rendered in `--lcd-ink` with a 1px pixel shadow to blend with the LCD |
| LCD Indic text (Hindi, Bodo, Nepali) | **Noto Sans Devanagari**, weight 600 | Same treatment |
| Bezel brand "SAATHI", key numbers | **Silkscreen** or **VT323** | Small caps-free, letter-spaced 0.08em |
| Page UI (panel, buttons, slip) | **IBM Plex Sans** + Noto Sans Bengali/Devanagari fallbacks | 16–18px body, 1.5 line-height |
| Care slip (receipt) | **IBM Plex Mono** | Receipt/dot-matrix feel, 14–15px |

```html
<link href="https://fonts.googleapis.com/css2?family=VT323&family=Silkscreen&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;600&family=Noto+Sans+Bengali:wght@500;600&family=Noto+Sans+Devanagari:wght@500;600&display=swap" rel="stylesheet">
```

---

## 4. Handset anatomy

```
        ┌───────────────────────────┐
        │         ▬▬▬▬▬▬            │  earpiece slot
        │          SAATHI           │  bezel brand
        │ ┌───────────────────────┐ │
        │ │ ▂▄▆█  AS        ▮▮▮▯  │ │  status bar: signal, lang, battery
        │ │───────────────────────│ │
        │ │ আপোনাৰ প্ৰশ্নটো কওক।     │ │  4–6 text lines
        │ │                       │ │
        │ │                     ▼ │ │  scroll arrow if more text
        │ │───────────────────────│ │
        │ │ Speak          Menu   │ │  softkey labels
        │ └───────────────────────┘ │
        │   ╭───╮   ╭─────╮  ╭───╮  │
        │   │ ⌐ │   │  ◆  │  │ C │  │  left soft · nav key · right soft
        │   ╰───╯   ╰─────╯  ╰───╯  │
        │  ╭─────╮         ╭─────╮  │
        │  │ CALL│         │ END │  │  green / red
        │  ╰─────╯         ╰─────╯  │
        │  ╭───╮ ╭───╮ ╭───╮        │
        │  │ 1 │ │ 2 │ │ 3 │        │
        │  │   │ │abc│ │def│        │  3×4 keypad, keys slightly
        │  ╰───╯ ╰───╯ ╰───╯        │  oval, gap 10px
        │   ... 4–9, *, 0, #        │
        │                           │
        │        · · mic · ·        │  mic holes at bottom
        └───────────────────────────┘
```

### Proportions (desktop)
- Phone: **300px wide × ~620px tall**, aspect ≈ 1 : 2.05
- Body radius: `48px 48px 64px 64px` (fatter at the bottom, like a candy-bar phone)
- LCD: 236 × 200px, radius 6px, recessed (inset shadow) inside a darker bezel
- Keys: 64 × 44px, radius `22px / 18px` (oval pill)
- Nav key: 96 × 48px, centre diamond `◆`

### Material effects (CSS only, no images)
- Shell: `linear-gradient(160deg, var(--shell-hi), var(--shell) 30%, var(--shell-lo))` plus inner highlight `inset 0 2px 0 rgba(255,255,255,.12)`
- Keys: `box-shadow: 0 3px 0 #9AA3AC` (depth). On press: `translateY(3px)`, shadow becomes `0 0 0`
- LCD: pixel grid via `repeating-linear-gradient` 3px cells using `--lcd-ghost`, plus `inset 0 3px 6px rgba(0,0,0,.25)`

---

## 5. Softkey mapping

Softkeys change per state, just like a real phone. Labels sit on the bottom line of the LCD.

| State | Left softkey | Nav ◆ | Right softkey | Keypad |
|---|---|---|---|---|
| Idle | — | — | Menu | Call key starts the call |
| Language menu | Select | ▲▼ move | Back | 1–7 pick, 8 "not listed" |
| Ready to ask | **Speak** (hold) | — | Type | 0 = menu |
| Confirming (read-back) | Yes | — | No | 1 yes, 2 no |
| Answer | Again | ▲▼ scroll | Menu | 1 ask, 2 repeat, 5 simpler, 3 language, 9 end |
| Emergency | Call 112 | ▲▼ scroll | Back | as Answer |
| Consent | Yes | — | No | 1 / 2 |
| Ended | — | — | — | Call key to start again |

---

## 6. LCD screens

All screens: status bar (signal bars, selected language code like `AS`, battery), a 1px rule, content, 1px rule, softkey labels.

**Idle**
```
▂▄▆█            ▮▮▮▯
──────────────────────
     AAROGYA
      SAATHI
   health line
      12:45
──────────────────────
               Menu
```

**Calling** (2 s, before the welcome plays): `Calling…` with three dots animating, and a small pixel handset icon.

**Language menu** (selected row inverted: `--lcd-ink` background, `--lcd-bg` text)
```
 Choose language
──────────────────────
█1 অসমীয়া          █
 2 बड़ो
 3 মৈতৈলোন্
 4 नेपाली          ▼
──────────────────────
Select          Back
```

**Listening**: an 8-bar pixel equaliser that bounces while the mic is held, with "Listening…" under it. A blinking `●REC` sits in the status bar.

**Read-back**
```
 I heard:
──────────────────────
 “মোৰ কালিৰ পৰা জ্বৰ
  হৈছে”
 1 = Yes   2 = No
──────────────────────
Yes               No
```

**Thinking**: a pixel hourglass that flips every 600ms.

**Answer**: answer text with a ▼ scroll arrow. The Nav key scrolls. Long answers auto-scroll one line every 2.5s while audio plays.

**Emergency**
- Backlight flashes amber (`--lcd-amber`) **3 times** then stays amber.
- Inverted header bar: `! EMERGENCY  112`
- Text: the emergency script and first-aid line.
- Left softkey becomes **Call 112**. In the simulator it shows "In a real phone, this dials 112." It never fakes a call.

**Crisis**: same layout as Emergency but a steady (non-flashing) backlight and a `Tele-MANAS 14416` header. It stays calm, not alarming.

**Call ended**
```
 Call ended
 00:02:41
──────────────────────
 Slip code
 ┌──────────┐
 │  F35342  │
 └──────────┘
 Show to ASHA
──────────────────────
```

**Backlight**: after 10s with no key press the LCD dims to `--lcd-bg-dim`. Any key wakes it.

---

## 7. Pixel icons

Draw as tiny inline SVGs on a 12×12 grid with `shape-rendering: crispEdges`. Only `--lcd-ink`.

| Icon | Used for |
|---|---|
| Signal bars (4 steps) | Status bar |
| Battery (3 segments) | Status bar |
| Handset | Calling, ended |
| Microphone | Listening |
| Hourglass | Thinking |
| ! in triangle | Emergency |
| Heart with plus | Brand/idle screen |
| Envelope | Slip ready |
| ▲ ▼ | Scroll |

---

## 8. Motion and sound

| Event | Visual | Sound |
|---|---|---|
| Key press | Key moves 3px down, keypad backlight glows for 150ms | DTMF tone (real frequencies, 140ms) |
| Call start | Screen backlight flicks on, "Calling…" dots | Two short ring-back beeps |
| Listening | Equaliser bars bounce | — |
| Answer arrives | Text types in line by line (30ms per character, max 1s total) | One soft "blip" |
| Emergency | Amber flash ×3 | Three short alert beeps |
| Call end | Screen shrinks to a line, then off (300ms) | End tone |

- **Only one** of these runs at a time.
- `prefers-reduced-motion`: no flashing, no type-in, no bouncing. Text appears instantly and the amber backlight is steady.
- Mute toggle silences tones and voice.

---

## 9. The panel beside the phone

The panel stays modern and readable on `--paper`, with three small retro nods:

1. **Conversation tab = "Call log."** Each turn is a card with a timestamp in VT323, the caller's words, the safety-check result, the answer, the card source and the latency waterfall. The waterfall uses chunky pixel blocks (each 4px wide) instead of a smooth bar.
2. **Care slip = thermal receipt.** Narrow (360px) paper strip in IBM Plex Mono with a jagged torn bottom edge (CSS `mask` with a zigzag), dashed separators and a big slip code. The Print button prints exactly this receipt.
3. **Languages tab = "Network coverage."** Each language row shows signal bars instead of text badges:
   - 4 bars: full voice
   - 2 bars: ready once API keys are added
   - 0 bars with "No service": unsupported

---

## 10. Layout

**Desktop (≥ 1024px)**
```
┌──────────────────────────────────────────────────────────┐
│ Aarogya Saathi           Demo mode: scripted answers…   │  slim header
├────────────────────────┬─────────────────────────────────┤
│                        │  Call log | Care slip | Network │
│      [ PHONE ]         │                                 │
│  (sticky, centred      │   turn cards…                   │
│   in left column)      │                                 │
│                        │                                 │
│  Type instead [_____]  │                                 │
│  Demo questions ○ ○ ○  │                                 │
└────────────────────────┴─────────────────────────────────┘
   left column 420px              right column fluid
```

**Tablet (640–1023px)**: same two columns, phone scaled to 0.9.

**Mobile (< 640px)**: phone first, full width minus 16px gutters, scaled so the whole handset fits the screen height. The panel follows below. No horizontal scroll.

The page background shows a faint desk texture (2% noise), with the phone casting a soft long shadow down-right as if lying on a table.

---

## 11. Accessibility

- LCD contrast `#26331A` on `#C5D3A0` is about **8.4 : 1** (dimmed backlight 6.3 : 1, amber emergency 8.0 : 1), all passing WCAG AA. Keep them.
- LCD text is never below 20px (VT323) or 17px (Noto Indic).
- Every key is a real `<button>` with an `aria-label` ("Key 5, simpler words").
- LCD is an `aria-live="polite"` region. Emergency uses `aria-live="assertive"`.
- Physical keyboard works: 0–9, `*`, `#`, Enter = Call, Escape = End, Space (hold) = Speak, arrows = scroll.
- Visible focus ring: 3px `--key-call` outline offset 3px on keys.
- Full answers are always in the panel in a normal font, so the LCD's pixel style never blocks reading.

---

## 12. CSS starter

```css
:root {
  --shell:#2E3A48; --shell-hi:#46566A; --shell-lo:#1C242E;
  --key:#DADFE4; --key-ink:#1E2630; --key-sub:#5B6673;
  --key-call:#3E9B4F; --key-end:#C8372D; --key-glow:#9FE07A;
  --lcd-bg:#C5D3A0; --lcd-bg-dim:#A9B88A; --lcd-ink:#26331A;
  --lcd-ghost:rgba(38,51,26,.08); --lcd-amber:#E8C468;
  --desk:#EDEBE4; --paper:#FBFAF6; --text:#1F2328; --muted:#5E6670;
  --rule:#D6D2C8; --alert:#B3202A; --ok:#2F7D45;
  --pixel:"VT323", monospace;
  --ui:"IBM Plex Sans", "Noto Sans Bengali", "Noto Sans Devanagari", sans-serif;
}

.phone {
  width: 300px; padding: 28px 26px 36px;
  border-radius: 48px 48px 64px 64px;
  background: linear-gradient(160deg, var(--shell-hi), var(--shell) 30%, var(--shell-lo));
  box-shadow: inset 0 2px 0 rgba(255,255,255,.12), 18px 24px 40px -18px rgba(0,0,0,.45);
}

.lcd {
  background:
    repeating-linear-gradient(0deg, var(--lcd-ghost) 0 1px, transparent 1px 3px),
    repeating-linear-gradient(90deg, var(--lcd-ghost) 0 1px, transparent 1px 3px),
    var(--lcd-bg);
  color: var(--lcd-ink);
  font: 24px/1.15 var(--pixel);
  border-radius: 6px;
  box-shadow: inset 0 3px 6px rgba(0,0,0,.25);
  transition: background-color .4s;
}
.lcd[data-backlight="off"] { --lcd-bg: var(--lcd-bg-dim); }
.lcd[data-mode="emergency"] { --lcd-bg: var(--lcd-amber); }
.lcd :lang(as), .lcd :lang(bn), .lcd :lang(mni) { font: 600 18px/1.4 "Noto Sans Bengali", sans-serif; text-shadow: 1px 0 0 var(--lcd-ghost); }
.lcd :lang(hi), .lcd :lang(brx), .lcd :lang(ne) { font: 600 18px/1.4 "Noto Sans Devanagari", sans-serif; }
.lcd .selected { background: var(--lcd-ink); color: var(--lcd-bg); }

.key {
  height: 44px; border: 0; border-radius: 22px / 18px;
  background: var(--key); color: var(--key-ink);
  font: 26px/1 var(--pixel);
  box-shadow: 0 3px 0 #9AA3AC;
  transition: transform .05s, box-shadow .05s;
}
.key small { display: block; font: 11px/1 var(--ui); color: var(--key-sub); }
.key:active, .key.pressed { transform: translateY(3px); box-shadow: 0 0 0 #9AA3AC; }
.keypad.lit .key { box-shadow: 0 3px 0 #9AA3AC, 0 0 10px var(--key-glow); }
.key.call { background: var(--key-call); color: #fff; }
.key.end  { background: var(--key-end);  color: #fff; }

@keyframes amber-flash { 0%,100% { background-color: var(--lcd-bg); } 50% { background-color: var(--lcd-amber); } }
.lcd.flash { animation: amber-flash .35s steps(1) 3; }

@media (prefers-reduced-motion: reduce) {
  .lcd.flash, .eq-bar, .typing { animation: none !important; }
}
```

---

## 13. Do and don't

| Do | Don't |
|---|---|
| Keep the LCD monochrome | Add colour, gradients or emoji inside the screen |
| Use pixel fonts for short Latin labels | Use pixel fonts for Assamese/Hindi or long answers |
| Make every key press give feedback | Animate things nobody triggered (except the emergency flash) |
| Use red only for danger | Use red for decoration or branding |
| Brand the handset "SAATHI" | Use the Nokia name, logo or an exact 3310/1100 outline |
| Show "In a real phone this dials 112" | Pretend the simulator made a real call |

---

## 14. Implementation checklist

- [ ] Fonts: swap Anek for VT323, Silkscreen, IBM Plex Sans/Mono and Noto Sans Bengali/Devanagari in `frontend/index.html`
- [ ] Rebuild the handset markup: bezel brand, status bar, softkey labels row, nav key, mic holes
- [ ] Replace `frontend/styles.css` tokens with section 2, and add the phone/LCD/key styles from section 12
- [ ] In `frontend/app.js`: add softkey state map (section 5), backlight timeout, language-menu list with inverted selection, ▲▼ scrolling, equaliser and hourglass, amber emergency flash, keyboard shortcuts (section 11)
- [ ] Pixel icon SVGs (section 7)
- [ ] Call log, thermal-receipt slip and signal-bar network table (section 9)
- [ ] Test at 390px, 768px and 1360px. Check reduced motion and keyboard-only use.
