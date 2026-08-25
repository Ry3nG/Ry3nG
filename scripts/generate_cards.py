#!/usr/bin/env python3
"""Build the WHEN I CODE heatmap from GitHub PushEvents.

Uses the authenticated events feed so private repos count. One cell
increment per push, stamped at push time in SGT. GitHub only keeps a
few hundred events, which is about two weeks for this account.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

USER = "Ry3nG"
OUT = Path("dist")

BG = "#f5f5f7"
DIM = "#6e6e73"
ACCENT = "#0071e3"
HEATMAP_EMPTY = "#e8edf4"
FONT = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', Helvetica, Arial, sans-serif"

W, H = 540, 195
RADIUS = 8
PAD = 28
TZ = timezone(timedelta(hours=8))
LOOKBACK_DAYS = 14
MAX_EVENT_PAGES = 3


def token() -> str:
    for name in ("PROFILE_STATS_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(name)
        if value:
            return value
    raise SystemExit("need PROFILE_STATS_TOKEN, GH_TOKEN, or GITHUB_TOKEN")


def api_get(url: str, auth: str) -> object:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {auth}",
            "User-Agent": "Ry3nG-profile-cards",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def fetch_push_times(auth: str) -> list[datetime]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    stamps: list[datetime] = []
    for page in range(1, MAX_EVENT_PAGES + 1):
        url = f"https://api.github.com/users/{USER}/events?per_page=100&page={page}"
        try:
            payload = api_get(url, auth)
        except urllib.error.HTTPError as exc:
            if exc.code == 422 and stamps:
                break
            raise SystemExit(f"GitHub events HTTP {exc.code}: {url}") from exc
        if not isinstance(payload, list):
            raise SystemExit(f"GitHub events returned {type(payload).__name__}, expected list")
        if not payload:
            break
        stop = False
        for event in payload:
            created = event.get("created_at")
            if not created:
                continue
            moment = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if moment < cutoff:
                stop = True
                break
            if event.get("type") == "PushEvent":
                stamps.append(moment)
        if stop or len(payload) < 100:
            break
    if not stamps:
        raise SystemExit("no PushEvents in the last 14 days; refusing to write an empty heatmap")
    return stamps


def build_heatmap(stamps: list[datetime]) -> str:
    cell = [[0] * 24 for _ in range(7)]
    for moment in stamps:
        local = moment.astimezone(TZ)
        cell[local.weekday()][local.hour] += 1

    max_val = max(value for row in cell for value in row)
    if max_val <= 0:
        raise SystemExit("heatmap counts are all zero")

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
    for weekday in range(7):
        row_y = grid_y + weekday * (cell_h + gap)
        parts.append(
            f'  <text x="{label_x}" y="{row_y + cell_h - 3}" font-size="10" font-weight="500" fill="{DIM}">{days[weekday]}</text>'
        )
        for hour in range(24):
            cx = grid_x + hour * (cell_w + gap)
            intensity = cell[weekday][hour] / max_val
            if intensity < 0.01:
                fill = f'fill="{HEATMAP_EMPTY}"'
            else:
                fill = f'fill="{ACCENT}" fill-opacity="{0.18 + 0.82 * intensity:.2f}"'
            parts.append(
                f'  <rect x="{cx}" y="{row_y}" width="{cell_w}" height="{cell_h}" rx="2" {fill}/>'
            )

    axis_y = grid_y + 7 * (cell_h + gap) + 14
    for hour, label in ((0, "00"), (6, "06"), (12, "12"), (18, "18"), (23, "23")):
        lx = grid_x + hour * (cell_w + gap) + cell_w / 2
        parts.append(
            f'  <text x="{lx:.1f}" y="{axis_y}" font-size="9" fill="{DIM}" text-anchor="middle">{label}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stamps = fetch_push_times(token())
    (OUT / "coding-heatmap.svg").write_text(build_heatmap(stamps))
    print(f"wrote {OUT / 'coding-heatmap.svg'} from {len(stamps)} pushes")


if __name__ == "__main__":
    main()
