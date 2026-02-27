from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Dict, Type

from ..domain.enums import SINDICATOS
from ..portals.base import PortalBase


@dataclass(frozen=True)
class PortalRef:
    """
    Referência (string) para uma classe de portal.

    Exemplo:
      module_path = "boleto_bot.portals.sindcomerciarios"
      class_name  = "SindComerciariosPortal"
    """
    module_path: str
    class_name: str


# ✅ Mapa: sindicato_key -> (módulo + classe)
# OBS: Aqui NÃO tem XPath. É só um "endereçamento" do portal certo.
PORTAL_REGISTRY: Dict[str, PortalRef] = {
    "SINDCOMERCIARIOS_CE": PortalRef(
        module_path="boleto_bot.portals.sindcomerciarios",
        class_name="SindComerciariosPortal",
    ),
    # "SINDHOTELARIA_CE": PortalRef(
    #     module_path="boleto_bot.portals.sindhotelaria",
    #     class_name="SindHotelariaPortal",
    # ),
    "SINDGASTRO_CE": PortalRef(
        module_path="boleto_bot.portals.sindgastro",
        class_name="SindGastroPortal",
    ),
}


def get_portal_class(sindicato_key: str) -> Type[PortalBase]:
    """
    Dada a key do sindicato (ex.: "SINDCOMERCIARIOS_CE"),
    encontra e retorna a CLASSE do portal correspondente.

    Isso permite que o flow_runner faça:
      portal_cls = get_portal_class(req.sindicato_key)
      portal = portal_cls(browser)
    """
    key = (sindicato_key or "").strip()

    # 1) Valida se o sindicato existe no catálogo (enums.py)
    if key not in SINDICATOS:
        raise ValueError(f"Sindicato inválido: {key}")

    # 2) Verifica se existe implementação de portal registrada
    ref = PORTAL_REGISTRY.get(key)
    if not ref:
        raise ValueError(
            f"Não existe portal implementado/registrado para o sindicato: {key}"
        )

    # 3) Importa o módulo dinamicamente
    module = importlib.import_module(ref.module_path)

    # 4) Pega a classe dentro do módulo
    cls = getattr(module, ref.class_name, None)
    if cls is None:
        raise ImportError(
            f"Classe {ref.class_name} não encontrada em {ref.module_path}"
        )

    # 5) Garante que a classe realmente é um PortalBase
    if not issubclass(cls, PortalBase):
        raise TypeError(
            f"{ref.class_name} deve herdar de PortalBase"
        )

    return cls
