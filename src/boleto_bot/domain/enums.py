from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class TipoContribuicao(str, Enum):
    TAXA_SAUDE_EMPREGADO = "Taxa saúde do empregado"
    CONTRIBUICAO_NEGOCIAL = "Contribuição Negocial"
    MENSALIDADE_ASSOCIADOS_EMPRESA = "Mensalidade de associados da empresa"
    ACORDO_ABERTURA_FERIADOS = "Acordo de abertura nos feriados"
    CONTRIBUICAO_ASSISTENCIAL_NAO_SOCIO = "Contribuição Assistencial - Não Sócio"
    CONTRIBUICAO_ASSOCIATIVA = "CONTRIBUIÇÃO ASSOCIATIVA"
    TAXA_MEDICA_EMPRESA = "Taxa Médica - EMPRESA"
    CONTRIBUICAO_CONFEDERATIVA_NEGOCIAL = "Contribuição Confederativa Negocial"

@dataclass(frozen=True)
class SindicatoInfo:
    key: str
    nome: str
    url_base: Optional[str] = None  # você pode preencher depois


SINDICATOS: Dict[str, SindicatoInfo] = {
    "SINDCOMERCIARIOS_CE": SindicatoInfo(
        key="SINDCOMERCIARIOS_CE",
        nome="SindComerciários (CE)",
        url_base="https://sweb.diretasistemas.com.br/prosindweb/index.php?sind=697",  
    ),
    # "SINDHOTELARIA_CE": SindicatoInfo(
    #     key="SINDHOTELARIA_CE",
    #     nome="SindHotelaria (CE)",
    #     url_base="https://sweb.diretasistemas.com.br/prosindweb/index.php?sind=1790", 
    # ),
    "SINDGASTRO_CE": SindicatoInfo(
        key="SINDGASTRO_CE",
        nome="SindGastro (CE)",
        url_base="https://sweb.diretasistemas.com.br/prosindweb/index.php?sind=1784", 
    ),
}


SINDICATO_TIPOS_CONTRIBUICAO: Dict[str, List[TipoContribuicao]] = {
    "SINDCOMERCIARIOS_CE": [
        TipoContribuicao.CONTRIBUICAO_NEGOCIAL,
        TipoContribuicao.MENSALIDADE_ASSOCIADOS_EMPRESA,
        TipoContribuicao.TAXA_SAUDE_EMPREGADO,
        TipoContribuicao.ACORDO_ABERTURA_FERIADOS,
    ],
    "SINDGASTRO_CE": [
        TipoContribuicao.CONTRIBUICAO_ASSISTENCIAL_NAO_SOCIO,
        TipoContribuicao.CONTRIBUICAO_ASSOCIATIVA,
        TipoContribuicao.TAXA_MEDICA_EMPRESA,
        TipoContribuicao.CONTRIBUICAO_CONFEDERATIVA_NEGOCIAL,
    ],
}


def listar_sindicatos() -> List[SindicatoInfo]:
    """Retorna a lista de sindicatos cadastrados (útil pra UI)."""
    return list(SINDICATOS.values())


def listar_tipos_contribuicao() -> List[str]:
    """Retorna as descrições dos tipos (útil pra dropdown)."""
    return [t.value for t in TipoContribuicao]


def listar_tipos_por_sindicato(sindicato_key: str) -> List[str]:
    """Retorna os tipos permitidos para um sindicato."""
    return [t.value for t in SINDICATO_TIPOS_CONTRIBUICAO.get(sindicato_key, [])]
