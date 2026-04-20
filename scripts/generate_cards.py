#!/usr/bin/env python3
"""Build Apple-style WakaTime summary SVGs from the public /stats endpoint."""
import json
import sys
import urllib.request
from pathlib import Path

USER = "Ry3nG"
API = f"https://wakatime.com/api/v1/users/{USER}/stats"
OUT = Path("dist")

BG = "#f5f5f7"
TEXT = "#1d1d1f"
DIM = "#6e6e73"
ACCENT = "#0071e3"
GRAYS = ["#86868b", "#a1a1a6", "#c7c7cc", "#d2d2d7", "#e5e5ea"]
FONT = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', Helvetica, Arial, sans-serif"

W, H = 540, 195
RADIUS = 8
PAD = 28


def fetch():
    req = urllib.request.Request(API, headers={"User-Agent": "Mozilla/5.0 card-generator"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)["data"]


def xml_escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def summary_card(data):
    total = data["human_readable_total"]  # e.g. "1,912 hrs 39 mins"
    hrs_num = total.split(" hrs")[0]
    daily = data["human_readable_daily_average"]
    since = data["human_readable_range"].replace("since ", "")
    ai_pct = next((c["percent"] for c in data.get("categories", []) if c["name"] == "AI Coding"), 0.0)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
        f'  <rect width="{W}" height="{H}" rx="{RADIUS}" fill="{BG}"/>',
        f'  <text x="{PAD}" y="44" font-size="11" font-weight="600" fill="{DIM}" letter-spacing="1.5">CODING TIME</text>',
        f'  <text x="{PAD}" y="112" font-size="64" font-weight="600" fill="{TEXT}" letter-spacing="-1.5">{xml_escape(hrs_num)}</text>',
        f'  <text x="{PAD}" y="142" font-size="14" fill="{DIM}">hours since {xml_escape(since)}</text>',
        f'  <text x="{PAD}" y="172" font-size="13" fill="{DIM}">{xml_escape(daily)} daily · {ai_pct:.1f}% AI-assisted</text>',
        '</svg>',
    ]
    return "\n".join(parts) + "\n"


def stacked_bar(items, colors, x, y, w, h):
    out = [f'  <g>']
    cx = x
    for item, color in zip(items, colors):
        seg = w * item["percent"] / 100
        out.append(f'    <rect x="{cx:.2f}" y="{y}" width="{seg:.2f}" height="{h}" fill="{color}"/>')
        cx += seg
    out.append('  </g>')
    return "\n".join(out)


def legend(items, colors, x, y, col_w=160, row_h=22):
    out = []
    for i, (item, color) in enumerate(zip(items, colors)):
        col = i % 3
        row = i // 3
        lx = x + col * col_w
        ly = y + row * row_h
        label = f"{item['name']} {item['percent']:.1f}%"
        out.append(f'    <circle cx="{lx + 4}" cy="{ly - 4}" r="4" fill="{color}"/>')
        out.append(f'    <text x="{lx + 14}" y="{ly}" font-size="12" fill="{TEXT}">{xml_escape(label)}</text>')
    return "\n".join(out)


def panel(kicker, items, colors):
    items = items[:6]
    colors = colors[:len(items)]
    out = [
        f'    <text x="{PAD}" y="44" font-size="11" font-weight="600" fill="{DIM}" letter-spacing="1.5">{kicker.upper()}</text>',
        stacked_bar(items, colors, PAD, 72, W - 2 * PAD, 14),
        legend(items, colors, PAD, 118),
    ]
    return "\n".join(out)


def rotating_card(data):
    langs_raw = data.get("languages", [])
    top5 = langs_raw[:5]
    rest = sum(l["percent"] for l in langs_raw[5:])
    langs = top5 + ([{"name": "Other", "percent": rest}] if rest > 0.5 else [])
    oss = data.get("operating_systems", [])

    lang_colors = [ACCENT] + GRAYS
    os_colors = [ACCENT] + GRAYS

    dur = "10s"
    lang_keytimes = "0;0.47;0.5;0.97;1"
    lang_vals = "1;1;0;0;1"
    os_vals = "0;0;1;1;0"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
        f'  <rect width="{W}" height="{H}" rx="{RADIUS}" fill="{BG}"/>',
        '  <g opacity="1">',
        panel("Languages", langs, lang_colors),
        f'    <animate attributeName="opacity" values="{lang_vals}" keyTimes="{lang_keytimes}" dur="{dur}" repeatCount="indefinite"/>',
        '  </g>',
        '  <g opacity="0">',
        panel("Platforms", oss, os_colors),
        f'    <animate attributeName="opacity" values="{os_vals}" keyTimes="{lang_keytimes}" dur="{dur}" repeatCount="indefinite"/>',
        '  </g>',
    ]

    # pagination dots, centered
    dots_cx = W / 2
    dots_y = H - 18
    parts.append(f'  <circle cx="{dots_cx - 7}" cy="{dots_y}" r="3" fill="{ACCENT}">')
    parts.append(f'    <animate attributeName="fill" values="{ACCENT};{ACCENT};{GRAYS[3]};{GRAYS[3]};{ACCENT}" keyTimes="{lang_keytimes}" dur="{dur}" repeatCount="indefinite"/>')
    parts.append('  </circle>')
    parts.append(f'  <circle cx="{dots_cx + 7}" cy="{dots_y}" r="3" fill="{GRAYS[3]}">')
    parts.append(f'    <animate attributeName="fill" values="{GRAYS[3]};{GRAYS[3]};{ACCENT};{ACCENT};{GRAYS[3]}" keyTimes="{lang_keytimes}" dur="{dur}" repeatCount="indefinite"/>')
    parts.append('  </circle>')
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def main():
    data = fetch()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "coding-summary.svg").write_text(summary_card(data))
    (OUT / "coding-breakdown.svg").write_text(rotating_card(data))
    print(f"wrote {OUT}/coding-summary.svg and {OUT}/coding-breakdown.svg")


if __name__ == "__main__":
    sys.exit(main() or 0)
