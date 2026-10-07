#!/usr/bin/env python3
"""Prepare local transcription tools for the selected workspace.

Installs workspace-local helpers where possible:
- yt-dlp in tools/youtube/venv
- ffmpeg via imageio-ffmpeg in tools/ffmpeg/venv
- whisper.cpp under tools/whisper.cpp, plus ggml-base.en.bin

This script is intentionally conservative: it reports what it will do, keeps
artifacts inside the selected workspace, and does not require global package
managers.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import urllib.request
import venv
from pathlib import Path


MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin"
WHISPER_CPP_REPO = "https://github.com/ggerganov/whisper.cpp.git"


def is_windows() -> bool:
    return platform.system().lower().startswith("win")


def executable_names(name: str) -> list[str]:
    if is_windows():
        if name.endswith((".exe", ".cmd", ".bat")):
            return [name]
        return [f"{name}.exe", f"{name}.cmd", f"{name}.bat", name]
    return [name]


def workspace_candidates(start: Path) -> list[Path]:
    return [start, *start.parents]


def looks_like_workspace(path: Path) -> bool:
    return (path / "skills" / "knowledge-intake" / "references" / "workspace.json").exists()


def resolve_workspace_root(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    env_value = os.environ.get("KNOWLEDGE_WORKSPACE_ROOT")
    if env_value:
        return Path(env_value).expanduser().resolve()
    for candidate in workspace_candidates(Path.cwd().resolve()):
        if looks_like_workspace(candidate):
            return candidate
    script_path = Path(__file__).resolve()
    for candidate in workspace_candidates(script_path):
        if looks_like_workspace(candidate):
            return candidate
    return Path.cwd().resolve()


def tool_paths(workspace_root: Path, name: str) -> list[Path]:
    paths = []
    for candidate in executable_names(name):
        paths.append(workspace_root / "tools" / "bin" / candidate)
    return paths


def find_tool(workspace_root: Path, name: str) -> str | None:
    for candidate in executable_names(name):
        found = shutil.which(candidate)
        if found:
            return found
    for candidate in tool_paths(workspace_root, name):
        if candidate.exists():
            return str(candidate)
    return None


def model_path(workspace_root: Path) -> Path:
    return workspace_root / "tools" / "whisper.cpp" / "models" / "ggml-base.en.bin"


def report(workspace_root: Path) -> dict[str, object]:
    return {
        "workspace_root": str(workspace_root),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.executable,
        "yt_dlp": find_tool(workspace_root, "yt-dlp"),
        "ffmpeg": find_tool(workspace_root, "ffmpeg"),
        "whisper_cli": find_tool(workspace_root, "whisper-cli"),
        "whisper_model": str(model_path(workspace_root)) if model_path(workspace_root).exists() else None,
    }


def run(command: list[str], cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=str(cwd) if cwd else None, check=True)


def ensure_venv(venv_dir: Path) -> Path:
    if not (venv_dir / ("Scripts" if is_windows() else "bin")).exists():
        venv.create(venv_dir, with_pip=True)
    return venv_dir


def venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts" if is_windows() else "bin") / ("python.exe" if is_windows() else "python")


def bin_dir(workspace_root: Path) -> Path:
    path = workspace_root / "tools" / "bin"
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_wrapper(workspace_root: Path, name: str, target: Path) -> Path:
    destination = bin_dir(workspace_root) / (f"{name}.cmd" if is_windows() else name)
    if is_windows():
        destination.write_text(f'@echo off\r\n"{target}" %*\r\n', encoding="utf-8")
    else:
        destination.write_text(f'#!/usr/bin/env sh\nexec "{target}" "$@"\n', encoding="utf-8")
        destination.chmod(destination.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return destination


def install_yt_dlp(workspace_root: Path) -> Path:
    venv_dir = ensure_venv(workspace_root / "tools" / "youtube" / "venv")
    py = venv_python(venv_dir)
    run([str(py), "-m", "pip", "install", "--upgrade", "pip", "yt-dlp"])
    target = venv_dir / ("Scripts" if is_windows() else "bin") / ("yt-dlp.exe" if is_windows() else "yt-dlp")
    return make_wrapper(workspace_root, "yt-dlp", target)


def install_ffmpeg(workspace_root: Path) -> Path:
    venv_dir = ensure_venv(workspace_root / "tools" / "ffmpeg" / "venv")
    py = venv_python(venv_dir)
    run([str(py), "-m", "pip", "install", "--upgrade", "pip", "imageio-ffmpeg"])
    completed = subprocess.run(
        [str(py), "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"],
        text=True,
        capture_output=True,
        check=True,
    )
    return make_wrapper(workspace_root, "ffmpeg", Path(completed.stdout.strip()))


def locate_whisper_binary(workspace_root: Path) -> Path | None:
    root = workspace_root / "tools" / "whisper.cpp"
    names = executable_names("whisper-cli") + executable_names("main")
    for base in [
        root / "build" / "bin",
        root / "build" / "bin" / "Release",
        root / "build" / "Release",
        root,
    ]:
        for name in names:
            candidate = base / name
            if candidate.exists():
                return candidate
    return None


def install_whisper_cpp(workspace_root: Path, jobs: int) -> Path:
    root = workspace_root / "tools" / "whisper.cpp"
    if not root.exists():
        if not shutil.which("git"):
            raise RuntimeError("git is required to clone whisper.cpp when it is not already present")
        run(["git", "clone", "--depth", "1", WHISPER_CPP_REPO, str(root)])
    if not shutil.which("cmake"):
        raise RuntimeError("cmake is required to build whisper.cpp")
    build_dir = root / "build"
    run(["cmake", "-S", str(root), "-B", str(build_dir), "-DWHISPER_BUILD_TESTS=OFF"])
    run(["cmake", "--build", str(build_dir), "--config", "Release", "-j", str(jobs)])
    binary = locate_whisper_binary(workspace_root)
    if not binary:
        raise RuntimeError("whisper.cpp built, but no whisper-cli/main binary was found")
    return make_wrapper(workspace_root, "whisper-cli", binary)


def ensure_model(workspace_root: Path) -> Path:
    path = model_path(workspace_root)
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(MODEL_URL, headers={"User-Agent": "LocalKnowledgeIntake/1.0"})
    with urllib.request.urlopen(request, timeout=300) as response:
        with path.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root")
    parser.add_argument("--check", action="store_true", help="Only print detected tools")
    parser.add_argument("--yes", action="store_true", help="Perform downloads/installs without an interactive prompt")
    parser.add_argument("--skip-whisper-cpp", action="store_true")
    parser.add_argument("--jobs", type=int, default=max(os.cpu_count() or 2, 2))
    args = parser.parse_args()

    workspace_root = resolve_workspace_root(args.workspace_root)
    before = report(workspace_root)
    if args.check:
        print(json.dumps(before, indent=2))
        return 0

    if not args.yes:
        print(json.dumps(before, indent=2))
        print("Re-run with --yes to install missing workspace-local tools.")
        return 2

    if not find_tool(workspace_root, "yt-dlp"):
        install_yt_dlp(workspace_root)
    if not find_tool(workspace_root, "ffmpeg"):
        install_ffmpeg(workspace_root)
    if not args.skip_whisper_cpp and not find_tool(workspace_root, "whisper-cli"):
        install_whisper_cpp(workspace_root, args.jobs)
    if not args.skip_whisper_cpp:
        ensure_model(workspace_root)

    print(json.dumps(report(workspace_root), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
