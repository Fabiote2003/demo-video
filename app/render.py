import json
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WM_W, WM_X, WM_Y, WM_ALPHA = 400, 72, 44, 0.93
TOPE_MB, OBJETIVO_MB, AUDIO_KBPS = 15, 14.5, 64
PLATE_TIMEOUT_S = 180
ENCODE_TIMEOUT_S = 1200


class RenderError(Exception):
    pass


class LogoError(Exception):
    pass


def logo_kind(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def prepare_logo(data: bytes, kind: str) -> tuple[bytes, str]:
    suffix = {"png": ".png", "jpeg": ".jpg", "webp": ".webp"}[kind]
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"logo{suffix}"
        src.write_bytes(data)
        try:
            if kind == "webp":
                png = Path(tmp) / "logo.png"
                _run(
                    ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-i", str(src), "-y", str(png)],
                    Path(tmp),
                    30,
                )
                src = png
            _dimensions(src)
        except RenderError as exc:
            raise LogoError("No pudimos leer el logo") from exc
        return src.read_bytes(), src.suffix


def render_demo(
    *,
    club: str,
    logo_path: Path,
    output_path: Path,
    base_path: Path,
    remotion_dir: Path,
) -> None:
    if not base_path.is_file():
        raise RenderError("No está el video base")
    work = output_path.parent / "work"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    public_name = f"{output_path.parent.name}{logo_path.suffix.lower()}"
    public_logo = remotion_dir / "public" / "logos" / public_name
    public_logo.parent.mkdir(parents=True, exist_ok=True)
    intro = work / "intro.mp4"
    badge = work / "badge.png"
    try:
        shutil.copyfile(logo_path, public_logo)
        width, height = _dimensions(logo_path)
        props = json.dumps(
            {"club": club, "logo": f"logos/{public_name}", "logoW": width, "logoH": height},
            ensure_ascii=False,
        )
        linux = ["--enable-multiprocess-on-linux"] if sys.platform == "linux" else []
        npx = "npx.cmd" if sys.platform == "win32" else "npx"
        _run(
            [
                npx, "remotion", "render", "src/index.jsx", "Intro", str(intro),
                "--codec=h264", "--pixel-format=yuv420p", "--log=error", f"--props={props}", *linux,
            ],
            remotion_dir,
            PLATE_TIMEOUT_S,
        )
        _run(
            [
                npx, "remotion", "still", "src/index.jsx", "Badge", str(badge),
                "--image-format=png", "--log=error", f"--props={props}", *linux,
            ],
            remotion_dir,
            PLATE_TIMEOUT_S,
        )
        _assemble(intro, badge, base_path, output_path, work)
        mb = output_path.stat().st_size / 1024 / 1024
        if mb > TOPE_MB:
            output_path.unlink(missing_ok=True)
            raise RenderError("El video pasó el tope de 15 MB")
    finally:
        public_logo.unlink(missing_ok=True)
        shutil.rmtree(work, ignore_errors=True)


def _assemble(intro: Path, badge: Path, base: Path, output: Path, work: Path) -> None:
    intro_s = _duration(intro)
    kbps = int(OBJETIVO_MB * 8 * 1024 * 1024 / (intro_s + _duration(base)) / 1000) - AUDIO_KBPS
    if kbps < 50:
        raise RenderError("No se pudo armar el video")
    graph = ";".join(
        [
            f"[2:v]scale={WM_W}:-1,format=rgba,colorchannelmixer=aa={WM_ALPHA}[wm]",
            f"[1:v][wm]overlay={WM_X}:H-h-{WM_Y}:format=auto[basev]",
            "[0:v]scale=1920:1080:in_range=full:out_range=tv,format=yuv420p,setsar=1,fps=30[introv]",
            f"anullsrc=channel_layout=stereo:sample_rate=48000,atrim=0:{intro_s:.3f},asetpts=PTS-STARTPTS[introa]",
            "[introv][introa][basev][1:a]concat=n=2:v=1:a=1[vo][ao]",
        ]
    )
    shared = [
        "ffmpeg", "-nostdin", "-hide_banner", "-v", "error",
        "-i", str(intro), "-i", str(base), "-i", str(badge),
        "-filter_complex", graph, "-map", "[vo]", "-map", "[ao]",
        "-c:v", "libx264", "-preset", "slow", "-b:v", f"{kbps}k", "-pix_fmt", "yuv420p",
        "-passlogfile", str(work / "pass"),
        "-c:a", "aac", "-b:a", f"{AUDIO_KBPS}k", "-ac", "1", "-r", "30",
    ]
    _run([*shared, "-pass", "1", "-f", "mp4", "-y", str(work / "pass1.mp4")], work, ENCODE_TIMEOUT_S)
    _run([*shared, "-pass", "2", "-movflags", "+faststart", "-y", str(output)], work, ENCODE_TIMEOUT_S)


def _duration(path: Path) -> float:
    try:
        return float(
            _ffprobe(["-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
        )
    except (RenderError, ValueError) as exc:
        raise RenderError("No se pudo armar el video") from exc


def _dimensions(path: Path) -> tuple[int, int]:
    raw = _ffprobe(
        [
            "-select_streams", "v:0", "-show_entries", "stream=width,height",
            "-of", "csv=p=0:s=x", str(path),
        ]
    )
    try:
        width, height = (int(value) for value in raw.split("x")[:2])
    except ValueError as exc:
        raise RenderError("No pudimos leer el logo") from exc
    if width <= 0 or height <= 0:
        raise RenderError("No pudimos leer el logo")
    return width, height


def _ffprobe(args: list[str]) -> str:
    completed = subprocess.run(
        ["ffprobe", "-v", "error", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise RenderError("No pudimos leer el logo")
    return completed.stdout.strip()


def _run(args: list[str], cwd: Path, timeout: int) -> None:
    logging.info("%s", " ".join(args[:4]))
    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RenderError("El armado del video excedió el tiempo") from exc
    if completed.returncode != 0:
        logging.error("%s", (completed.stderr or completed.stdout)[-2000:])
        raise RenderError("No se pudo armar el video")
