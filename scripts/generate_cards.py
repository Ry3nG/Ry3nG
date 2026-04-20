#!/usr/bin/env python3
"""Build Apple-style WakaTime summary SVGs using the authenticated API."""
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
BASE = "https://wakatime.com/api/v1/users/current"
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


def api_get(path):
    req = urllib.request.Request(
        f"{BASE}{path}",
        headers={"Authorization": auth_header(), "User-Agent": "Mozilla/5.0 card-gen"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def safe_get(path):
    try:
        return api_get(path)
    except urllib.error.HTTPError as e:
        print(f"  ! {path} -> HTTP {e.code}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ! {path} -> {e}", file=sys.stderr)
        return None


def xml_escape(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_heatmap():
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=13)

    cell = [[0.0] * 24 for _ in range(7)]
    day_count = [0] * 7

    for i in range(14):
        d = start + timedelta(days=i)
        iso = d.isoformat()
        time.sleep(0.4)
        resp = safe_get(f"/durations?date={iso}")
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


def extract_panel(stats_resp, label):
    if not stats_resp:
        return None
    d = stats_resp.get("data", {})
    total = d.get("human_readable_total", "")
    if " hrs" in total:
        hrs_num = total.split(" hrs")[0]
    elif " hr" in total:
        hrs_num = total.split(" hr")[0]
    else:
        hrs_num = "0"
    daily = d.get("human_readable_daily_average", "—")
    langs = d.get("languages", [])[:3]
    return {"label": label, "hrs_num": hrs_num, "daily": daily, "langs": langs}


def render_panel(p):
    parts = [
        f'    <text x="{PAD}" y="44" font-size="11" font-weight="600" fill="{DIM}" letter-spacing="1.5">{xml_escape(p["label"])}</text>',
        f'    <text x="{PAD}" y="108" font-size="58" font-weight="600" fill="{TEXT}" letter-spacing="-1.2">{xml_escape(p["hrs_num"])}</text>',
        f'    <text x="{PAD}" y="132" font-size="13" fill="{DIM}">hrs · {xml_escape(p["daily"])} daily avg</text>',
    ]
    if p["langs"]:
        lang_text = "  ·  ".join(
            f'{xml_escape(l["name"])} {l["percent"]:.0f}%' for l in p["langs"]
        )
        parts.append(
            f'    <text x="{PAD}" y="162" font-size="12" fill="{TEXT}">{xml_escape(lang_text)}</text>'
        )
    return "\n".join(parts)


def build_rotating(panels):
    panels = [p for p in panels if p]
    n = len(panels)
    if n == 0:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">'
            f'<rect width="{W}" height="{H}" rx="{RADIUS}" fill="{BG}"/>'
            f'<text x="{W//2}" y="{H//2}" text-anchor="middle" font-family="{FONT}" font-size="13" fill="{DIM}">no data</text>'
            f'</svg>\n'
        )

    cycle = 5 * n
    fade = 0.03
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
        f'  <rect width="{W}" height="{H}" rx="{RADIUS}" fill="{BG}"/>',
    ]

    for i, p in enumerate(panels):
        t0 = i / n
        t1 = (i + 1) / n
        parts.append(f'  <g opacity="{1 if i == 0 else 0}">')
        parts.append(render_panel(p))
        if n > 1:
            if i == 0:
                kt = f"0;{max(0, t1 - fade):.3f};{t1:.3f};{1 - fade:.3f};1"
                vv = "1;1;0;0;1"
            else:
                kt = f"0;{max(0, t0 - fade):.3f};{t0:.3f};{t1 - fade:.3f};{t1:.3f};1"
                vv = "0;0;1;1;0;0"
            parts.append(
                f'    <animate attributeName="opacity" values="{vv}" keyTimes="{kt}" dur="{cycle}s" repeatCount="indefinite"/>'
            )
        parts.append('  </g>')

    dots_y = H - 14
    dot_r = 3
    gap_between = 10
    total_dots_w = n * (2 * dot_r) + (n - 1) * gap_between
    dots_start = (W - total_dots_w) / 2
    for i in range(n):
        cx = dots_start + dot_r + i * (2 * dot_r + gap_between)
        init_fill = ACCENT if i == 0 else GRAYS[3]
        parts.append(f'  <circle cx="{cx:.1f}" cy="{dots_y}" r="{dot_r}" fill="{init_fill}">')
        if n > 1:
            t0 = i / n
            t1 = (i + 1) / n
            if i == 0:
                kt = f"0;{max(0, t1 - fade):.3f};{t1:.3f};{1 - fade:.3f};1"
                vv = f"{ACCENT};{ACCENT};{GRAYS[3]};{GRAYS[3]};{ACCENT}"
            else:
                kt = f"0;{max(0, t0 - fade):.3f};{t0:.3f};{t1 - fade:.3f};{t1:.3f};1"
                vv = f"{GRAYS[3]};{GRAYS[3]};{ACCENT};{ACCENT};{GRAYS[3]};{GRAYS[3]}"
            parts.append(
                f'    <animate attributeName="fill" values="{vv}" keyTimes="{kt}" dur="{cycle}s" repeatCount="indefinite"/>'
            )
        parts.append('  </circle>')

    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    print("Fetching stats ranges...")
    panels = []
    for path, label in [
        ("/stats/this_year", "2026 SO FAR"),
        ("/stats/last_6_months", "LAST 6 MONTHS"),
        ("/stats/last_7_days", "LAST 7 DAYS"),
    ]:
        time.sleep(0.3)
        data = safe_get(path)
        p = extract_panel(data, label)
        if p:
            print(f"  {label}: {p['hrs_num']} hrs")
            panels.append(p)

    print("Building heatmap from last 14 days of /durations...")
    heatmap_svg = build_heatmap()
    (OUT / "coding-heatmap.svg").write_text(heatmap_svg)

    print("Building rotating stats card...")
    rotating_svg = build_rotating(panels)
    (OUT / "coding-ranges.svg").write_text(rotating_svg)

    print(f"Wrote {OUT}/coding-heatmap.svg and {OUT}/coding-ranges.svg")


if __name__ == "__main__":
    main()
