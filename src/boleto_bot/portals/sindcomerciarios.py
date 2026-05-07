from __future__ import annotations

import base64
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
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
            old_handles = self._handles_before_boleto

            self._switch_to_checkout_context(old_handles, timeout_s=45)
        
            btnBoleto = '/html/body/app-root[1]/app-invoice-wrapper/app-layout/div/main/app-invoices-v2/div/div/div[2]/div[2]/app-payment-methods/div/app-card/div/div[2]/div[1]/div[2]'
            self._click_xpath_js(btnBoleto, "opcao Boleto", timeout_s=30)

            btnGerarBoleto = '/html/body/app-root[1]/app-invoice-wrapper/app-layout/div/main/app-invoices-v2/div/div/div[2]/div[2]/app-payment-methods/div/app-card/div/div[2]/app-button/button'
            self._click_xpath_js(btnGerarBoleto, "botao Gerar Boleto", timeout_s=30)

            self._switch_to_app_boleto_context(timeout_s=45)
            self._wait(30).until(lambda d: d.execute_script("return document.readyState") == "complete")

            pdf_bytes = self._print_current_page_to_pdf()
            self._try_click_imprimir_boleto(timeout_s=5)

            try:
                boleto_url = self.driver.current_url
            except Exception:
                boleto_url = None

            return PortalResult(
                sucesso=True,
                boleto_pdf_bytes=pdf_bytes,
                boleto_url=boleto_url,
            )

        except Exception as e:
            raise BoletoNotAvailableError(
                message="Falha ao abrir/gerar o boleto em PDF.",
                details=f"url={self._safe_current_url()} handles={self._safe_window_handles()} err={e}",
            )

    def _print_current_page_to_pdf(self) -> bytes:
        try:
            self._wait(30).until(lambda d: d.execute_script("return document.readyState") == "complete")
            pdf = self.driver.execute_cdp_cmd(
                "Page.printToPDF",
                {"printBackground": True, "preferCSSPageSize": True},
            )
            return base64.b64decode(pdf.get("data", ""))
        except Exception as e:
            raise RuntimeError(
                "Nao consegui gerar PDF da pagina atual do boleto. "
                f"url={self._safe_current_url()} err={e}"
            )

    def _try_click_imprimir_boleto(self, timeout_s: int = 5) -> None:
        try:
            self._click_imprimir_boleto(timeout_s=timeout_s)
            time.sleep(0.5)
        except Exception:
            # O PDF ja foi capturado da propria tela do boleto. O clique visual
            # pode abrir/fechar a janela de impressao e invalidar o handle.
            return

    def _click_imprimir_boleto(self, timeout_s: int = 30) -> None:
        xpath = '/html/body/app-root[1]/app-boleto/app-layout/div/main/div/div[2]/div[1]/app-card/div/div[3]/div[4]/app-button[1]/button'
        css_host = 'app-boleto app-button[title="Imprimir Boleto"]'
        css_button = f'{css_host} button'

        try:
            button = self._wait(timeout_s).until(lambda d: self._find_imprimir_button(css_button, xpath))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
            time.sleep(0.3)

            try:
                button.click()
                return
            except Exception:
                pass

            try:
                ActionChains(self.driver).move_to_element(button).pause(0.2).click().perform()
                return
            except Exception:
                pass

            clicked = self.driver.execute_script(
                """
                const target = arguments[0];
                const host = target.closest('app-button') || target;
                for (const el of [target, host]) {
                    for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
                        el.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
                    }
                    if (typeof el.click === 'function') el.click();
                }
                return true;
                """,
                button,
            )
            if not clicked:
                raise RuntimeError("fallback js retornou false")
        except Exception as e:
            raise RuntimeError(
                "Nao consegui clicar no botao Imprimir Boleto. "
                f"url={self._safe_current_url()} xpath={xpath} err={e}"
            )

    def _find_imprimir_button(self, css_button: str, xpath: str):
        buttons = self.driver.find_elements(By.CSS_SELECTOR, css_button)
        for button in buttons:
            if button.is_displayed() and button.is_enabled():
                return button

        buttons = self.driver.find_elements(By.XPATH, xpath)
        for button in buttons:
            if button.is_displayed() and button.is_enabled():
                return button

        return False

    def _switch_to_checkout_context(self, old_handles: list[str], timeout_s: int = 45) -> None:
        def _checkout_ready(driver):
            handles = list(driver.window_handles)
            ordered_handles = [h for h in handles if h not in old_handles] + [h for h in handles if h in old_handles]

            for handle in ordered_handles:
                driver.switch_to.window(handle)
                current_url = driver.current_url or ""
                if "app-invoices" in current_url or "app-invoice" in current_url:
                    return True
                try:
                    has_payment_methods = driver.execute_script(
                        "return !!document.querySelector('app-payment-methods');"
                    )
                    if has_payment_methods:
                        return True
                except Exception:
                    pass
            return False

        try:
            self._wait(timeout_s).until(_checkout_ready)
            self._wait(30).until(lambda d: d.execute_script("return document.readyState") == "complete")
            return
        except Exception as e:
            raise RuntimeError(
                "Nao consegui encontrar a tela de pagamento do boleto. "
                f"url={self._safe_current_url()} handles={self._safe_window_handles()} err={e}"
            )

    def _switch_to_app_boleto_context(self, timeout_s: int = 45) -> None:
        def _app_boleto_ready(driver):
            for handle in list(driver.window_handles):
                try:
                    driver.switch_to.window(handle)
                    current_url = driver.current_url or ""
                    if "app-boleto" in current_url or "/boleto/" in current_url:
                        return True
                    has_app_boleto = driver.execute_script("return !!document.querySelector('app-boleto');")
                    if has_app_boleto:
                        return True
                except Exception:
                    continue
            return False

        try:
            self._wait(timeout_s).until(_app_boleto_ready)
            return
        except Exception as e:
            raise RuntimeError(
                "Nao consegui encontrar a tela final app-boleto. "
                f"url={self._safe_current_url()} handles={self._safe_window_handles()} err={e}"
            )

    def _click_xpath_js(self, xpath: str, description: str, timeout_s: int = 30) -> None:
        try:
            self._wait(timeout_s).until(
                lambda d: d.execute_script(
                    """
                    const el = document.evaluate(
                        arguments[0],
                        document,
                        null,
                        XPathResult.FIRST_ORDERED_NODE_TYPE,
                        null
                    ).singleNodeValue;
                    return !!el;
                    """,
                    xpath,
                )
            )
            clicked = self.driver.execute_script(
                """
                const el = document.evaluate(
                    arguments[0],
                    document,
                    null,
                    XPathResult.FIRST_ORDERED_NODE_TYPE,
                    null
                ).singleNodeValue;
                if (!el) return false;
                el.scrollIntoView({block: 'center'});
                for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
                    el.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
                }
                if (typeof el.click === 'function') el.click();
                return true;
                """,
                xpath,
            )
            if not clicked:
                raise RuntimeError("script retornou false")
            time.sleep(0.5)
        except Exception as e:
            raise RuntimeError(
                f"Nao consegui clicar em {description}. "
                f"url={self._safe_current_url()} xpath={xpath} err={e}"
            )

    def _safe_current_url(self) -> str:
        try:
            return self.driver.current_url or ""
        except Exception as e:
            return f"<current_url indisponivel: {e}>"

    def _safe_window_handles(self) -> list[str] | str:
        try:
            return self.driver.window_handles
        except Exception as e:
            return f"<window_handles indisponivel: {e}>"

    def close(self) -> None:
        return
