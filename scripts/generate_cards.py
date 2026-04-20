#!/usr/bin/env python3
"""Build Apple-style WakaTime summary SVGs.

- Left card (coding-heatmap.svg): 7×24 hour-of-day heatmap over last 14 days,
  uses authenticated /durations endpoint.
- Right card (coding-breakdown.svg): auto-rotating Languages ↔ Platforms,
  uses public /stats (all-time).
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API_KEY = os.environ.get("WAKATIME_API_KEY")
USER = "Ry3nG"
AUTH_BASE = "https://wakatime.com/api/v1/users/current"
PUBLIC_BASE = f"https://wakatime.com/api/v1/users/{USER}"
OUT = Path("dist")

BG = "#f5f5f7"
TEXT = "#1d1d1f"
DIM = "#6e6e73"
ACCENT = "#0071e3"
GRAYS = ["#86868b", "#a1a1a6", "#c7c7cc", "#d2d2d7", "#e5e5ea"]
HEATMAP_EMPTY = "#e8edf4"

FONT = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', Helvetica, Arial, sans-serif"

W, H = 540, 195
RADIUS = 8
PAD = 28
TZ_OFFSET_HOURS = 8  # Singapore


def auth_header():
    if not API_KEY:
        raise SystemExit("WAKATIME_API_KEY not set")
    return "Basic " + base64.b64encode(API_KEY.encode()).decode()


def api_get(url, auth=True):
    headers = {"User-Agent": "Mozilla/5.0 card-gen"}
    if auth:
        headers["Authorization"] = auth_header()
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def safe_get(url, auth=True):
    try:
        return api_get(url, auth=auth)
    except urllib.error.HTTPError as e:
        print(f"  ! {url} -> HTTP {e.code}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ! {url} -> {e}", file=sys.stderr)
        return None


def xml_escape(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------- Heatmap (left card) ----------

def build_heatmap():
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=13)

    cell = [[0.0] * 24 for _ in range(7)]
    day_count = [0] * 7

    for i in range(14):
        d = start + timedelta(days=i)
        iso = d.isoformat()
        time.sleep(0.4)
        resp = safe_get(f"{AUTH_BASE}/durations?date={iso}")
        if not resp:
            continue
        weekday = d.weekday()
        day_count[weekday] += 1
        for session in resp.get("data", []):
            start_ts = session.get("time", 0)
            dur = session.get("duration", 0)
            local_dt = datetime.fromtimestamp(start_ts, timezone.utc) + timedelta(hours=TZ_OFFSET_HOURS)
            hour = local_dt.hour
            cell[weekday][hour] += dur

    for wd in range(7):
        if day_count[wd] > 0:
            for h in range(24):
                cell[wd][h] /= day_count[wd]

    flat = [c for row in cell for c in row]
    max_val = max(flat) if flat else 1.0
    if max_val == 0:
        max_val = 1.0

    label_x = PAD
    label_w = 24
    grid_x = label_x + label_w
    grid_y = 62
    cell_w = 17
    cell_h = 14
    gap = 1
    days = ["M", "T", "W", "T", "F", "S", "S"]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
        f'  <rect width="{W}" height="{H}" rx="{RADIUS}" fill="{BG}"/>',
        f'  <text x="{PAD}" y="44" font-size="11" font-weight="600" fill="{DIM}" letter-spacing="1.5">WHEN I CODE</text>',
        f'  <text x="{W - PAD}" y="44" font-size="10" font-weight="500" fill="{DIM}" text-anchor="end" letter-spacing="0.5">LAST 14 DAYS · SGT</text>',
    ]

    for wd in range(7):
        row_y = grid_y + wd * (cell_h + gap)
        parts.append(
            f'  <text x="{label_x}" y="{row_y + cell_h - 3}" font-size="10" font-weight="500" fill="{DIM}">{days[wd]}</text>'
        )
        for h in range(24):
            cx = grid_x + h * (cell_w + gap)
            val = cell[wd][h]
            intensity = val / max_val if max_val > 0 else 0
            if intensity < 0.01:
                parts.append(
                    f'  <rect x="{cx}" y="{row_y}" width="{cell_w}" height="{cell_h}" rx="2" fill="{HEATMAP_EMPTY}"/>'
                )
            else:
                op = 0.18 + 0.82 * intensity
                parts.append(
                    f'  <rect x="{cx}" y="{row_y}" width="{cell_w}" height="{cell_h}" rx="2" fill="{ACCENT}" fill-opacity="{op:.2f}"/>'
                )

    axis_y = grid_y + 7 * (cell_h + gap) + 14
    for h, label in [(0, "00"), (6, "06"), (12, "12"), (18, "18"), (23, "23")]:
        lx = grid_x + h * (cell_w + gap) + cell_w / 2
        parts.append(
            f'  <text x="{lx:.1f}" y="{axis_y}" font-size="9" fill="{DIM}" text-anchor="middle">{label}</text>'
        )

    parts.append('</svg>')
    return "\n".join(parts) + "\n"


# ---------- Breakdown rotation (right card) ----------

def stacked_bar(items, colors, x, y, w, h):
    out = ['  <g>']
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
        label = f'{item["name"]} {item["percent"]:.1f}%'
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


def build_breakdown(stats_data):
    langs_raw = stats_data.get("languages", [])
    top5 = langs_raw[:5]
    rest = sum(l["percent"] for l in langs_raw[5:])
    langs = top5 + ([{"name": "Other", "percent": rest}] if rest > 0.5 else [])
    oss = stats_data.get("operating_systems", [])

    lang_colors = [ACCENT] + GRAYS
    os_colors = [ACCENT] + GRAYS

    dur = "10s"
    key_times = "0;0.47;0.5;0.97;1"
    lang_vals = "1;1;0;0;1"
    os_vals = "0;0;1;1;0"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
        f'  <rect width="{W}" height="{H}" rx="{RADIUS}" fill="{BG}"/>',
        '  <g opacity="1">',
        panel("Languages", langs, lang_colors),
        f'    <animate attributeName="opacity" values="{lang_vals}" keyTimes="{key_times}" dur="{dur}" repeatCount="indefinite"/>',
        '  </g>',
        '  <g opacity="0">',
        panel("Platforms", oss, os_colors),
        f'    <animate attributeName="opacity" values="{os_vals}" keyTimes="{key_times}" dur="{dur}" repeatCount="indefinite"/>',
        '  </g>',
    ]

    dots_cx = W / 2
    dots_y = H - 14
    parts.append(f'  <circle cx="{dots_cx - 7}" cy="{dots_y}" r="3" fill="{ACCENT}">')
    parts.append(f'    <animate attributeName="fill" values="{ACCENT};{ACCENT};{GRAYS[3]};{GRAYS[3]};{ACCENT}" keyTimes="{key_times}" dur="{dur}" repeatCount="indefinite"/>')
    parts.append('  </circle>')
    parts.append(f'  <circle cx="{dots_cx + 7}" cy="{dots_y}" r="3" fill="{GRAYS[3]}">')
    parts.append(f'    <animate attributeName="fill" values="{GRAYS[3]};{GRAYS[3]};{ACCENT};{ACCENT};{GRAYS[3]}" keyTimes="{key_times}" dur="{dur}" repeatCount="indefinite"/>')
    parts.append('  </circle>')
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    print("Building heatmap from last 14 days of /durations...")
    (OUT / "coding-heatmap.svg").write_text(build_heatmap())

    print("Fetching public all-time /stats for breakdown...")
    stats = safe_get(f"{PUBLIC_BASE}/stats", auth=False)
    if not stats:
        print("! failed to fetch public stats", file=sys.stderr)
        sys.exit(1)
    (OUT / "coding-breakdown.svg").write_text(build_breakdown(stats["data"]))

    print(f"Wrote {OUT}/coding-heatmap.svg and {OUT}/coding-breakdown.svg")


if __name__ == "__main__":
    main()
