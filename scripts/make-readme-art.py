#!/usr/bin/env python3
"""Draws the README graphics (docs/*.svg). Run:  python3 scripts/make-readme-art.py
Pure SVG with built-in animation, so they play inside GitHub's README. No images, no fonts to load."""
import html
import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs"
BG, PANEL, LINE = "#040b0c", "#071a1a", "#0f3d3a"
C1, C2, DEEP = "#14e0c0", "#7dfff0", "#0a3a35"
AMB, RED, ICE = "#ffd24a", "#ff4d5e", "#9fd8ff"
TXT, DIM = "#d8fff8", "#6fa9a2"
SANS = "'Segoe UI','Helvetica Neue',Arial,sans-serif"
MONO = "'Cascadia Code','Consolas','Courier New',monospace"


def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{title}">'
            f'<title>{title}</title><defs>'
            f'<radialGradient id="bg" cx="50%" cy="45%" r="75%"><stop offset="0" stop-color="#08262a"/><stop offset="1" stop-color="{BG}"/></radialGradient>'
            f'<radialGradient id="core" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#fff"/><stop offset=".35" stop-color="{C2}"/><stop offset="1" stop-color="{C1}" stop-opacity="0"/></radialGradient>'
            f'<radialGradient id="halo" cx="50%" cy="50%" r="50%"><stop offset=".55" stop-color="{C1}" stop-opacity=".0"/><stop offset=".8" stop-color="{C1}" stop-opacity=".22"/><stop offset="1" stop-color="{C1}" stop-opacity="0"/></radialGradient>'
            f'<linearGradient id="bar" x1="0" x2="1"><stop offset="0" stop-color="{C1}"/><stop offset="1" stop-color="{C2}"/></linearGradient>'
            f'<pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="{C1}" stroke-opacity=".07"/></pattern>'
            f'<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
            f'<filter id="glow2" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="7" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
            f'</defs>'
            f'<rect width="{w}" height="{h}" rx="12" fill="url(#bg)"/><rect width="{w}" height="{h}" rx="12" fill="url(#grid)"/>'
            f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="12" fill="none" stroke="{C1}" stroke-opacity=".35"/>'
            f'{body}</svg>')


def t(x, y, s, size=14, fill=TXT, weight=400, anchor="start", font=SANS, ls=0, extra=""):
    s = s.replace("&", "&amp;").replace("<", "&lt;")
    return (f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}" letter-spacing="{ls}" {extra}>{s}</text>')


def brackets(x, y, w, h, c=C1, n=14, op=.9):
    return (f'<g stroke="{c}" stroke-width="2" fill="none" opacity="{op}">'
            f'<path d="M{x},{y+n}V{y}H{x+n}"/><path d="M{x+w-n},{y}H{x+w}V{y+n}"/>'
            f'<path d="M{x},{y+h-n}V{y+h}H{x+n}"/><path d="M{x+w-n},{y+h}H{x+w}V{y+h-n}"/></g>')


def spin(cx, cy, dur, rev=False):
    a, b = (360, 0) if rev else (0, 360)
    return f'<animateTransform attributeName="transform" type="rotate" from="{a} {cx} {cy}" to="{b} {cx} {cy}" dur="{dur}s" repeatCount="indefinite"/>'


def pulse(attr, vals, dur, extra=""):
    return f'<animate attributeName="{attr}" values="{vals}" dur="{dur}s" repeatCount="indefinite" {extra}/>'


def orb(cx, cy, r, seed=7, glyphs=True):
    rnd = random.Random(seed)
    o = [f'<circle cx="{cx}" cy="{cy}" r="{r*1.35}" fill="url(#halo)">{pulse("r", f"{r*1.3};{r*1.42};{r*1.3}", 4)}</circle>']
    # longitude ellipses, slowly turning
    for i, (rot, dur) in enumerate([(0, 26), (60, 34), (120, 30)]):
        o.append(f'<g transform="rotate({rot} {cx} {cy})"><g>{spin(cx, cy, dur, rev=i % 2 == 1)}'
                 f'<ellipse cx="{cx}" cy="{cy}" rx="{r*.34}" ry="{r}" fill="none" stroke="{C1}" stroke-width="1.4" stroke-opacity=".75"/>'
                 f'<ellipse cx="{cx}" cy="{cy}" rx="{r*.7}" ry="{r}" fill="none" stroke="{C2}" stroke-width="1" stroke-opacity=".45"/></g></g>')
    # latitude lines
    for k in range(-3, 4):
        y = cy + k * r * .25
        rx = r * math.sqrt(max(0, 1 - (k * .25) ** 2))
        o.append(f'<ellipse cx="{cx}" cy="{y}" rx="{rx}" ry="{rx*.16}" fill="none" stroke="{C1}" stroke-opacity=".38"/>')
    # outer glowing rings
    o.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{C2}" stroke-width="3" filter="url(#glow)" opacity=".95"/>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="{r*1.12}" fill="none" stroke="{C1}" stroke-width="1.5" stroke-dasharray="3 9" opacity=".8">{spin(cx, cy, 40)}</circle>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="{r*.82}" fill="none" stroke="{C1}" stroke-width="2" stroke-dasharray="46 20 6 20" opacity=".7">{spin(cx, cy, 18, True)}</circle>')
    # code glyphs
    if glyphs:
        chars = "01{}[]<>=/#$%&*+-;:abcdef"
        for _ in range(46):
            a, d = rnd.uniform(0, 6.283), r * math.sqrt(rnd.uniform(.05, .92))
            x, y = cx + d * math.cos(a), cy + d * math.sin(a) * .98
            col = AMB if rnd.random() < .5 else C2
            op = rnd.uniform(.35, .9)
            dur = rnd.uniform(2, 5)
            o.append(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{MONO}" font-size="{rnd.choice([8, 9, 10])}" fill="{col}" opacity="{op:.2f}">'
                     f'{html.escape(rnd.choice(chars) + rnd.choice(chars))}{pulse("opacity", f"{op:.2f};{op*.25:.2f};{op:.2f}", f"{dur:.1f}")}</text>')
    # core
    o.append(f'<circle cx="{cx}" cy="{cy}" r="{r*.3}" fill="url(#core)" filter="url(#glow2)">{pulse("r", f"{r*.27};{r*.34};{r*.27}", 2.4)}</circle>')
    # orbiting sparks
    for rad, dur, col in [(r * .55, 6, AMB), (r * .9, 11, C2), (r * 1.25, 16, C1)]:
        o.append(f'<g>{spin(cx, cy, dur)}<circle cx="{cx+rad}" cy="{cy}" r="3.2" fill="{col}" filter="url(#glow)"/></g>')
    return "".join(o)


def typed(lines, x, y, size, fill, dur=12, font=SANS, weight=400, ls=0):
    """Lines that fade in one after another and loop."""
    n = len(lines)
    out = []
    for i, s in enumerate(lines):
        a, b = i / n, (i + 1) / n
        kt = f"0;{a:.3f};{a+.03:.3f};{b-.03:.3f};{b:.3f};1"
        out.append(t(x, y, s, size, fill, weight, font=font, ls=ls,
                     extra='opacity="0"').replace("</text>", f'<animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="{kt}" dur="{dur}s" repeatCount="indefinite"/></text>'))
    return "".join(out)


# ---------------------------------------------------------------- 1. hero
def hero():
    W, H = 960, 380
    b = [brackets(14, 14, W - 28, H - 28)]
    b.append(f'<rect x="0" y="0" width="{W}" height="3" fill="{C2}" opacity=".5"><animate attributeName="y" values="0;{H};0" dur="9s" repeatCount="indefinite"/></rect>')
    b.append(t(52, 62, "// STARK-GRADE PERSONAL AI · v17", 12, C1, 500, font=MONO, ls=3))
    b.append(t(48, 150, "N E M I I I", 64, TXT, 800, ls=4, extra='filter="url(#glow)"'))
    b.append(f'<rect x="52" y="168" width="360" height="3" fill="url(#bar)"><animate attributeName="width" values="0;360;360;0" keyTimes="0;.15;.9;1" dur="9s" repeatCount="indefinite"/></rect>')
    b.append(typed(["Say it. She does it.", "She draws. She composes. She speaks.", "Offline. On your SSD. On your orb.", "Then she tells you what really happened."],
                   52, 214, 22, C2, 12, weight=500))
    b.append(t(52, 246, "Voice-first AI operator for your Windows PC", 14, DIM))
    b.append(t(52, 266, "FastAPI · Next.js · Three.js · Ollama · ComfyUI · Whisper · Kokoro", 12, DIM, font=MONO))
    chips = [("67", "ACTIONS", C1), ("4", "MODES", AMB), ("100%", "OFFLINE STUDIO", C2), ("6 GB", "GPU READY", RED)]
    x = 52
    for big, small, col in chips:
        w = 146
        b.append(f'<rect x="{x}" y="296" width="{w}" height="56" rx="6" fill="{PANEL}" stroke="{col}" stroke-opacity=".7"/>'
                 f'<rect x="{x}" y="296" width="4" height="56" fill="{col}"/>')
        b.append(t(x + 16, 326, big, 24, col, 700))
        b.append(t(x + 16, 343, small, 10, DIM, 600, font=MONO, ls=2))
        x += w + 12
    b.append(orb(722, 190, 128))
    b.append(t(722, 352, "ONLINE", 11, C2, 600, "middle", MONO, 4, 'filter="url(#glow)"'))
    b.append(f'<circle cx="676" cy="348" r="3.5" fill="{C2}">{pulse("opacity", "1;.2;1", 1.4)}</circle>')
    return svg(W, H, "".join(b), "NEMIII: a voice-first AI operator for your Windows PC")


# ---------------------------------------------------------------- 2. flow
def flow():
    W, H = 960, 430
    b = [t(40, 44, "HOW A SENTENCE BECOMES AN ACTION", 13, C1, 600, font=MONO, ls=3)]

    def box(x, y, w, h, title, sub, col=C1, glow=False):
        return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{PANEL}" stroke="{col}" stroke-opacity=".85"' + (' filter="url(#glow)"' if glow else "") + '/>'
                f'<rect x="{x}" y="{y}" width="{w}" height="4" rx="2" fill="{col}"/>'
                + t(x + w / 2, y + h / 2 - 2, title, 15, TXT, 700, "middle")
                + t(x + w / 2, y + h / 2 + 17, sub, 11, DIM, 400, "middle"))

    def link(x1, y1, x2, y2, col=C2, dur=2.2):
        return (f'<path d="M{x1},{y1}L{x2},{y2}" stroke="{col}" stroke-opacity=".3" stroke-width="2" fill="none"/>'
                f'<path d="M{x1},{y1}L{x2},{y2}" stroke="{col}" stroke-width="2.4" fill="none" stroke-dasharray="6 14">'
                f'<animate attributeName="stroke-dashoffset" from="40" to="0" dur="{dur}s" repeatCount="indefinite"/></path>')

    b += [link(150, 150, 205, 150), link(335, 150, 390, 150), link(520, 150, 575, 150), link(705, 150, 760, 150)]
    b += [box(20, 110, 130, 80, "YOU", "voice · typing · hands", AMB),
          box(205, 110, 130, 80, "BROWSER", "orb UI · localhost", C1),
          box(390, 110, 130, 80, "BACKEND", "FastAPI in WSL", C1, True),
          box(575, 110, 130, 80, "BRAIN", "Qwen · Llama · Groq", C2),
          box(760, 110, 180, 80, "SAFETY GATE", "whitelist · asks first", RED, True)]
    # fast path
    b.append(f'<path d="M455,110V78H640V110" stroke="{AMB}" stroke-width="1.6" fill="none" stroke-dasharray="4 6"><animate attributeName="stroke-dashoffset" from="20" to="0" dur="1.4s" repeatCount="indefinite"/></path>')
    b.append(t(548, 70, "fast path: yes · no · mode · theme · briefing (no AI needed)", 11, AMB, 500, "middle"))
    # fan out
    for x2 in (150, 330, 510, 690, 860):
        b.append(link(850, 190, x2, 262, RED, 2.6))
    outs = [(40, "PC CONTROL", "apps · media · windows", C1), (222, "LIVE INTEL", "news · weather · mail", C1),
            (404, "SECURITY", "ports · links · CVEs", C1), (586, "STUDIO", "image · music · voice", AMB), (768, "SMART HOME", "lights · fans · scenes", C1)]
    for x, ti, su, col in outs:
        b.append(box(x, 262, 170, 74, ti, su, col))
    b.append(f'<rect x="40" y="366" width="898" height="44" rx="8" fill="{PANEL}" stroke="{C2}" stroke-opacity=".5"/>')
    b.append(t(489, 393, "ACTIVITY LOG  ·  every action, its result and whether it really worked  ·  shown in the ACTIVITY tab", 13, C2, 500, "middle"))
    for x in (125, 307, 489, 671, 853):
        b.append(f'<path d="M{x},336V366" stroke="{C2}" stroke-opacity=".5" stroke-width="1.5" stroke-dasharray="3 5"/>')
    return svg(W, H, "".join(b), "How a sentence becomes an action in NEMIII")


# ---------------------------------------------------------------- 3. systems
def systems():
    W, H = 960, 470
    b = [t(40, 44, "SUBSYSTEMS", 13, C1, 600, font=MONO, ls=3), t(920, 44, "67 whitelisted actions", 12, DIM, 400, "end", MONO)]
    cards = [
        ("01", "PC CONTROL", "Open or close apps and games, media keys, volume, screenshots, lock, type for you.", C1, "M6 18h20M10 24h12M16 6v8M8 8l16 0"),
        ("02", "LIVE INTEL", "News, weather, Wikipedia, currency, GitHub, Gmail (read-only), PC vitals.", C2, "M4 20l6-8 6 5 6-10 6 6"),
        ("03", "DAILY OPS", "Reminders, timers, alarms, morning briefing, memory, find and read your files.", AMB, "M16 6v10l6 4M16 2a14 14 0 1 0 0 28 14 14 0 0 0 0-28"),
        ("04", "THE STUDIO", "Draw, compose, speak and transcribe, offline, stored on your SSD.", RED, "M4 24l8-12 6 8 4-5 6 9z"),
        ("05", "SECURITY", "Own-machine port scans, link checks, LAN devices, CISA exploited CVEs, honeypot.", C1, "M16 3l11 4v8c0 7-5 12-11 14C10 27 5 22 5 15V7z"),
        ("06", "SMART HOME", "Lights, switches, fans and scenes through Home Assistant. Never locks.", C2, "M4 16L16 5l12 11M8 14v13h16V14"),
        ("07", "SENSES + HANDS", "Camera and screen vision. Pinch, swipe, fist, two and three fingers.", AMB, "M3 16c4-8 22-8 26 0-4 8-22 8-26 0zM16 12a4 4 0 1 0 0 8 4 4 0 0 0 0-8"),
        ("08", "VOICE", "Natural offline voice, four personalities, pause and stop, never reads symbols.", RED, "M16 4a4 4 0 0 1 4 4v8a4 4 0 0 1-8 0V8a4 4 0 0 1 4-4zM8 15a8 8 0 0 0 16 0M16 23v5"),
    ]
    for i, (num, ti, body, col, icon) in enumerate(cards):
        x, y = 40 + (i % 4) * 224, 70 + (i // 4) * 190
        dly = i * .35
        b.append(f'<g><animateTransform attributeName="transform" type="translate" values="0 0;0 -5;0 0" dur="5s" begin="{dly}s" repeatCount="indefinite" calcMode="spline" keySplines=".4 0 .6 1;.4 0 .6 1" keyTimes="0;.5;1"/>'
                 f'<rect x="{x}" y="{y}" width="208" height="170" rx="8" fill="{PANEL}" stroke="{col}" stroke-opacity=".75"/>'
                 f'<rect x="{x}" y="{y}" width="208" height="4" rx="2" fill="{col}"/>'
                 f'<g transform="translate({x+16},{y+22})"><path d="{icon}" fill="none" stroke="{col}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow)"/></g>'
                 + t(x + 192, y + 36, num, 11, DIM, 400, "end", MONO)
                 + t(x + 16, y + 78, ti, 15, TXT, 700, ls=1))
        words, line, ln = body.split(), "", 0
        for w_ in words:
            if len(line + " " + w_) > 30:
                b.append(t(x + 16, y + 102 + ln * 17, line.strip(), 12, DIM))
                line, ln = "", ln + 1
            line += " " + w_
        b.append(t(x + 16, y + 102 + ln * 17, line.strip(), 12, DIM))
        b.append("</g>")
    return svg(W, H, "".join(b), "NEMIII subsystems")


# ---------------------------------------------------------------- 4. modes
def modes():
    W, H = 960, 300
    b = [t(40, 44, "PERSONALITY MODES", 13, C1, 600, font=MONO, ls=3),
         t(920, 44, '"Switch to Jarvis"  ·  or just call her by name', 12, DIM, 400, "end", MONO)]
    ms = [("NEMIII", "calm · warm · attentive", '"Done. I opened Steam."', C1),
          ("JARVIS", "formal · courteous · dry wit", '"Right away, boss. Steam is up."', AMB),
          ("FRIDAY", "tactical · direct · fast", '"Steam open. Anything else?"', RED),
          ("EDITH", "literal · neutral · no chatter", '"Done."', ICE)]
    for i, (n, tag, quote, col) in enumerate(ms):
        x = 40 + i * 224
        b.append(f'<g><animateTransform attributeName="transform" type="translate" values="0 0;0 -6;0 0" dur="4.6s" begin="{i*.4}s" repeatCount="indefinite" calcMode="spline" keySplines=".4 0 .6 1;.4 0 .6 1" keyTimes="0;.5;1"/>'
                 f'<rect x="{x}" y="70" width="208" height="200" rx="8" fill="{PANEL}" stroke="{col}" stroke-opacity=".85"/><rect x="{x}" y="70" width="208" height="5" rx="2" fill="{col}"/>')
        b.append(f'<circle cx="{x+104}" cy="140" r="32" fill="none" stroke="{col}" stroke-width="2" filter="url(#glow)"/>'
                 f'<circle cx="{x+104}" cy="140" r="21" fill="none" stroke="{col}" stroke-dasharray="4 6" opacity=".8">{spin(x+104, 140, 10 + i * 3, i % 2 == 1)}</circle>'
                 f'<circle cx="{x+104}" cy="140" r="8" fill="{col}">{pulse("r", "6;10;6", 2 + i * .3)}</circle>')
        # voice wave
        wave = "".join(f'<rect x="{x+60+j*8}" y="196" width="4" height="12" fill="{col}" opacity=".85"><animate attributeName="height" values="4;{10+(j*7)%18};4" dur="{1+((j*3)%5)*.2:.1f}s" repeatCount="indefinite"/><animate attributeName="y" values="202;{202-(10+(j*7)%18)/2};202" dur="{1+((j*3)%5)*.2:.1f}s" repeatCount="indefinite"/></rect>' for j in range(11))
        b.append(wave)
        b.append(t(x + 104, 100, n, 17, col, 800, "middle", ls=3))
        b.append(t(x + 104, 232, tag, 11, DIM, 400, "middle"))
        b.append(t(x + 104, 254, quote, 12, TXT, 500, "middle", extra='font-style="italic"'))
        b.append("</g>")
    return svg(W, H, "".join(b), "Four personality modes")


# ---------------------------------------------------------------- 5. studio
def studio():
    W, H = 960, 470
    b = [t(40, 44, "THE STUDIO  ·  OFFLINE  ·  ON YOUR EXTERNAL SSD", 13, C1, 600, font=MONO, ls=3)]
    b.append(f'<rect x="40" y="70" width="230" height="64" rx="8" fill="{PANEL}" stroke="{AMB}"/>' + t(155, 98, '"Draw a neon city', 14, TXT, 600, "middle") + t(155, 118, 'at night"', 14, TXT, 600, "middle"))
    ms = [("DRAW", "SDXL Turbo · ComfyUI", "6.9 GB", AMB, "image"), ("COMPOSE", "MusicGen small", "2.4 GB", C2, "music"),
          ("SPEAK", "Kokoro 82M voice", "0.3 GB", C1, "voice"), ("HEAR", "Whisper small", "0.5 GB", ICE, "text"), ("THINK", "Qwen 2.5 7B · Moondream", "4.7 GB", RED, "brain")]
    for i, (n, m, sz, col, _) in enumerate(ms):
        y = 70 + i * 58
        b.append(f'<path d="M270,102C330,102 330,{y+26} 380,{y+26}" stroke="{col}" stroke-opacity=".35" stroke-width="2" fill="none"/>'
                 f'<path d="M270,102C330,102 330,{y+26} 380,{y+26}" stroke="{col}" stroke-width="2.4" fill="none" stroke-dasharray="5 12"><animate attributeName="stroke-dashoffset" from="34" to="0" dur="{2+i*.3:.1f}s" repeatCount="indefinite"/></path>'
                 f'<rect x="380" y="{y}" width="250" height="52" rx="7" fill="{PANEL}" stroke="{col}" stroke-opacity=".85"/><rect x="380" y="{y}" width="4" height="52" fill="{col}"/>'
                 + t(398, y + 22, n, 14, col, 800, ls=2) + t(398, y + 40, m, 11, DIM) + t(618, y + 31, sz, 12, TXT, 600, "end", MONO))
        b.append(f'<path d="M630,{y+26}C690,{y+26} 690,235 740,235" stroke="{col}" stroke-opacity=".3" stroke-width="2" fill="none"/>'
                 f'<path d="M630,{y+26}C690,{y+26} 690,235 740,235" stroke="{col}" stroke-width="2.4" fill="none" stroke-dasharray="5 12"><animate attributeName="stroke-dashoffset" from="34" to="0" dur="{2.4+i*.2:.1f}s" repeatCount="indefinite"/></path>')
    # SSD
    b.append(f'<g filter="url(#glow)"><rect x="740" y="190" width="180" height="90" rx="10" fill="{PANEL}" stroke="{C2}" stroke-width="2"/></g>'
             f'<rect x="756" y="206" width="148" height="10" rx="3" fill="{DEEP}"/><rect x="756" y="206" width="90" height="10" rx="3" fill="url(#bar)"><animate attributeName="width" values="30;120;30" dur="7s" repeatCount="indefinite"/></rect>'
             + t(830, 244, "EXTERNAL SSD", 15, TXT, 800, "middle", ls=2) + t(830, 264, "models · outputs · tools", 11, DIM, 400, "middle"))
    b.append(f'<circle cx="896" cy="211" r="3" fill="{C2}">{pulse("opacity", "1;.2;1", 1.2)}</circle>')
    b.append(f'<path d="M830,280V348" stroke="{C2}" stroke-width="2.4" stroke-dasharray="5 9"><animate attributeName="stroke-dashoffset" from="28" to="0" dur="1.6s" repeatCount="indefinite"/></path>')
    # progress + viewer
    b.append(f'<rect x="40" y="386" width="880" height="62" rx="8" fill="{PANEL}" stroke="{C1}" stroke-opacity=".6"/>')
    b.append(t(60, 410, "MAKING · A PICTURE OF NEON CITY AT NIGHT", 12, C2, 600, font=MONO, ls=1))
    b.append(f'<rect x="60" y="420" width="520" height="10" rx="2" fill="{DEEP}"/><rect x="60" y="420" width="0" height="10" rx="2" fill="url(#bar)"><animate attributeName="width" values="0;130;260;390;520;520" keyTimes="0;.18;.4;.62;.85;1" dur="8s" repeatCount="indefinite"/></rect>')
    b.append(t(60, 441, "real steps and a real percentage, then the viewer opens", 10, DIM, font=MONO))
    for j in range(4):
        col = [C1, AMB, RED, ICE][j]
        b.append(f'<rect x="{700+j*52}" y="398" width="42" height="38" rx="4" fill="{col}" fill-opacity=".25" stroke="{col}"/>'
                 f'<path d="M{704+j*52},432l12-14 8 8 8-10 6 8" stroke="{col}" fill="none" stroke-width="1.6"/>')
    return svg(W, H, "".join(b), "The NEMIII studio: models on an external SSD")


# ---------------------------------------------------------------- 6. ui preview
def ui():
    W, H = 960, 560
    b = [brackets(10, 10, W - 20, H - 20, op=.6)]
    b.append(t(30, 40, "N · E · M · I · I · I", 16, C2, 600, ls=5))
    b.append(t(30, 58, "VOICE-CONTROLLED PC ASSISTANT", 9, DIM, 400, font=MONO, ls=2))
    b.append(t(30, 74, "BRAIN: LOCAL  ·  MIC: ON  ·  PC: LINKED", 9, DIM, 400, font=MONO, ls=1))
    b.append(t(30, 90, "MODE: JARVIS  ·  THEME: PEACOCK", 9, DIM, 400, font=MONO, ls=1))
    # progress card
    b.append(f'<rect x="270" y="26" width="360" height="62" rx="4" fill="{DEEP}" fill-opacity=".9" stroke="{C1}"/>')
    b.append(t(284, 46, "MAKING · A PICTURE OF NEON CITY AT NIGHT", 9, C2, 600, font=MONO, ls=1) + t(616, 46, "55%", 9, C2, 600, "end", MONO))
    b.append(f'<rect x="284" y="54" width="332" height="7" fill="{BG}" stroke="{C1}" stroke-opacity=".5"/><rect x="284" y="54" width="120" height="7" fill="url(#bar)"><animate attributeName="width" values="40;332;40" dur="9s" repeatCount="indefinite"/></rect>')
    b.append(t(284, 78, "drawing, step 2 of 4 · 12s", 9, DIM, 400, font=MONO))
    # dashboard
    b.append(f'<rect x="690" y="22" width="248" height="62" rx="4" fill="{PANEL}" stroke="{C1}" stroke-opacity=".5"/>' + t(704, 42, "AROUND YOU", 8, DIM, 400, font=MONO, ls=2) + t(704, 62, "Chennai", 15, TXT, 600) + t(704, 78, "32°C · humid", 10, DIM))
    # orb
    b.append(orb(450, 290, 150, seed=3))
    # viewer
    b.append(f'<g><rect x="262" y="212" width="376" height="190" rx="4" fill="{DEEP}" fill-opacity=".96" stroke="{C1}"/>')
    b.append(t(276, 232, "CREATIONS", 9, C2, 600, font=MONO, ls=2))
    for k, lab in enumerate(["◀ OLDER", "NEWER ▶", "OPEN IN WINDOWS", "×"]):
        w_ = [58, 58, 100, 20][k]
        xx = [380, 442, 504, 608][k]
        b.append(f'<rect x="{xx}" y="220" width="{w_}" height="18" fill="{BG}" stroke="{C1}" stroke-opacity=".7"/>' + t(xx + w_ / 2, 233, lab, 8, C1, 500, "middle", MONO))
    b.append(f'<defs><linearGradient id="art" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff2bd6"/><stop offset=".5" stop-color="#2b6bff"/><stop offset="1" stop-color="{C2}"/></linearGradient></defs>')
    b.append(f'<rect x="276" y="248" width="348" height="108" fill="url(#art)" opacity=".85"/>')
    b.append("".join(f'<rect x="{282+i*26}" y="{356-h}" width="18" height="{h}" fill="#05060f" opacity=".75"/><rect x="{286+i*26}" y="{356-h+10}" width="3" height="3" fill="{AMB}"/>'
                      for i, h in enumerate([40, 70, 52, 90, 62, 80, 36, 66, 48, 84, 56, 72, 44])))
    b.append(t(276, 372, "PICTURE · 20261101-neon-city-at-night.png", 9, DIM, 400, font=MONO))
    for k in range(6):
        col = ["#ff2bd6", C1, AMB, "#2b6bff", RED, C2][k]
        b.append(f'<rect x="{276+k*44}" y="380" width="38" height="16" fill="{col}" fill-opacity=".5" stroke="{col}"/>')
    b.append("</g>")
    # caption + talkbar
    b.append(t(450, 450, "Right away, boss. Drawing it now.", 15, "#fff", 500, "middle"))
    for xx, lab in [(386, "PAUSE"), (466, "STOP")]:
        b.append(f'<rect x="{xx}" y="464" width="72" height="26" fill="{DEEP}" stroke="{C1}"/>' + t(xx + 36, 481, lab, 10, C1, 600, "middle", MONO, 3))
    # chat bar
    b.append(f'<rect x="270" y="512" width="340" height="26" fill="{BG}" stroke="{C1}"/>' + t(282, 529, "Type to Nemiii and press Enter…", 10, DIM, 400, font=MONO))
    # button grid
    labs = ["TALK", "WAKE ON", "HANDS OFF", "COME HERE", "LOOK", "SCREEN", "THEME", "PANEL", "MINI ORB", "CREATIONS", "MODE", "SOUND ON", "VOICE ON", "NATURAL"]
    for i, lab in enumerate(labs):
        x, y = 724 + (i % 2) * 108, 214 + (i // 2) * 36
        on = lab in ("WAKE ON", "CREATIONS", "SOUND ON", "VOICE ON", "NATURAL")
        b.append(f'<rect x="{x}" y="{y}" width="100" height="28" fill="{C1 if on else BG}" fill-opacity="{.2 if on else 1}" stroke="{C1}" stroke-opacity=".8"/>' + t(x + 50, y + 18, lab, 9, C2 if on else C1, 500, "middle", MONO, 1.5))
    b.append(t(480, 548, "illustration of the NEMIII screen", 8, DIM, 400, "middle", MONO))
    return svg(W, H, "".join(b), "Illustration of the NEMIII screen")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for name, fn in [("hero", hero), ("flow", flow), ("systems", systems), ("modes", modes), ("studio", studio), ("ui", ui)]:
        (OUT / f"{name}.svg").write_text(fn(), encoding="utf-8")
        print("wrote", OUT / f"{name}.svg")
