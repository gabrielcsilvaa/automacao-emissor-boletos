from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _env_str(key: str, default: str) -> str:
    v = os.getenv(key)
    return default if v is None or str(v).strip() == "" else str(v).strip()


def _env_bool(key: str, default: bool) -> bool:
    v = os.getenv(key)
    if v is None:
        return default
    v = v.strip().lower()
    if v in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def _env_int(key: str, default: int) -> int:
    v = os.getenv(key)
    if v is None:
        return default
    try:
        return int(v.strip())
    except ValueError:
        return default


def _default_user_storage_root(app_folder_name: str = "BoletoBot") -> Path:
    home = Path.home()
    desktop = home / "Desktop"
    docs = home / "Documents"
    if desktop.exists():
        base = desktop
    elif docs.exists():
        base = docs
    else:
        base = home
    return (base / app_folder_name).expanduser()


def _default_downloads_tmp_dir(app_folder_name: str = "BoletoBot") -> Path:
    return Path(tempfile.gettempdir()) / app_folder_name / "downloads_tmp"

@dataclass(frozen=True)
class Settings:
    BASE_DIR: Path
    STORAGE_ROOT: Path
    BOLETOS_DIR: Path
    DOWNLOADS_DIR: Path
    LOG_DIR: Optional[Path]

    HEADLESS: bool
    NAV_TIMEOUT_MS: int
    ACTION_TIMEOUT_MS: int
    SLOW_MO_MS: int
    MAX_RETRIES: int

    @staticmethod
    def _default_base_dir() -> Path:
        return Path(__file__).resolve().parents[3]

    @classmethod
    def from_env(cls) -> "Settings":
        base_dir = cls._default_base_dir()
        default_storage_root = _default_user_storage_root("Boletos")  # ou "BoletoBot"
        storage_root_str = _env_str("BOLETOBOT_STORAGE_ROOT", str(default_storage_root))
        storage_root = Path(storage_root_str).expanduser().resolve()

        boletos_dir = storage_root
        downloads_dir_str = _env_str(
            "BOLETOBOT_DOWNLOADS_DIR",
            str(_default_downloads_tmp_dir("BoletoBot")),
        )
        downloads_dir = Path(downloads_dir_str).expanduser().resolve()


        settings = cls(
            BASE_DIR=base_dir,
            STORAGE_ROOT=storage_root,
            BOLETOS_DIR=boletos_dir,
            DOWNLOADS_DIR=downloads_dir,
            HEADLESS=_env_bool("BOLETOBOT_HEADLESS", False),
            NAV_TIMEOUT_MS=_env_int("BOLETOBOT_NAV_TIMEOUT_MS", 60_000),
            ACTION_TIMEOUT_MS=_env_int("BOLETOBOT_ACTION_TIMEOUT_MS", 30_000),
            SLOW_MO_MS=_env_int("BOLETOBOT_SLOW_MO_MS", 0),
            MAX_RETRIES=_env_int("BOLETOBOT_MAX_RETRIES", 0),
        )

        settings.ensure_dirs()
        return settings

    def ensure_dirs(self) -> None:
        self.STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
        self.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        if self.LOG_DIR is not None:
            self.LOG_DIR.mkdir(parents=True, exist_ok=True)
