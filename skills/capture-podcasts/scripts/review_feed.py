#!/usr/bin/env python3
"""Review public podcast RSS feeds and maintain a no-backfill cursor."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


USER_AGENT = "LocalKnowledgeIntake/1.0 (+private RSS reader)"


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def child_text(node: ET.Element, names: set[str]) -> str | None:
    for child in node:
        if local_name(child.tag) in names and child.text:
            value = child.text.strip()
            if value:
                return value
    return None


def parse_item(item: ET.Element) -> dict[str, object]:
    guid = child_text(item, {"guid", "id"})
    link = child_text(item, {"link"})
    title = child_text(item, {"title"}) or "Untitled episode"
    published = child_text(item, {"pubdate", "published", "updated"})
    duration = child_text(item, {"duration"})
    enclosure_url = None
    transcripts: list[dict[str, str]] = []

    for child in item:
        name = local_name(child.tag)
        if name == "enclosure" and not enclosure_url:
            enclosure_url = child.attrib.get("url")
        elif name == "transcript":
            url = child.attrib.get("url") or (child.text or "").strip()
            if url:
                transcripts.append(
                    {
                        "url": url,
                        "type": child.attrib.get("type", ""),
                        "language": child.attrib.get("language", ""),
                    }
                )

    stable_id = guid or link or enclosure_url
    return {
        "id": stable_id,
        "guid": guid,
        "title": title,
        "published": published,
        "duration": duration,
        "link": link,
        "enclosure_url": enclosure_url,
        "transcripts": transcripts,
    }


def fetch_feed(url: str, etag: str | None = None, modified: str | None = None) -> tuple[bytes | None, dict[str, str]]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.5"}
    if etag:
        headers["If-None-Match"] = etag
    if modified:
        headers["If-Modified-Since"] = modified
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            metadata = {
                "etag": response.headers.get("ETag", ""),
                "last_modified": response.headers.get("Last-Modified", ""),
                "final_url": response.geturl(),
            }
            return response.read(), metadata
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return None, {"not_modified": "true"}
        raise


def parse_feed(payload: bytes) -> tuple[str, list[dict[str, object]]]:
    root = ET.fromstring(payload)
    channel = next((node for node in root.iter() if local_name(node.tag) in {"channel", "feed"}), root)
    show_title = child_text(channel, {"title"}) or "Unknown podcast"
    items = [parse_item(node) for node in channel if local_name(node.tag) in {"item", "entry"}]
    return show_title, [item for item in items if item.get("id")]


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def atomic_json_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def podcast_state(loop_state: dict) -> dict:
    state = loop_state.setdefault("state", {})
    cursors = state.setdefault("cursors", {})
    return cursors.setdefault("podcasts", {})


def review_one(feed: dict, loop_state: dict, initialize: bool) -> dict[str, object]:
    url = feed["rss_url"]
    feeds_state = podcast_state(loop_state)
    previous = feeds_state.get(url, {})
    payload, headers = fetch_feed(url, previous.get("etag"), previous.get("last_modified"))
    if payload is None:
        return {"feed": url, "status": "not_modified", "new_episodes": []}

    show_title, items = parse_feed(payload)
    now = datetime.now(timezone.utc).isoformat()
    latest_id = items[0]["id"] if items else None

    if initialize or not previous.get("latest_id"):
        feeds_state[url] = {
            "name": feed.get("name") or show_title,
            "initialized_at": now,
            "latest_id": latest_id,
            "etag": headers.get("etag"),
            "last_modified": headers.get("last_modified"),
            "final_url": headers.get("final_url", url),
        }
        return {
            "feed": url,
            "show": show_title,
            "status": "initialized_without_backfill",
            "current_episode_count": len(items),
            "latest": items[0] if items else None,
            "new_episodes": [],
        }

    cursor = previous["latest_id"]
    new_items: list[dict[str, object]] = []
    for item in items:
        if item["id"] == cursor:
            break
        new_items.append(item)

    previous.update(
        {
            "name": feed.get("name") or show_title,
            "checked_at": now,
            "etag": headers.get("etag"),
            "last_modified": headers.get("last_modified"),
            "final_url": headers.get("final_url", url),
        }
    )
    return {"feed": url, "show": show_title, "status": "reviewed", "new_episodes": new_items}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--initialize", action="store_true", help="Seed current feed heads and process no history")
    parser.add_argument("--write-state", action="store_true", help="Persist feed metadata and cursors")
    args = parser.parse_args()

    registry = load_json(args.registry)
    loop_state = load_json(args.state)
    results = []
    for feed in registry.get("feeds", []):
        if feed.get("active", True):
            try:
                results.append(review_one(feed, loop_state, args.initialize))
            except (KeyError, OSError, ValueError, ET.ParseError, urllib.error.URLError) as exc:
                results.append(
                    {
                        "feed": feed.get("rss_url"),
                        "status": "failed",
                        "error": f"{type(exc).__name__}: {exc}",
                        "new_episodes": [],
                    }
                )

    if args.write_state:
        atomic_json_write(args.state, loop_state)
    json.dump({"feeds": results}, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 1 if any(result.get("status") == "failed" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
