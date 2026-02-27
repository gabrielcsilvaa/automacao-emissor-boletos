
from __future__ import annotations

from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse
import base64
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

def _norm_text(text: str) -> str:
    return " ".join((text or "").replace("\u00A0", " ").split())

def _format_valor(valor) -> str:
    try:
        s = f"{valor:.2f}"
    except Exception:
        s = str(valor)
    return s.replace(".", ",")

def _normalize_bloqueto_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.path.endswith("bloqueto.php"):
        return url

    qs = parse_qs(parsed.query, keep_blank_values=True)
    target = (qs.pop("p", [None])[0] or "").strip()
    if not target:
        return url

    qs.pop("valor", None)
    new_query = urlencode({k: v[0] for k, v in qs.items()}, doseq=True)
    base = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    return urljoin(base, target) + (f"?{new_query}" if new_query else "")


class SindGastroPortal(PortalBase):
    """
    Portal do SindGastro (CE).

    📌 IMPORTANTE:
    - XPath/CSS selectors entram SOMENTE aqui dentro.
    - O FlowRunner não sabe nada de XPath.
    """

    # =========================
    # 1) Identidade do portal
    # =========================

    @property
    def key(self) -> str:
        return "SINDGASTRO_CE"

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

        btnContribuicoes = '//*[@id="menubv"]/li[3]/a'  
        self._click(By.XPATH, btnContribuicoes)
        time.sleep(1)

        tbody_xpath = '//*[@id="content"]/table[1]/tbody'
        self._wait(30).until(EC.presence_of_element_located((By.XPATH, tbody_xpath)))
        rows = self.driver.find_elements(By.XPATH, f"{tbody_xpath}/tr")

        reqTipo = _norm_text(request.tipo_contribuicao.value)
        reqMes = f"{request.competencia.mes:02d}"
        reqAno = str(request.competencia.ano)

        for idx in range(1, len(rows) + 1):
            tipoText = _norm_text(self._get_text(By.XPATH, f"{tbody_xpath}/tr[{idx}]/th[1]"))
            if tipoText.lower() == "tipo":
                continue

            anoText = _norm_text(self._get_text(By.XPATH, f"{tbody_xpath}/tr[{idx}]/th[2]"))
            mesText = _norm_text(self._get_text(By.XPATH, f"{tbody_xpath}/tr[{idx}]/th[3]"))

            if tipoText == reqTipo and anoText == reqAno and mesText == reqMes:
                try:
                    imprimir_xpath = f'{tbody_xpath}/tr[{idx}]//a[contains(., "Imprimir")]'
                    imprimir_el = self._wait(30).until(
                        EC.presence_of_element_located((By.XPATH, imprimir_xpath))
                    )
                    href = imprimir_el.get_attribute("href") or ""
                    self._boleto_url = _normalize_bloqueto_url(urljoin(self.base_url, href))
                except Exception as e:
                    raise ContributionGenerationError(
                        message="Não consegui ler o link de Imprimir para a contribuição selecionada.",
                        details=f"tipo={tipoText} mes={mesText} ano={anoText} err={e}",
                    )
                self._handles_before_boleto = list(self.driver.window_handles)
                self._preencher_valor_e_confirmar(request)
                return

        raise ContributionGenerationError(
            message="Não encontrei a contribuição/competência solicitada na tabela.",
            details=f"tipo={reqTipo} mes={reqMes} ano={reqAno}",
        )

    def _preencher_valor_e_confirmar(self, request: BoletoRequest) -> None:
        valorStr = _format_valor(request.valor)

        try:
            self._type(By.XPATH, '//*[@id="valor"]', valorStr, timeout_s=30)
        except Exception as e:
            raise ContributionGenerationError(
                message="Não encontrei o campo de valor na página de alteração.",
                details=f"valor={valorStr} err={e}",
            )

        self._handles_before_boleto = list(self.driver.window_handles)
        try:
            self._click(By.XPATH, '//*[@id="OK"]', timeout_s=30)
        except Exception as e:
            raise ContributionGenerationError(
                message="Não consegui clicar no botão OK para confirmar o valor.",
                details=f"valor={valorStr} err={e}",
            )

        # popup de confirmação (jconfirm)
        try:
            popupXpath = '/html/body/div[2]/div[2]/div/div/div/div/div/div/div'
            confirmXpath = '/html/body/div[2]/div[2]/div/div/div/div/div/div/div/div[4]/button[1]'
            self._wait(30).until(EC.presence_of_element_located((By.XPATH, popupXpath)))
            self._click(By.XPATH, confirmXpath, timeout_s=30)
        except Exception as e:
            raise ContributionGenerationError(
                message="Popup de confirmação não apareceu ou não consegui clicar em CONFIRMA.",
                details=f"valor={valorStr} err={e}",
            )

    def obter_boleto(self) -> PortalResult:
        try:
            boleto_url = getattr(self, "_boleto_url", None)
            if boleto_url:
                self.driver.get(boleto_url)
            else:
                old_handles = self._handles_before_boleto  # agora existe
                # tenta trocar pra nova aba e garante URL válida
                self._switch_to_boleto_context(old_handles, timeout_s=30)

            self._wait(30).until(lambda d: "bloqueto.php" in (d.current_url or ""))
            self._wait(30).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            try:
                self.driver.execute_script(
                    "window.print = () => {}; window.onbeforeprint = null; window.onafterprint = null;"
                )
            except Exception:
                pass

            pdf = self.driver.execute_cdp_cmd(
                "Page.printToPDF",
                {"printBackground": True, "preferCSSPageSize": True},
            )
            pdf_bytes = base64.b64decode(pdf.get("data", ""))
            
            return PortalResult(
                sucesso=True,
                boleto_pdf_bytes=pdf_bytes,
                boleto_url=self.driver.current_url,
            )

        except Exception as e:
            raise BoletoNotAvailableError(
                message="Falha ao abrir/gerar o boleto em PDF.",
                details=f"url={self.driver.current_url} boleto_url={getattr(self, '_boleto_url', None)} handles={self.driver.window_handles} err={e}",
            )

    def close(self) -> None:
        """
        Se esse portal abrir popup/aba extra, você fecha aqui.
        (por enquanto pode ficar vazio)
        """
        return
