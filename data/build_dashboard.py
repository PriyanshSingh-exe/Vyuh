"""
build_dashboard.py (v2)
Reads data/alert_log.csv + data/output_detected.mp4 + data/snapshots
and generates a single polished HTML dashboard (data/dashboard.html):
  - Hero video player showing the annotated output video
  - Stat cards
  - Scrollable event timeline synced to timestamps
  - Snapshot gallery

Run this AFTER detect.py has produced alert_log.csv, output_detected.mp4,
and snapshots. Keep dashboard.html in the same data/ folder as the video
and snapshots (it references them by relative path, not embedded).

Usage:
    python build_dashboard.py
"""

import csv
import os
from collections import Counter
from datetime import datetime

LOG_PATH = "data/alert_log.csv"
VIDEO_FILENAME = "output_detected.mp4"
SNAPSHOTS_DIR = "snapshots"  # relative to data/, used as relative src in HTML
OUTPUT_PATH = "data/dashboard.html"
MAX_SNAPSHOTS_SHOWN = 10


def load_alerts(log_path):
    if not os.path.exists(log_path):
        raise FileNotFoundError(f"Could not find {log_path}. Run detect.py first.")
    rows = []
    with open(log_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def event_color(event):
    return {
        "entered_zone": "#ff4d4d",
        "still_present": "#ffb020",
        "detected": "#4da3ff",
    }.get(event, "#8a96ab")


def build_html(rows):
    total_alerts = len(rows)
    unique_ids = set(r["track_id"] for r in rows if r["track_id"] != "-1")
    label_counts = Counter(r["label"] for r in rows)
    event_counts = Counter(r["event"] for r in rows)

    max_ts = max((float(r["timestamp_sec"]) for r in rows), default=1) or 1

    timeline_rows = ""
    for r in sorted(rows, key=lambda r: float(r["timestamp_sec"])):
        color = event_color(r["event"])
        ts = float(r["timestamp_sec"])
        timeline_rows += f"""
        <div class="tl-row" onclick="seekTo({ts})">
            <div class="tl-time">{ts:.1f}s</div>
            <div class="tl-dot" style="background:{color}"></div>
            <div class="tl-info">
                <span class="tag">{r['label']}</span>
                <span class="tag id">ID {r['track_id']}</span>
                <span class="tag event" style="background:{color}22;color:{color}">{r['event']}</span>
            </div>
            <div class="tl-frame">frame {r['frame']}</div>
        </div>
        """

    markers = ""
    for r in rows:
        ts = float(r["timestamp_sec"])
        pct = (ts / max_ts) * 100
        color = event_color(r["event"])
        markers += f'<div class="marker" style="left:{pct:.2f}%;background:{color}" title="{r["label"]} @ {ts:.1f}s"></div>'

    snapshot_rows = [r for r in rows if r.get("snapshot_file")]
    if len(snapshot_rows) > MAX_SNAPSHOTS_SHOWN:
        step = len(snapshot_rows) / MAX_SNAPSHOTS_SHOWN
        snapshot_rows = [snapshot_rows[int(i * step)] for i in range(MAX_SNAPSHOTS_SHOWN)]

    snapshot_cards = ""
    for r in snapshot_rows:
        img_src = f"{SNAPSHOTS_DIR}/{r['snapshot_file']}"
        color = event_color(r["event"])
        caption = f"{r['label']} &middot; ID {r['track_id']} &middot; {r['event']} &middot; t={r['timestamp_sec']}s &middot; frame {r['frame']}"
        snapshot_cards += f"""
        <div class="card" onclick="openLightbox('{img_src}', '{caption}', {r['timestamp_sec']})">
            <img src="{img_src}" loading="lazy" />
            <div class="meta">
                <span class="tag">{r['label']}</span>
                <span class="tag id">ID {r['track_id']}</span>
                <span class="tag event" style="background:{color}22;color:{color}">{r['event']}</span>
                <div class="ts">t = {r['timestamp_sec']}s &middot; frame {r['frame']}</div>
            </div>
        </div>
        """

    label_rows = "".join(
        f"<tr><td>{label}</td><td>{count}</td></tr>"
        for label, count in label_counts.most_common()
    )
    event_rows = "".join(
        f"<tr><td>{event}</td><td>{count}</td></tr>"
        for event, count in event_counts.most_common()
    )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>VYUH - Live Intrusion Dashboard</title>
<style>
    :root {{
        --bg: #0a0f1a;
        --panel: #121a2b;
        --panel2: #0e1524;
        --accent: #ff4d4d;
        --accent2: #ffb020;
        --blue: #4da3ff;
        --text: #e8edf5;
        --muted: #8a96ab;
        --border: #1f2b42;
    }}
    * {{ box-sizing: border-box; }}
    body {{
        margin: 0;
        font-family: 'Segoe UI', system-ui, sans-serif;
        background: var(--bg);
        color: var(--text);
    }}
    .topbar {{
        padding: 18px 32px;
        border-bottom: 1px solid var(--border);
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        background: linear-gradient(90deg, #101828, #0a0f1a);
    }}
    .topbar h1 {{ margin: 0; font-size: 22px; letter-spacing: 0.5px; }}
    .topbar .sub {{ color: var(--muted); font-size: 12px; }}
    .live-dot {{
        display: inline-block;
        width: 8px; height: 8px;
        border-radius: 50%;
        background: var(--accent);
        margin-right: 6px;
        box-shadow: 0 0 8px var(--accent);
        animation: pulse 1.5s infinite;
    }}
    @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} }}
    .layout {{
        display: grid;
        grid-template-columns: 1.6fr 1fr;
        gap: 20px;
        padding: 24px 32px;
    }}
    .video-panel {{
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 14px;
        overflow: hidden;
    }}
    .video-wrap {{ position: relative; background: #000; }}
    video {{ width: 100%; display: block; max-height: 520px; }}
    .scrub-track {{
        position: relative;
        height: 22px;
        margin: 0 16px;
        background: var(--panel2);
    }}
    .marker {{
        position: absolute;
        top: 6px;
        width: 6px; height: 10px;
        border-radius: 2px;
        cursor: pointer;
    }}
    .video-caption {{
        padding: 14px 18px;
        color: var(--muted);
        font-size: 12px;
        border-top: 1px solid var(--border);
    }}
    .stat-row {{ display: flex; gap: 12px; padding: 18px; flex-wrap: wrap; }}
    .stat {{
        background: var(--panel2);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 14px 18px;
        flex: 1;
        min-width: 110px;
    }}
    .stat .num {{ font-size: 26px; font-weight: 700; color: var(--accent2); }}
    .stat .label {{
        font-size: 11px; color: var(--muted); text-transform: uppercase;
        letter-spacing: 0.5px; margin-top: 2px;
    }}
    .side-panel {{
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 14px;
        display: flex;
        flex-direction: column;
        max-height: 700px;
    }}
    .side-panel h2 {{
        margin: 0; padding: 16px 18px; font-size: 14px;
        color: var(--accent2); border-bottom: 1px solid var(--border);
    }}
    .timeline {{ overflow-y: auto; flex: 1; }}
    .tl-row {{
        display: flex; align-items: center; gap: 10px;
        padding: 10px 18px; border-bottom: 1px solid var(--border);
        cursor: pointer; transition: background 0.15s;
    }}
    .tl-row:hover {{ background: var(--panel2); }}
    .tl-time {{ font-size: 11px; color: var(--muted); width: 44px; flex-shrink: 0; }}
    .tl-dot {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}
    .tl-info {{ flex: 1; }}
    .tl-frame {{ font-size: 10px; color: var(--muted); flex-shrink: 0; }}
    .tag {{
        display: inline-block; font-size: 11px; padding: 2px 8px;
        border-radius: 20px; background: #1e2c47; color: var(--text); margin-right: 4px;
    }}
    .tag.id {{ background: #3a2560; }}
    section.below {{ padding: 0 32px 32px 32px; }}
    h2.section-title {{
        font-size: 16px; color: var(--accent2);
        border-bottom: 1px solid var(--border);
        padding-bottom: 8px; margin-top: 8px;
    }}
    .grid {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 14px;
        margin-bottom: 24px;
    }}
    .card {{
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 10px;
        overflow: hidden;
        cursor: pointer;
        transition: transform 0.15s, border-color 0.15s;
    }}
    .card:hover {{ transform: translateY(-2px); border-color: var(--accent2); }}
    .card img {{ width: 100%; display: block; aspect-ratio: 16/9; object-fit: cover; }}
    .card .meta {{ padding: 10px 12px; }}
    .ts {{ font-size: 11px; color: var(--muted); margin-top: 6px; }}
    table {{ width: 100%; max-width: 420px; border-collapse: collapse; font-size: 13px; }}
    td {{ padding: 6px 10px; border-bottom: 1px solid var(--border); }}
    .tables-row {{ display: flex; gap: 40px; flex-wrap: wrap; margin-bottom: 12px; }}
    footer {{ padding: 20px 32px; color: var(--muted); font-size: 11px; }}

    .lightbox {{
        display: none;
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(5, 8, 14, 0.92);
        z-index: 1000;
        align-items: center;
        justify-content: center;
        flex-direction: column;
        padding: 40px;
    }}
    .lightbox.open {{ display: flex; }}
    .lightbox img {{
        max-width: 90vw;
        max-height: 75vh;
        border-radius: 10px;
        border: 1px solid var(--border);
        box-shadow: 0 10px 40px rgba(0,0,0,0.6);
    }}
    .lightbox .caption {{
        margin-top: 16px;
        color: var(--text);
        font-size: 13px;
        text-align: center;
    }}
    .lightbox .actions {{
        margin-top: 16px;
        display: flex;
        gap: 12px;
    }}
    .lightbox button {{
        background: var(--panel2);
        color: var(--text);
        border: 1px solid var(--border);
        padding: 8px 16px;
        border-radius: 8px;
        cursor: pointer;
        font-size: 13px;
    }}
    .lightbox button.primary {{
        background: var(--accent2);
        color: #1a1305;
        border: none;
        font-weight: 600;
    }}
    .lightbox button:hover {{ opacity: 0.85; }}
    .lightbox-close {{
        position: absolute;
        top: 24px;
        right: 32px;
        font-size: 28px;
        color: var(--muted);
        cursor: pointer;
        background: none;
        border: none;
    }}
</style>
</head>
<body>

<div class="topbar">
    <div>
        <h1><span class="live-dot"></span>VYUH &mdash; Intrusion Detection Dashboard</h1>
        <div class="sub">SIH26187 &middot; AI-based Border Surveillance using existing CCTV</div>
    </div>
    <div class="sub">Generated {generated_at}</div>
</div>

<div class="layout">
    <div class="video-panel">
        <div class="video-wrap">
            <video id="mainVideo" controls>
                <source src="{VIDEO_FILENAME}" type="video/mp4">
                Your browser does not support video playback.
            </video>
        </div>
        <div class="scrub-track" id="scrubTrack">
            {markers}
        </div>
        <div class="video-caption">Click any timeline entry or snapshot to jump the video to that moment.</div>
        <div class="stat-row">
            <div class="stat"><div class="num">{total_alerts}</div><div class="label">Total Alerts</div></div>
            <div class="stat"><div class="num">{len(unique_ids)}</div><div class="label">Unique Objects</div></div>
            <div class="stat"><div class="num">{len(label_counts)}</div><div class="label">Object Classes</div></div>
        </div>
    </div>

    <div class="side-panel">
        <h2>Event Timeline</h2>
        <div class="timeline">
            {timeline_rows if timeline_rows else '<p style="padding:18px;color:var(--muted)">No events logged.</p>'}
        </div>
    </div>
</div>

<section class="below">
    <h2 class="section-title">Detection Summary</h2>
    <div class="tables-row">
        <table>
            <tr><td><b>Label</b></td><td><b>Count</b></td></tr>
            {label_rows}
        </table>
        <table>
            <tr><td><b>Event</b></td><td><b>Count</b></td></tr>
            {event_rows}
        </table>
    </div>

    <h2 class="section-title">Snapshot Evidence</h2>
    <div class="grid">
        {snapshot_cards if snapshot_cards else '<p style="color:var(--muted)">No snapshots found.</p>'}
    </div>
</section>

<footer>Generated automatically from alert_log.csv &middot; VYUH Project</footer>

<div class="lightbox" id="lightbox">
    <button class="lightbox-close" onclick="closeLightbox()">&times;</button>
    <img id="lightboxImg" src="" />
    <div class="caption" id="lightboxCaption"></div>
    <div class="actions">
        <button class="primary" id="lightboxSeekBtn">Jump to this moment in video</button>
        <button onclick="closeLightbox()">Close</button>
    </div>
</div>

<script>
    function seekTo(seconds) {{
        const video = document.getElementById('mainVideo');
        video.currentTime = parseFloat(seconds);
        video.play();
    }}

    function openLightbox(src, caption, timestamp) {{
        document.getElementById('lightboxImg').src = src;
        document.getElementById('lightboxCaption').innerHTML = caption;
        document.getElementById('lightbox').classList.add('open');
        document.getElementById('lightboxSeekBtn').onclick = function() {{
            seekTo(timestamp);
            closeLightbox();
        }};
    }}

    function closeLightbox() {{
        document.getElementById('lightbox').classList.remove('open');
    }}

    document.getElementById('lightbox').addEventListener('click', function(e) {{
        if (e.target === this) closeLightbox();
    }});

    document.addEventListener('keydown', function(e) {{
        if (e.key === 'Escape') closeLightbox();
    }});
</script>

</body>
</html>
"""
    return html


def main():
    rows = load_alerts(LOG_PATH)
    html = build_html(rows)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard generated: {OUTPUT_PATH}")
    print(f"Total alerts: {len(rows)}")
    video_path = os.path.join("data", VIDEO_FILENAME)
    if not os.path.exists(video_path):
        print(f"WARNING: {video_path} not found - video player will show a blank/broken video.")


if __name__ == "__main__":
    main()
    