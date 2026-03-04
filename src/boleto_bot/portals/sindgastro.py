from __future__ import annotations

import base64
import os
import time
import unicodedata
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from ..automation.errors import (
    BoletoNotAvailableError,
    ContributionGenerationError,
    PageLoadError,
)
from ..domain.enums import SINDICATOS
from ..domain.models import BoletoRequest
from ..portals.base import PortalBase, PortalResult


def _norm_text(text: str) -> str:
    return " ".join((text or "").replace("\u00A0", " ").split())


def _norm_key(text: str) -> str:
    lowered = _norm_text(text).casefold()
    folded = unicodedata.normalize("NFD", lowered)
    return "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")


def _parse_int_from_text(text: str) -> int | None:
    digits = "".join(ch for ch in (text or "") if ch.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


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

def _build_boleto_url_from_altvalor(altvalor_url: str, valor_dot: str) -> str:
    parsed = urlparse(altvalor_url)
    qs = parse_qs(parsed.query, keep_blank_values=True)

    target = (qs.pop("p", [None])[0] or "").strip()
    if not target:
        return _normalize_bloqueto_url(altvalor_url)

    qs["valor"] = [valor_dot]
    new_query = urlencode({k: v[0] for k, v in qs.items()}, doseq=True)
    base = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    return urljoin(base, target) + (f"?{new_query}" if new_query else "")


class SindGastroPortal(PortalBase):
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

        home_empresa = '//*[@id="E"]'
        self._click(By.XPATH, home_empresa)

    def login(self, request: BoletoRequest) -> None:
        input_documento = '//*[@id="content"]/div/form/input[4]'
        self._type(By.XPATH, input_documento, request.cnpj)

        input_senha = '//*[@id="content"]/div/form/input[5]'
        self._type(By.XPATH, input_senha, request.senha)
        time.sleep(2)

        btn_ok = '//*[@id="OK"]'
        self._click(By.XPATH, btn_ok)
        time.sleep(1)

    def gerar_contribuicao(self, request: BoletoRequest) -> None:
        skip_altvalor = os.getenv("BOLETOBOT_SINDGASTRO_SKIP_ALTV", "0") == "1"

        btn_contribuicoes = '//*[@id="menubv"]/li[3]/a'
        self._click(By.XPATH, btn_contribuicoes)
        time.sleep(1)

        tbody_xpath = '//*[@id="content"]/table[1]/tbody'
        req_tipo_key = _norm_key(request.tipo_contribuicao.value)
        req_mes = request.competencia.mes
        req_ano = request.competencia.ano

        matched_idx, tipo_text, ano_text, mes_text = self._find_matching_row(
            tbody_xpath,
            req_tipo_key,
            req_mes,
            req_ano,
        )

        self._capturar_e_clicar_imprimir(
            tbody_xpath,
            matched_idx,
            tipo_text,
            ano_text,
            mes_text,
            expect_altvalor=(not skip_altvalor),
        )
        if skip_altvalor:
            return
        self._preencher_valor_e_confirmar(request)

    def _find_matching_row(
        self,
        tbody_xpath: str,
        req_tipo_key: str,
        req_mes: int,
        req_ano: int,
    ) -> tuple[int, str, str, str]:
        self._wait(30).until(EC.presence_of_element_located((By.XPATH, tbody_xpath)))
        rows = self.driver.find_elements(By.XPATH, f"{tbody_xpath}/tr")

        snapshot: list[str] = []
        for idx in range(1, len(rows) + 1):
            cells = self.driver.find_elements(By.XPATH, f"{tbody_xpath}/tr[{idx}]/*[self::th or self::td]")
            if not cells:
                continue

            tipo_text = _norm_text(cells[0].text if len(cells) >= 1 else "")
            ano_text = _norm_text(cells[1].text if len(cells) >= 2 else "")
            mes_text = _norm_text(cells[2].text if len(cells) >= 3 else "")
            snapshot.append(f"{idx}:{tipo_text}|{mes_text}/{ano_text}")

            if _norm_key(tipo_text) == "tipo":
                continue

            tipo_ok = _norm_key(tipo_text) == req_tipo_key
            ano_ok = _parse_int_from_text(ano_text) == req_ano
            mes_ok = _parse_int_from_text(mes_text) == req_mes
            if tipo_ok and ano_ok and mes_ok:
                return idx, tipo_text, ano_text, mes_text

        raise ContributionGenerationError(
            message="Não encontrei a contribuição/competência solicitada na tabela.",
            details=(
                f"tipo={req_tipo_key} mes={req_mes} ano={req_ano} "
                f"linhas={'; '.join(snapshot[:10])}"
            ),
        )

    def _capturar_e_clicar_imprimir(
        self,
        tbody_xpath: str,
        row_idx: int,
        tipo_text: str,
        ano_text: str,
        mes_text: str,
        expect_altvalor: bool = True,
    ) -> None:
        imprimir_xpath = f'{tbody_xpath}/tr[{row_idx}]/th[6]/a'

        old_handles = list(self.driver.window_handles)
        self._handles_before_boleto = old_handles
        self._boleto_url = None

        try:
            imprimir_el = self._wait(30).until(EC.element_to_be_clickable((By.XPATH, imprimir_xpath)))
            href = (imprimir_el.get_attribute("href") or "").strip()
            href_url = urljoin(self.base_url, href) if href else ""

            # Modo de teste: não clica em "Imprimir" para evitar abrir preview do Chrome.
            # Apenas captura a URL e segue com abertura direta no obter_boleto().
            if not expect_altvalor:
                if not href_url:
                    raise RuntimeError("Link de imprimir sem href.")
                self._boleto_url = _normalize_bloqueto_url(href_url)
                return

            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", imprimir_el)
            try:
                imprimir_el.click()
            except Exception:
                if href_url:
                    self.driver.get(href_url)
                else:
                    self.driver.execute_script("arguments[0].click();", imprimir_el)

            if expect_altvalor:
                self._switch_to_altvalor_context(old_handles, href_url=href_url, timeout_s=20)
            else:
                # modo de teste: não entra na tela altvalor.php
                time.sleep(1)
        except Exception as e:
            raise ContributionGenerationError(
                message="Não consegui clicar no botão Imprimir da contribuição selecionada.",
                details=f"row={row_idx} tipo={tipo_text} mes={mes_text} ano={ano_text} err={e}",
            )

    def _switch_to_altvalor_context(self, old_handles: list[str], *, href_url: str, timeout_s: int = 20) -> None:
        def _new_or_same_tab_altvalor(driver):
            current_url = driver.current_url or ""
            if "altvalor.php" in current_url:
                return True

            handles = driver.window_handles
            if len(handles) > len(old_handles):
                for handle in handles:
                    if handle not in old_handles:
                        driver.switch_to.window(handle)
                        return "altvalor.php" in (driver.current_url or "")
            return False

        try:
            self._wait(timeout_s).until(_new_or_same_tab_altvalor)
        except Exception:
            if href_url:
                self.driver.get(href_url)
                self._wait(timeout_s).until(lambda d: "altvalor.php" in (d.current_url or ""))
                return
            raise

    def _preencher_valor_e_confirmar(self, request: BoletoRequest) -> None:
        valor_str = _format_valor(request.valor)
        valor_dot = f"{request.valor:.2f}"
        altvalor_url = ""

        try:
            self._wait(20).until(lambda d: "altvalor.php" in (d.current_url or ""))
            altvalor_url = self.driver.current_url or ""
            self._type(By.XPATH, '//*[@id="valor"]', valor_str, timeout_s=20)
        except Exception as e:
            raise ContributionGenerationError(
                message="Não consegui preencher o valor na tela de alteração.",
                details=f"url={self.driver.current_url} valor={valor_str} err={e}",
            )

        try:
            self._click(By.XPATH, '//*[@id="OK"]', timeout_s=20)
        except Exception as e:
            raise ContributionGenerationError(
                message="Não consegui clicar no botão OK para confirmar o valor.",
                details=f"url={self.driver.current_url} valor={valor_str} err={e}",
            )

        self._handles_before_boleto = list(self.driver.window_handles)
        try:
            popup_xpath = '/html/body/div[2]/div[2]/div/div/div/div/div/div/div'
            confirm_xpath = '/html/body/div[2]/div[2]/div/div/div/div/div/div/div/div[4]/button[1]'
            self._wait(20).until(EC.presence_of_element_located((By.XPATH, popup_xpath)))
            # Guarda URL final esperada do boleto para abrir depois sem depender da UI de impressão.
            if altvalor_url:
                self._boleto_url = _build_boleto_url_from_altvalor(altvalor_url, valor_dot)
            self._click(By.XPATH, confirm_xpath, timeout_s=20)

            try:
                self._wait(15).until(
                    lambda d: "bloqueto.php" in (d.current_url or "") or len(d.window_handles) > len(self._handles_before_boleto)
                )
            except Exception:
                pass

            current = self.driver.current_url or ""
            if "bloqueto.php" in current:
                self._boleto_url = current
            elif "altvalor.php" in current and altvalor_url:
                self._boleto_url = _build_boleto_url_from_altvalor(altvalor_url, valor_dot)
        except Exception as e:
            raise ContributionGenerationError(
                message="Popup de confirmação não apareceu ou não consegui clicar em CONFIRMA.",
                details=f"url={self.driver.current_url} valor={valor_str} err={e}",
            )

    def obter_boleto(self) -> PortalResult:
        js_disabled = False
        try:
            boleto_url = getattr(self, "_boleto_url", None)
            try:
                # Evita abertura da UI de impressão do Chrome (window.print).
                self.driver.execute_cdp_cmd("Emulation.setScriptExecutionDisabled", {"value": True})
                js_disabled = True
            except Exception:
                pass

            if boleto_url:
                self.driver.get(boleto_url)
            else:
                old_handles = self._handles_before_boleto
                self._switch_to_boleto_context(old_handles, timeout_s=30)

            self._wait(30).until(lambda d: "bloqueto.php" in (d.current_url or ""))
            self._wait(30).until(lambda d: d.execute_script("return document.readyState") == "complete")
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
        finally:
            if js_disabled:
                try:
                    self.driver.execute_cdp_cmd("Emulation.setScriptExecutionDisabled", {"value": False})
                except Exception:
                    pass

    def close(self) -> None:
        return
