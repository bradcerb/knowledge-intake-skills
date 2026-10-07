#!/usr/bin/env python3
"""Capture one YouTube video into a local raw Markdown transcript."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
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


WORKSPACE_ROOT = resolve_workspace_root()


def executable_names(name: str) -> list[str]:
    if os.name == "nt":
        if name.endswith((".exe", ".cmd", ".bat")):
            return [name]
        return [f"{name}.exe", f"{name}.cmd", f"{name}.bat", name]
    return [name]


def resolve_under_workspace(path: Path) -> Path:
    return path if path.is_absolute() else WORKSPACE_ROOT / path


def local_tool(name: str) -> str | None:
    for candidate in executable_names(name):
        path_tool = shutil.which(candidate)
        if path_tool:
            return path_tool
    for candidate in executable_names(name):
        workspace_tool = WORKSPACE_ROOT / "tools" / "bin" / candidate
        if workspace_tool.exists():
            return str(workspace_tool)
    return None


def local_whisper_cpp_model() -> str | None:
    env_model = os.environ.get("WHISPER_CPP_MODEL")
    if env_model:
        return env_model
    workspace_model = WORKSPACE_ROOT / "tools" / "whisper.cpp" / "models" / "ggml-base.en.bin"
    if workspace_model.exists():
        return str(workspace_model)
    return None


def dependency_report() -> dict[str, object]:
    yt_dlp = local_tool("yt-dlp")
    ffmpeg = local_tool("ffmpeg")
    whisper_cli = local_tool("whisper-cli")
    model = local_whisper_cpp_model()
    return {
        "workspace_root": str(WORKSPACE_ROOT),
        "ready": bool(yt_dlp and ffmpeg and whisper_cli and model),
        "yt_dlp": yt_dlp,
        "ffmpeg": ffmpeg,
        "whisper_cpp_cli": whisper_cli,
        "whisper_cpp_model": model,
        "missing": [
            item
            for item, present in {
                "yt-dlp": bool(yt_dlp),
                "ffmpeg": bool(ffmpeg),
                "whisper-cli": bool(whisper_cli),
                "WHISPER_CPP_MODEL or workspace ggml-base.en.bin": bool(model),
            }.items()
            if not present
        ],
    }


def prepare_dependencies() -> None:
    script = WORKSPACE_ROOT / "skills" / "knowledge-intake" / "scripts" / "prepare_local_transcription.py"
    if not script.exists():
        raise RuntimeError(f"Missing dependency bootstrap script: {script}")
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--workspace-root",
            str(WORKSPACE_ROOT),
            "--yes",
        ],
        check=True,
    )


def run_json(command: list[str]) -> dict:
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr[-4000:] or completed.stdout[-4000:])
        completed.check_returncode()
    return json.loads(completed.stdout)


def run_quiet(command: list[str]) -> None:
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout[-4000:])
        sys.stderr.write(completed.stderr[-4000:])
        completed.check_returncode()


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:80] or "youtube-video"


def yaml_string(value: object) -> str:
    return json.dumps("" if value is None else str(value), ensure_ascii=False)


def published_at(metadata: dict) -> str:
    timestamp = metadata.get("timestamp")
    if timestamp:
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    upload_date = str(metadata.get("upload_date") or "")
    if len(upload_date) == 8:
        return f"{upload_date[0:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    return ""


def duration_minutes(metadata: dict) -> float | None:
    duration = metadata.get("duration")
    if duration is None:
        return None
    try:
        return round(float(duration) / 60, 2)
    except (TypeError, ValueError):
        return None


def get_metadata(url: str, allow_playlist: bool) -> dict:
    yt_dlp = local_tool("yt-dlp") or "yt-dlp"
    command = [
        yt_dlp,
        "--dump-single-json",
        "--skip-download",
        "--no-warnings",
        "--extractor-args",
        "youtube:player_client=android",
    ]
    if not allow_playlist:
        command.append("--no-playlist")
    command.append(url)
    return run_json(command)


def download_audio(url: str, destination_dir: Path, allow_playlist: bool) -> Path:
    yt_dlp = local_tool("yt-dlp") or "yt-dlp"
    output = destination_dir / "source.%(ext)s"
    command = [
        yt_dlp,
        "--format",
        "bestaudio/best",
        "--output",
        str(output),
        "--no-progress",
        "--quiet",
        "--no-warnings",
        "--extractor-args",
        "youtube:player_client=android",
    ]
    if not allow_playlist:
        command.append("--no-playlist")
    command.append(url)
    run_quiet(command)
    candidates = [path for path in destination_dir.iterdir() if path.name.startswith("source.")]
    if not candidates:
        raise RuntimeError("yt-dlp completed but no audio file was created")
    return candidates[0]


def convert_audio(source: Path, destination: Path) -> None:
    ffmpeg = local_tool("ffmpeg") or "ffmpeg"
    run_quiet(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-nostdin",
            "-i",
            str(source),
            "-ar",
            "16000",
            "-ac",
            "1",
            str(destination),
        ]
    )


def transcribe(wav_path: Path, work_dir: Path, model_path: str, threads: int) -> str:
    whisper_cli = local_tool("whisper-cli") or "whisper-cli"
    output_prefix = work_dir / "transcript"
    run_quiet(
        [
            whisper_cli,
            "--no-gpu",
            "-np",
            "--threads",
            str(threads),
            "-m",
            model_path,
            "-f",
            str(wav_path),
            "-otxt",
            "-of",
            str(output_prefix),
        ]
    )
    return output_prefix.with_suffix(".txt").read_text(encoding="utf-8").strip()


def raw_markdown(metadata: dict, transcript: str, source_url: str) -> str:
    captured_at = datetime.now(timezone.utc).isoformat()
    description = (metadata.get("description") or "").strip()
    frontmatter = [
        "---",
        "type: video",
        "platform: youtube",
        f"external_id: {yaml_string('youtube:' + str(metadata.get('id') or source_url))}",
        f"title: {yaml_string(metadata.get('title') or 'Untitled video')}",
        f"channel: {yaml_string(metadata.get('channel') or metadata.get('uploader'))}",
        f"published_at: {yaml_string(published_at(metadata))}",
        f"captured_at: {yaml_string(captured_at)}",
        f"duration_minutes: {json.dumps(duration_minutes(metadata))}",
        f"source_url: {yaml_string(metadata.get('webpage_url') or source_url)}",
        "transcript_source: \"whisper.cpp\"",
        "visibility: private",
        "status: raw",
        "---",
        "",
        f"# {metadata.get('title') or 'Untitled video'}",
        "",
        "## Video Notes",
        "",
        description or "_No video description was supplied._",
        "",
        "## Transcript",
        "",
        transcript,
        "",
    ]
    return "\n".join(frontmatter)


def output_path(raw_dir: Path, metadata: dict, source_url: str) -> Path:
    stable_id = str(metadata.get("id") or source_url)
    digest = hashlib.sha256(stable_id.encode("utf-8")).hexdigest()[:10]
    title = str(metadata.get("title") or "youtube-video")
    return raw_dir / f"{slugify(title)}-{digest}.md"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    global WORKSPACE_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-dependencies", action="store_true")
    parser.add_argument("--prepare-dependencies", action="store_true")
    parser.add_argument("--workspace-root")
    parser.add_argument("--url")
    parser.add_argument("--raw-dir", type=Path, default=Path("learnings/raw"))
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--allow-playlist", action="store_true")
    parser.add_argument("--whisper-cpp-model")
    args = parser.parse_args()
    WORKSPACE_ROOT = resolve_workspace_root(args.workspace_root)
    args.raw_dir = resolve_under_workspace(args.raw_dir)
    if not args.whisper_cpp_model:
        args.whisper_cpp_model = local_whisper_cpp_model()

    if args.prepare_dependencies:
        prepare_dependencies()

    if args.check_dependencies:
        json.dump(dependency_report(), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if not args.url:
        parser.error("--url is required unless --check-dependencies is used")
    report = dependency_report()
    if not report["ready"]:
        raise RuntimeError(f"Missing dependencies: {', '.join(report['missing'])}")

    metadata = get_metadata(args.url, args.allow_playlist)
    with tempfile.TemporaryDirectory(prefix="youtube-transcript-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        audio_path = download_audio(args.url, temp_dir, args.allow_playlist)
        wav_path = temp_dir / "source.wav"
        convert_audio(audio_path, wav_path)
        transcript = transcribe(wav_path, temp_dir, args.whisper_cpp_model or "", args.threads)

    if not transcript:
        raise RuntimeError("Transcription completed but produced an empty transcript")

    destination = output_path(args.raw_dir, metadata, args.url)
    atomic_write(destination, raw_markdown(metadata, transcript, args.url))
    json.dump(
        {
            "status": "written",
            "raw_file": str(destination),
            "title": metadata.get("title"),
            "channel": metadata.get("channel") or metadata.get("uploader"),
            "transcript_source": "whisper.cpp",
        },
        sys.stdout,
        indent=2,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
