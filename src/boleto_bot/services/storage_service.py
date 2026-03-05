from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config.settings import Settings
from ..domain.models import BoletoRequest, Competencia
from ..domain.validators import cnpj_digits_or_raise
from ..domain.enums import SINDICATOS


@dataclass(frozen=True)
class OutputTarget:
    """
    Resultado do "onde salvar".
    """
    folder: Path
    filename: str
    full_path: Path


class StorageService:
    """
    Responsável por:
    - Criar a árvore: BOLETOS_DIR/<CNPJ>/<AAAA-MM>/
    - Gerar nome de arquivo consistente e seguro
    - Evitar sobrescrever arquivo (gera nome único se já existir)
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings


    def empresa_dir(self, cnpj: str) -> Path:
        """
        Retorna: <BOLETOS_DIR>/<CNPJ_DIGITOS>/
        """
        cnpj_digits = cnpj_digits_or_raise(cnpj)
        return self.settings.BOLETOS_DIR / cnpj_digits

    def competencia_dir(self, cnpj: str, competencia: Competencia) -> Path:
        """
        Retorna: <BOLETOS_DIR>/<CNPJ_DIGITOS>/<AAAA-MM>/
        """
        base = self.empresa_dir(cnpj)
        return base / competencia.yyyymm

    def ensure_dirs(self, cnpj: str, competencia: Competencia) -> Path:
        """
        Garante que a pasta final existe e retorna o Path dela.
        """
        folder = self.competencia_dir(cnpj, competencia)
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    # --------- Nome do arquivo ---------

    def build_filename(
        self,
        request: BoletoRequest,
        ext: str = "pdf",
        include_sindicato: bool = True,
        include_timestamp_if_duplicate: bool = False,
    ) -> str:
        """
        Gera um nome de arquivo "limpo" e previsível.

        Padrão:
          <AAAA-MM>_<TIPO>_<SINDICATO>.pdf

        """
        ext = (ext or "pdf").lstrip(".").lower()

        partes = [
            request.competencia_tag(),   # AAAA-MM
            request.tipo_tag(),          # TIPO_SAFE
        ]

        if include_sindicato:
            sindicato_tag = self._safe_piece(request.sindicato_key)
            partes.append(sindicato_tag)


        base = "_".join([p for p in partes if p])
        filename = f"{base}.{ext}"

        # Opcional: caso você queira sempre colocar timestamp em nome duplicado
        if include_timestamp_if_duplicate:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{base}_{ts}.{ext}"

        return filename

    def resolve_output(
        self,
        request: BoletoRequest,
        ext: str = "pdf",
        avoid_overwrite: bool = True,
    ) -> OutputTarget:
        """
        Retorna pasta + nome + caminho final.
        Por padrão evita sobrescrever arquivo existente.
        """
        folder = self.ensure_dirs(request.cnpj, request.competencia)

        filename = self.build_filename(request, ext=ext)
        full_path = folder / filename

        if avoid_overwrite:
            full_path = self._make_unique(full_path)

        return OutputTarget(folder=folder, filename=full_path.name, full_path=full_path)

    # --------- Helpers internos ---------

    def sindicato_nome(self, sindicato_key: str) -> Optional[str]:
        """
        Retorna o nome amigável do sindicato (se cadastrado em enums.py).
        Útil se você quiser usar no nome do arquivo no futuro.
        """
        info = SINDICATOS.get(sindicato_key)
        return info.nome if info else None

    def _make_unique(self, path: Path) -> Path:
        """
        Se o arquivo já existir, cria um nome incremental:
          arquivo.pdf -> arquivo_002.pdf -> arquivo_003.pdf ...
        """
        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix  # ".pdf"
        parent = path.parent

        i = 2
        while True:
            candidate = parent / f"{stem}_{i:03d}{suffix}"
            if not candidate.exists():
                return candidate
            i += 1

    def _safe_piece(self, text: str) -> str:
        """
        Normaliza um trecho pra ser usado em nome de arquivo:
        - remove acentos comuns
        - troca espaços por underscore
        - remove caracteres proibidos
        - limita tamanho
        """
        s = (text or "").strip().upper()

        # substituições simples de acentos (suficiente pro nosso caso)
        s = (
            s.replace("Ç", "C")
             .replace("Ã", "A").replace("Á", "A").replace("Â", "A")
             .replace("É", "E").replace("Ê", "E")
             .replace("Í", "I")
             .replace("Ó", "O").replace("Ô", "O").replace("Õ", "O")
             .replace("Ú", "U")
        )

        s = s.replace(" ", "_")

        # remove tudo que não seja letra/número/_/-
        s = re.sub(r"[^A-Z0-9_\-]+", "", s)

        # evita underscores repetidos
        s = re.sub(r"_+", "_", s).strip("_")

        # evita nomes gigantes
        return s[:60]
