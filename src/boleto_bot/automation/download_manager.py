from __future__ import annotations

import time
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Set

from ..config.settings import Settings
from ..services.storage_service import OutputTarget
from .errors import DownloadError, SaveFileError


PARTIAL_EXTS = {".crdownload", ".part", ".tmp"}


@dataclass(frozen=True)
class DownloadSnapshot:

    filenames: Set[str]
    taken_at: float  # time.time()


class DownloadManager:

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.download_dir = Path(settings.DOWNLOADS_DIR).expanduser().resolve()
        self.download_dir.mkdir(parents=True, exist_ok=True)


    def snapshot(self) -> DownloadSnapshot:
        filenames = {p.name for p in self.download_dir.iterdir() if p.is_file()}
        return DownloadSnapshot(filenames=filenames, taken_at=time.time())

    def wait_new_pdf(
        self,
        snap: DownloadSnapshot,
        timeout_s: int = 90,
        stable_for_s: float = 1.0,
        poll_interval_s: float = 0.25,
    ) -> Path:
        deadline = time.time() + timeout_s

        while time.time() < deadline:
            new_pdf = self._find_new_pdf(snap)
            if new_pdf is not None:
                self._wait_until_stable(new_pdf, stable_for_s=stable_for_s, timeout_s=timeout_s)
                return new_pdf
            time.sleep(poll_interval_s)

        raise DownloadError(
            message="Download do PDF não apareceu dentro do tempo esperado.",
            details=f"dir={self.download_dir} timeout_s={timeout_s}",
        )

    def move_to_output(self, downloaded_pdf: Path, target: OutputTarget) -> Path:
        try:
            target.folder.mkdir(parents=True, exist_ok=True)

            # move + renomeia
            final_path = Path(target.full_path)
            shutil.move(str(downloaded_pdf), str(final_path))

            return final_path.resolve()

        except Exception as e:
            raise SaveFileError(
                message="Falha ao salvar/mover o PDF para a pasta final.",
                details=f"from={downloaded_pdf} to={target.full_path} err={e}",
            )

    def _find_new_pdf(self, snap: DownloadSnapshot) -> Optional[Path]:
        candidates: list[Path] = []

        for p in self.download_dir.iterdir():
            if not p.is_file():
                continue

            name = p.name
            if name in snap.filenames:
                continue

            if p.suffix.lower() in PARTIAL_EXTS:
                continue

            # quero PDF
            if p.suffix.lower() != ".pdf":
                continue

            candidates.append(p)

        if not candidates:
            return None

        candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return candidates[0]

    def _wait_until_stable(self, path: Path, stable_for_s: float, timeout_s: int) -> None:
  
        deadline = time.time() + timeout_s
        last_size = -1
        stable_since: Optional[float] = None

        while time.time() < deadline:
            if self._has_partial_sibling(path):
                stable_since = None
                time.sleep(0.2)
                continue

            try:
                current_size = path.stat().st_size
            except FileNotFoundError:
                stable_since = None
                time.sleep(0.2)
                continue

            if current_size != last_size:
                last_size = current_size
                stable_since = None
            else:
                if stable_since is None:
                    stable_since = time.time()
                elif (time.time() - stable_since) >= stable_for_s:
                    return

            time.sleep(0.2)

        raise DownloadError(
            message="O PDF apareceu, mas não estabilizou (parece que o download não terminou).",
            details=f"path={path}",
        )

    def _has_partial_sibling(self, pdf_path: Path) -> bool:
   
        for ext in PARTIAL_EXTS:
            sibling = pdf_path.with_name(pdf_path.name + ext)
            if sibling.exists():
                return True
        return False
