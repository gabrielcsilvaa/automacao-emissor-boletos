from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ..config.settings import Settings


class BoletoHistoryService:
    def __init__(self, settings: Settings) -> None:
        self._path = Path(settings.STORAGE_ROOT) / "historico_boletos.json"

    def load(self) -> list[dict]:
        if not self._path.exists():
            return []

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        if not isinstance(raw, list):
            return []

        return [item for item in raw if isinstance(item, dict)]

    def save_many(self, payloads: Iterable[dict]) -> int:
        current = self.load()
        by_key = {self._make_key(item): item for item in current if self._make_key(item)}

        for payload in payloads:
            cleaned = self._clean(payload)
            key = self._make_key(cleaned)
            if key:
                by_key[key] = cleaned

        items = list(by_key.values())
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return len(items)

    def _clean(self, payload: dict) -> dict:
        return {
            "sindicato_key": str(payload.get("sindicato_key", "")),
            "tipo_contribuicao": str(payload.get("tipo_contribuicao", "")),
            "cnpj": str(payload.get("cnpj", "")),
            "senha": str(payload.get("senha", "")),
            "valor": str(payload.get("valor", "")),
            "ano": str(payload.get("ano", "")),
            "mes": str(payload.get("mes", "")),
        }

    def _make_key(self, payload: dict) -> tuple[str, str, str, str, str] | None:
        cnpj = "".join(ch for ch in str(payload.get("cnpj", "")) if ch.isdigit())
        if not cnpj:
            return None

        return (
            str(payload.get("sindicato_key", "")),
            str(payload.get("tipo_contribuicao", "")),
            cnpj,
            str(payload.get("ano", "")),
            str(payload.get("mes", "")),
        )
