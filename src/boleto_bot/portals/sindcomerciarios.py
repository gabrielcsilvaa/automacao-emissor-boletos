# src/boleto_bot/portals/sindcomerciarios.py

from __future__ import annotations

from selenium.webdriver.common.by import By
import time

from ..domain.models import BoletoRequest
from ..domain.enums import SINDICATOS
from ..portals.base import PortalBase, PortalResult
from ..automation.errors import (
    PageLoadError,
    ContributionGenerationError,
    BoletoNotAvailableError,
)

CONTRIBUICAO_VALUE_MAP = {
    "Contribuição Negocial": "CAS",
    "Mensalidade de associados da empresa": "MEN",
    "Taxa saúde do empregado": "TSE",
    "Acordo de abertura nos feriados": "ACR",
}


def _format_valor(valor) -> str:
    try:
        s = f"{valor:.2f}"
    except Exception:
        s = str(valor)
    return s.replace(".", ",")


class SindComerciariosPortal(PortalBase):
    """
    Portal do SindComerciários (CE).

    📌 IMPORTANTE:
    - XPath/CSS selectors entram SOMENTE aqui dentro.
    - O FlowRunner não sabe nada de XPath.
    """

    # =========================
    # 1) Identidade do portal
    # =========================

    @property       
    def key(self) -> str:
        return "SINDCOMERCIARIOS_CE"

    @property
    def base_url(self) -> str:
        info = SINDICATOS[self.key]
        if not info.url_base:
            raise ValueError(f"Sem url_base cadastrada para {self.key}")
        return info.url_base


    def open_home(self) -> None:
        try:
            self.driver.get(self.base_url)
        except Exception as e:
            raise PageLoadError(
                message="Não consegui abrir o site do sindicato.",
                details=f"url={self.base_url} err={e}",
            )
            
        homeEmpresa = '//*[@id="E"]'
        self._click(By.XPATH, homeEmpresa)
   

    def login(self, request: BoletoRequest) -> None:
        
        inputDocumento = '//*[@id="content"]/div/form/input[4]'
        self._type(By.XPATH, inputDocumento, request.cnpj)

        inputSenha = '//*[@id="content"]/div/form/input[5]'
        self._type(By.XPATH, inputSenha, request.senha)
        time.sleep(2)

        btnOk = '//*[@id="OK"]'
        self._click(By.XPATH, btnOk)
        time.sleep(1)

        return

    def gerar_contribuicao(self, request: BoletoRequest) -> None:

        btnGerarContribuicao = '//*[@id="menubv"]/li[4]/a'
        self._click(By.XPATH, btnGerarContribuicao)
        time.sleep(1)

        contribuicaoSelect = '//*[@id="con"]'
        try:
            contribuicao_value = CONTRIBUICAO_VALUE_MAP[request.tipo_contribuicao]
        except KeyError:
            raise ContributionGenerationError(
            message="Tipo de contribuição não mapeado para este sindicato.",
            details=f"tipo_contribuicao={request.tipo_contribuicao}",
        )

        self._select_by_value(By.XPATH, contribuicaoSelect, contribuicao_value)
        time.sleep(2)

        anoSelect = '//*[@id="ano"]'
        self._select_by_value(By.XPATH, anoSelect, str(request.competencia.ano))
        time.sleep(2)


        mesSelect = '//*[@id="mes"]'
        self._select_by_value(By.XPATH, mesSelect, str(request.competencia.mes))
        time.sleep(2)

        inputValor = '//*[@id="load_valor"]/input'
        self._type(By.XPATH, inputValor, _format_valor(request.valor))
        time.sleep(1)

        btnOkGerar = '//*[@id="OK"]'
        self._handles_before_boleto = self.driver.window_handles[:]
        self._click(By.XPATH, btnOkGerar)
        time.sleep(2)

        return

    def obter_boleto(self) -> PortalResult:
        try:
            old_handles = self._handles_before_boleto  # agora existe

            # tenta trocar pra nova aba e garante URL v?lida
            self._switch_to_boleto_context(old_handles, timeout_s=30)
        
            btnImprimir = '/html/body/app-root[1]/app-invoices/app-invoice-payment/div/div[3]/app-invoice-payment-boleto/div[6]/div[3]/button'
            self._click(By.XPATH, btnImprimir, timeout_s=30)

            # Nesse portal, o clique dispara o download; o FlowRunner
            # vai esperar o PDF aparecer na pasta de downloads.
            return PortalResult(
                sucesso=True,
                boleto_url=self.driver.current_url,
            )

        except Exception as e:
            raise BoletoNotAvailableError(
                message="Falha ao abrir a guia do boleto ou clicar para baixar.",
                details=f"url={self.driver.current_url} handles={self.driver.window_handles} err={e}",
            )

    def close(self) -> None:
        """
        Se esse portal abrir popup/aba extra, você fecha aqui.
        (por enquanto pode ficar vazio)
        """
        return
