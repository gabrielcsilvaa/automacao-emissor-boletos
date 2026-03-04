from __future__ import annotations

import argparse

from boleto_bot.automation.flow_runner import FlowRunner, FlowRunnerOptions
from boleto_bot.config.settings import Settings
from boleto_bot.domain.enums import TipoContribuicao
from boleto_bot.domain.validators import BatchValidationError, validar_e_montar_requests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Abre a interface gráfica (CustomTkinter).",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Fluxo completo (quando estiver pronto): gera e baixa PDF.",
    )
    parser.add_argument(
        "--pause",
        action="store_true",
        help="Pausa no final pra voce ver o navegador.",
    )
    args = parser.parse_args()

    if args.ui:
        try:
            from boleto_bot.ui.app import run as run_ui
        except ModuleNotFoundError as exc:
            if exc.name == "customtkinter":
                print("Dependência ausente: customtkinter. Instale com: pip install customtkinter")
                return
            raise
        run_ui()
        return

    settings = Settings.from_env()

    requests_payload = [
        {
            "sindicato_key": "SINDGASTRO_CE",
            "tipo_contribuicao": TipoContribuicao.CONTRIBUICAO_ASSOCIATIVA.value,
            "cnpj": "06323147000107",
            "senha": "06323147",
            "valor": "152,25",
            "ano": 2026,
            "mes": 2,
        },
    ]

    try:
        requests = validar_e_montar_requests(
            requests_payload,
            ordenar_por_sindicato=True,
        )
    except BatchValidationError as exc:
        print("Erros de validacao no lote:")
        for idx, item_errors in exc.errors.items():
            print(f"  - request[{idx}] -> {item_errors}")
        return

    options = FlowRunnerOptions(
        stop_after=None,
        group_by_sindicato=True,
        pause_after=args.pause,
    )

    report = FlowRunner(settings, options=options).run(requests)
    print("Resumo:", report.summary_dict())

    for item in report.items:
        print(f"\n[{item.status}] {item.message}")
        if item.request:
            print("Request:", item.request)
