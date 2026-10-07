#!/usr/bin/env python3
"""Download one podcast episode audio file and write a local transcript raw file."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path


USER_AGENT = "LocalKnowledgeIntake/1.0 (+private podcast transcription)"


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


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if value:
            self.parts.append(value)

    def text(self) -> str:
        return "\n".join(self.parts)


def dependency_report() -> dict[str, object]:
    whisper_cli = local_tool("whisper-cli")
    whisper = local_tool("whisper")
    ffmpeg = local_tool("ffmpeg")
    whisper_cpp_model = local_whisper_cpp_model()
    return {
        "workspace_root": str(WORKSPACE_ROOT),
        "ready": bool(ffmpeg and (whisper or (whisper_cli and whisper_cpp_model))),
        "ffmpeg": ffmpeg,
        "whisper_openai_cli": whisper,
        "whisper_cpp_cli": whisper_cli,
        "whisper_cpp_model": whisper_cpp_model,
        "missing": [
            item
            for item, present in {
                "ffmpeg": bool(ffmpeg),
                "whisper or whisper-cli+WHISPER_CPP_MODEL": bool(whisper or (whisper_cli and whisper_cpp_model)),
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


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:80] or "podcast-episode"


def yaml_string(value: str | None) -> str:
    if value is None:
        value = ""
    return json.dumps(value, ensure_ascii=False)


def duration_minutes(value: str | None) -> float | None:
    if not value:
        return None
    parts = value.strip().split(":")
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        return None
    if len(numbers) == 3:
        hours, minutes, seconds = numbers
    elif len(numbers) == 2:
        hours, minutes, seconds = 0, numbers[0], numbers[1]
    elif len(numbers) == 1:
        hours, minutes, seconds = 0, 0, numbers[0]
    else:
        return None
    return round(hours * 60 + minutes + seconds / 60, 2)


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    parser = TextExtractor()
    parser.feed(html.unescape(value))
    return parser.text()


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def run_quiet(command: list[str]) -> None:
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout[-4000:])
        sys.stderr.write(completed.stderr[-4000:])
        completed.check_returncode()


def download_audio(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        with destination.open("wb") as handle:
            shutil.copyfileobj(response, handle)


def convert_audio(source: Path, destination: Path) -> None:
    ffmpeg = local_tool("ffmpeg") or "ffmpeg"
    run(
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


def transcribe_with_whisper_cli(wav_path: Path, work_dir: Path, model_path: str, threads: int) -> tuple[str, str]:
    output_prefix = work_dir / "transcript"
    whisper_cli = local_tool("whisper-cli") or "whisper-cli"
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
    transcript_path = output_prefix.with_suffix(".txt")
    return transcript_path.read_text(encoding="utf-8").strip(), "whisper.cpp"


def transcribe_with_openai_whisper(wav_path: Path, work_dir: Path, model: str) -> tuple[str, str]:
    whisper = local_tool("whisper") or "whisper"
    run(
        [
            whisper,
            str(wav_path),
            "--model",
            model,
            "--output_dir",
            str(work_dir),
            "--output_format",
            "txt",
            "--fp16",
            "False",
        ]
    )
    transcript_path = work_dir / f"{wav_path.stem}.txt"
    return transcript_path.read_text(encoding="utf-8").strip(), f"openai-whisper:{model}"


def choose_engine(args: argparse.Namespace) -> tuple[str, str | None]:
    report = dependency_report()
    if not report["ffmpeg"]:
        raise RuntimeError("Missing dependency: ffmpeg")

    requested = args.engine
    if requested in {"auto", "whisper-cpp"} and report["whisper_cpp_cli"] and args.whisper_cpp_model:
        return "whisper-cpp", args.whisper_cpp_model
    if requested == "whisper-cpp":
        raise RuntimeError("Missing dependency: whisper-cli plus --whisper-cpp-model or WHISPER_CPP_MODEL")

    if requested in {"auto", "openai-whisper"} and report["whisper_openai_cli"]:
        return "openai-whisper", args.model
    if requested == "openai-whisper":
        raise RuntimeError("Missing dependency: whisper Python CLI")

    raise RuntimeError("Missing dependency: install whisper, or install whisper-cli and set WHISPER_CPP_MODEL")


def raw_markdown(args: argparse.Namespace, transcript: str, transcript_source: str) -> str:
    captured_at = datetime.now(timezone.utc).isoformat()
    minutes = duration_minutes(args.duration)
    show_notes = strip_html(args.description_html)
    frontmatter = [
        "---",
        "type: podcast",
        f"external_id: {yaml_string(args.external_id)}",
        f"title: {yaml_string(args.title)}",
        f"show: {yaml_string(args.show)}",
        f"published_at: {yaml_string(args.published_at)}",
        f"captured_at: {yaml_string(captured_at)}",
        f"duration_minutes: {json.dumps(minutes)}",
        f"rss_feed: {yaml_string(args.rss_feed)}",
        f"episode_url: {yaml_string(args.episode_url)}",
        f"audio_url: {yaml_string(args.audio_url)}",
        f"transcript_source: {yaml_string(transcript_source)}",
        "visibility: private",
        "status: raw",
        "---",
        "",
        f"# {args.title}",
        "",
        "## Show Notes",
        "",
        show_notes or "_No show notes were supplied by the feed._",
        "",
        "## Transcript",
        "",
        transcript,
        "",
    ]
    return "\n".join(frontmatter)


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


def output_path(raw_dir: Path, title: str, stable_id: str) -> Path:
    digest = hashlib.sha256(stable_id.encode("utf-8")).hexdigest()[:10]
    return raw_dir / f"{slugify(title)}-{digest}.md"


def main() -> int:
    global WORKSPACE_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-dependencies", action="store_true")
    parser.add_argument("--prepare-dependencies", action="store_true")
    parser.add_argument("--workspace-root")
    parser.add_argument("--raw-dir", type=Path, default=Path("learnings/raw"))
    parser.add_argument("--engine", choices=["auto", "whisper-cpp", "openai-whisper"], default="auto")
    parser.add_argument("--model", default="base.en", help="Model name for the Python whisper CLI")
    parser.add_argument("--whisper-cpp-model")
    parser.add_argument("--threads", type=int, default=4, help="Threads per whisper.cpp process")
    parser.add_argument("--external-id")
    parser.add_argument("--title")
    parser.add_argument("--show")
    parser.add_argument("--published-at")
    parser.add_argument("--duration")
    parser.add_argument("--rss-feed")
    parser.add_argument("--episode-url")
    parser.add_argument("--audio-url")
    parser.add_argument("--description-html", default="")
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

    required = ["external_id", "title", "show", "rss_feed", "audio_url"]
    missing = [name.replace("_", "-") for name in required if not getattr(args, name)]
    if missing:
        parser.error(f"missing required arguments: {', '.join(missing)}")

    engine, engine_model = choose_engine(args)
    with tempfile.TemporaryDirectory(prefix="podcast-transcript-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        audio_path = temp_dir / "episode-audio"
        wav_path = temp_dir / "episode.wav"
        download_audio(args.audio_url, audio_path)
        convert_audio(audio_path, wav_path)
        if engine == "whisper-cpp":
            transcript, transcript_source = transcribe_with_whisper_cli(wav_path, temp_dir, engine_model or "", args.threads)
        else:
            transcript, transcript_source = transcribe_with_openai_whisper(wav_path, temp_dir, engine_model or args.model)

    if not transcript:
        raise RuntimeError("Transcription completed but produced an empty transcript")

    stable_id = args.external_id or args.episode_url or args.audio_url
    destination = output_path(args.raw_dir, args.title, stable_id)
    atomic_write(destination, raw_markdown(args, transcript, transcript_source))
    json.dump({"status": "written", "raw_file": str(destination), "transcript_source": transcript_source}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
