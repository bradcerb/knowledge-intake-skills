#!/usr/bin/env python3
"""Transcribe an inclusive episode-number range from a podcast RSS XML file."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def looks_like_workspace(path: Path) -> bool:
    return (path / "skills" / "knowledge-intake" / "references" / "workspace.json").exists()


def resolve_workspace_root(value: str | None = None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    env_value = os.environ.get("KNOWLEDGE_WORKSPACE_ROOT")
    if env_value:
        return Path(env_value).expanduser().resolve()
    for start in [Path.cwd().resolve(), Path(__file__).resolve()]:
        for candidate in [start, *start.parents]:
            if looks_like_workspace(candidate):
                return candidate
    return Path(__file__).resolve().parents[3]


def resolve_under_workspace(workspace_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else workspace_root / path


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def child_text(node: ET.Element, names: set[str]) -> str:
    for child in node:
        if local_name(child.tag) in names and child.text:
            value = child.text.strip()
            if value:
                return value
    return ""


def parse_feed(path: Path, episode_min: int, episode_max: int | None) -> list[dict[str, str]]:
    root = ET.parse(path).getroot()
    channel = root.find("channel")
    if channel is None:
        channel = next((node for node in root.iter() if local_name(node.tag) in {"channel", "feed"}), root)
    show = child_text(channel, {"title"}) or "Unknown podcast"
    episodes: list[dict[str, str]] = []
    for item in channel.findall("item"):
        title = child_text(item, {"title"}) or "Untitled episode"
        match = re.search(r"\bEp\s*(\d+)\b", title, re.IGNORECASE)
        if not match:
            continue
        episode_number = int(match.group(1))
        if episode_number < episode_min:
            continue
        if episode_max is not None and episode_number > episode_max:
            continue
        enclosure_url = ""
        for child in item:
            if local_name(child.tag) == "enclosure":
                enclosure_url = child.attrib.get("url", "")
                break
        if not enclosure_url:
            continue
        episodes.append(
            {
                "episode": str(episode_number),
                "external_id": child_text(item, {"guid", "id"}) or enclosure_url,
                "title": title,
                "show": show,
                "published_at": child_text(item, {"pubdate", "published", "updated"}),
                "duration": child_text(item, {"duration"}),
                "episode_url": child_text(item, {"link"}),
                "audio_url": enclosure_url,
                "description_html": child_text(item, {"description", "summary"}),
            }
        )
    return sorted(episodes, key=lambda item: int(item["episode"]))


def run_episode(workspace_root: Path, runner: Path, raw_dir: Path, rss_feed: str, episode: dict[str, str], threads: int) -> dict[str, object]:
    command = [
        sys.executable,
        str(runner),
        "--workspace-root",
        str(workspace_root),
        "--raw-dir",
        str(raw_dir),
        "--threads",
        str(threads),
        "--external-id",
        episode["external_id"],
        "--title",
        episode["title"],
        "--show",
        episode["show"],
        "--published-at",
        episode["published_at"],
        "--duration",
        episode["duration"],
        "--rss-feed",
        rss_feed,
        "--episode-url",
        episode["episode_url"],
        "--audio-url",
        episode["audio_url"],
        "--description-html",
        episode["description_html"],
    ]
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode != 0:
        return {
            "episode": episode["episode"],
            "title": episode["title"],
            "status": "failed",
            "returncode": completed.returncode,
            "stderr_tail": completed.stderr[-4000:],
            "stdout_tail": completed.stdout[-4000:],
        }
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"raw_output": completed.stdout[-4000:]}
    return {"episode": episode["episode"], "title": episode["title"], "status": "written", **payload}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root")
    parser.add_argument("--feed-xml", required=True, type=Path)
    parser.add_argument("--rss-feed", required=True)
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--runner", required=True, type=Path)
    parser.add_argument("--episode-min", required=True, type=int)
    parser.add_argument("--episode-max", type=int)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    workspace_root = resolve_workspace_root(args.workspace_root)
    args.feed_xml = resolve_under_workspace(workspace_root, args.feed_xml)
    args.raw_dir = resolve_under_workspace(workspace_root, args.raw_dir)
    args.runner = resolve_under_workspace(workspace_root, args.runner)

    episodes = parse_feed(args.feed_xml, args.episode_min, args.episode_max)
    print(json.dumps({"status": "queued", "count": len(episodes), "episodes": [item["episode"] for item in episodes]}))
    results: list[dict[str, object]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(run_episode, workspace_root, args.runner, args.raw_dir, args.rss_feed, episode, args.threads)
            for episode in episodes
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)

    results = sorted(results, key=lambda item: int(str(item["episode"])))
    failed = [item for item in results if item.get("status") == "failed"]
    print(json.dumps({"status": "complete" if not failed else "failed", "written": len(results) - len(failed), "failed": len(failed), "results": results}, indent=2, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
