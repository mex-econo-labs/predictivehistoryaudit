#!/usr/bin/env python3
"""
screencap.py — Extract video frames at timestamps referenced in analysis JSON.

Usage:
    python3 screencap.py --input analysis.json --caps-dir caps/
    python3 screencap.py --input-dir . --caps-dir caps/    # batch all JSONs
    python3 screencap.py --input analysis.json --caps-dir caps/ --dry-run

For each timestamped item (notable_quotes, rhetoric, predictions), grabs a
single frame from the YouTube video via yt-dlp stream URL + ffmpeg seek.
Updates the JSON in-place with a "screencap" field pointing to the image file.
"""

import argparse
import json
import subprocess
import sys
import os
import glob
import time
import hashlib


YTDLP = os.path.expanduser("~/.local/bin/yt-dlp")
FFMPEG = os.path.expanduser("~/.local/bin/ffmpeg")


def get_stream_url(video_id: str) -> str | None:
    """Get a direct stream URL for the video (lowest quality — we just need a frame)."""
    try:
        result = subprocess.run(
            [YTDLP, "-f", "worst[ext=mp4]/worst", "--get-url",
             f"https://www.youtube.com/watch?v={video_id}"],
            capture_output=True, text=True, timeout=30
        )
        url = result.stdout.strip()
        return url if url and url.startswith("http") else None
    except (subprocess.TimeoutExpired, Exception) as e:
        print(f"  [ERROR] Failed to get stream URL for {video_id}: {e}", file=sys.stderr)
        return None


def grab_frame(stream_url: str, timestamp: str, output_path: str) -> bool:
    """Seek to timestamp in stream and extract one frame as JPEG."""
    try:
        result = subprocess.run(
            [FFMPEG, "-y", "-ss", timestamp, "-i", stream_url,
             "-frames:v", "1", "-update", "1", "-q:v", "2", output_path],
            capture_output=True, text=True, timeout=30
        )
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except (subprocess.TimeoutExpired, Exception) as e:
        print(f"  [ERROR] ffmpeg failed for {timestamp}: {e}", file=sys.stderr)
        return False


def normalize_timestamp(ts: str) -> str:
    """Ensure timestamp is in HH:MM:SS format for ffmpeg."""
    ts = ts.strip()
    # Handle SRT format with comma (00:01:23,456 -> 00:01:23)
    if "," in ts:
        ts = ts.split(",")[0]
    # Handle MM:SS -> 00:MM:SS
    parts = ts.split(":")
    if len(parts) == 2:
        ts = f"00:{ts}"
    return ts


def cap_filename(video_id: str, timestamp: str, index: int) -> str:
    """Generate a unique filename for a screencap."""
    ts_clean = timestamp.replace(":", "").replace(",", "")
    return f"{video_id}_{ts_clean}_{index:02d}.jpg"


def collect_timestamps(data: dict) -> list[tuple[str, list, int, str]]:
    """
    Walk the JSON and collect all (timestamp, parent_list, index, section) tuples
    for items that have a timestamp field and no existing screencap.
    """
    targets = []

    for i, q in enumerate(data.get("notable_quotes", [])):
        if q.get("timestamp") and not q.get("screencap"):
            targets.append((q["timestamp"], data["notable_quotes"], i, "quote"))

    for i, r in enumerate(data.get("rhetoric", [])):
        if r.get("timestamp") and not r.get("screencap"):
            targets.append((r["timestamp"], data["rhetoric"], i, "rhetoric"))

    for i, p in enumerate(data.get("thesis", {}).get("predictions", [])):
        if p.get("timestamp") and not p.get("screencap"):
            targets.append((p["timestamp"], data["thesis"]["predictions"], i, "prediction"))

    return targets


def process_file(json_path: str, caps_dir: str, dry_run: bool = False) -> dict:
    """Process one analysis JSON file. Returns stats dict."""
    print(f"\n{'='*60}")
    print(f"Processing: {os.path.basename(json_path)}")

    with open(json_path) as f:
        data = json.load(f)

    video_id = data["meta"]["video_id"]
    targets = collect_timestamps(data)

    if not targets:
        print("  No timestamps to capture (all done or none found).")
        return {"file": json_path, "total": 0, "captured": 0, "skipped": 0, "failed": 0}

    print(f"  Video: {video_id} | Timestamps to capture: {len(targets)}")

    if dry_run:
        for ts, _, _, section in targets:
            print(f"  [DRY RUN] Would capture {section} @ {ts}")
        return {"file": json_path, "total": len(targets), "captured": 0, "skipped": 0, "failed": 0}

    # Get stream URL once per video
    print(f"  Fetching stream URL...")
    stream_url = get_stream_url(video_id)
    if not stream_url:
        print(f"  [ERROR] Could not get stream URL. Skipping all captures.")
        return {"file": json_path, "total": len(targets), "captured": 0, "skipped": 0, "failed": len(targets)}

    stats = {"file": json_path, "total": len(targets), "captured": 0, "skipped": 0, "failed": 0}

    for idx, (timestamp, parent_list, item_idx, section) in enumerate(targets):
        ts_norm = normalize_timestamp(timestamp)
        filename = cap_filename(video_id, ts_norm, idx)
        output_path = os.path.join(caps_dir, filename)

        # Skip if file already exists
        if os.path.exists(output_path):
            print(f"  [{idx+1}/{len(targets)}] {section} @ {ts_norm} — already exists")
            parent_list[item_idx]["screencap"] = filename
            stats["skipped"] += 1
            continue

        print(f"  [{idx+1}/{len(targets)}] {section} @ {ts_norm} -> {filename}")
        success = grab_frame(stream_url, ts_norm, output_path)

        if success:
            parent_list[item_idx]["screencap"] = filename
            stats["captured"] += 1
        else:
            stats["failed"] += 1

        # Brief pause to avoid hammering YouTube
        time.sleep(0.5)

    # Write updated JSON back
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Updated JSON with screencap references.")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Extract screencaps at analysis timestamps")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", help="Single analysis JSON file")
    group.add_argument("--input-dir", help="Directory of analysis JSON files")
    parser.add_argument("--caps-dir", default="caps", help="Output directory for screencaps")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be captured without doing it")
    args = parser.parse_args()

    # Resolve caps dir relative to input location
    if args.input:
        base_dir = os.path.dirname(os.path.abspath(args.input))
    else:
        base_dir = os.path.abspath(args.input_dir)

    caps_dir = os.path.join(base_dir, args.caps_dir)
    os.makedirs(caps_dir, exist_ok=True)

    # Collect files to process
    if args.input:
        files = [args.input]
    else:
        files = sorted(glob.glob(os.path.join(args.input_dir, "*.json")))
        files = [f for f in files if os.path.basename(f) != "schema.json"]

    if not files:
        print("No analysis JSON files found.")
        sys.exit(1)

    print(f"Screencap extraction")
    print(f"Files: {len(files)} | Output: {caps_dir} | Dry run: {args.dry_run}")

    all_stats = []
    for json_path in files:
        stats = process_file(json_path, caps_dir, args.dry_run)
        all_stats.append(stats)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    total = sum(s["total"] for s in all_stats)
    captured = sum(s["captured"] for s in all_stats)
    skipped = sum(s["skipped"] for s in all_stats)
    failed = sum(s["failed"] for s in all_stats)
    print(f"  Total targets: {total}")
    print(f"  Captured: {captured}")
    print(f"  Already existed: {skipped}")
    print(f"  Failed: {failed}")


if __name__ == "__main__":
    main()
