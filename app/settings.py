import os
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGO_MAX_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class Settings:
    token: str
    base_video: Path
    data_dir: Path
    remotion_dir: Path
    max_queued: int
    ttl_days: int


def _path(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    return Path(raw) if raw else default


def load_settings() -> Settings:
    token = os.environ.get("DEMO_VIDEO_TOKEN", "").strip()
    if not token:
        sys.exit("Falta DEMO_VIDEO_TOKEN")
    return Settings(
        token=token,
        base_video=_path("DEMO_VIDEO_BASE", ROOT / "data" / "quadro_demo_base.mp4"),
        data_dir=_path("DEMO_VIDEO_DATA", ROOT / "data" / "jobs"),
        remotion_dir=_path("DEMO_VIDEO_REMOTION", ROOT / "remotion"),
        max_queued=3,
        ttl_days=7,
    )
