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
    key = (sindicato_key or "").strip()

    if key not in SINDICATOS:
        raise ValueError(f"Sindicato inválido: {key}")

    ref = PORTAL_REGISTRY.get(key)
    if not ref:
        raise ValueError(
            f"Não existe portal implementado/registrado para o sindicato: {key}"
        )

    module = importlib.import_module(ref.module_path)

    cls = getattr(module, ref.class_name, None)
    if cls is None:
        raise ImportError(
            f"Classe {ref.class_name} não encontrada em {ref.module_path}"
        )

    if not issubclass(cls, PortalBase):
        raise TypeError(
            f"{ref.class_name} deve herdar de PortalBase"
        )

    return cls
