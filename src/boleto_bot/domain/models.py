from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .enums import TipoContribuicao


@dataclass(frozen=True)
class Competencia:
    ano: int
    mes: int  # 1..12

    def __post_init__(self) -> None:
        if self.ano < 2000 or self.ano > 2100:
            raise ValueError("Ano fora do intervalo esperado (2000..2100).")
        if self.mes < 1 or self.mes > 12:
            raise ValueError("Mês inválido. Use 1..12.")

    @property
    def yyyymm(self) -> str:
        return f"{self.ano:04d}-{self.mes:02d}"


@dataclass(frozen=True)
class BoletoRequest:

    sindicato_key: str               
    tipo_contribuicao: TipoContribuicao
    cnpj: str                          # pode vir com máscara; normaliza depois no validators
    senha: str                         # não logar isso
    valor: Decimal                     # valor monetário (use Decimal, não float)
    competencia: Competencia           # ano + mês


    def competencia_tag(self) -> str:
        return self.competencia.yyyymm

    def tipo_tag(self) -> str:

        return (
            self.tipo_contribuicao.value.strip()
            .upper()
            .replace("Ç", "C")
            .replace("Ã", "A")
            .replace("Á", "A")
            .replace("Â", "A")
            .replace("É", "E")
            .replace("Ê", "E")
            .replace("Í", "I")
            .replace("Ó", "O")
            .replace("Ô", "O")
            .replace("Õ", "O")
            .replace("Ú", "U")
            .replace(" ", "_")
        )

    def safe_log_dict(self) -> dict:
        """
        Retorna um dicionário seguro para logs/relatórios (sem senha).
        """
        return {
            "sindicato_key": self.sindicato_key,
            "tipo_contribuicao": self.tipo_contribuicao.value,
            "cnpj": _mask_cnpj(self.cnpj),
            "valor": str(self.valor),
            "competencia": self.competencia.yyyymm,
        }


def _mask_cnpj(cnpj: str) -> str:

    digits = "".join(ch for ch in (cnpj or "") if ch.isdigit())
    if len(digits) < 6:
        return "****"
    return f"{digits[:2]}**********{digits[-2:]}"
