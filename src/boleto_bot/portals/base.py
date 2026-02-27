from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from ..automation.errors import ElementNotFoundError

from ..domain.models import BoletoRequest


@dataclass(frozen=True)
class PortalResult:
    sucesso: bool
    boleto_pdf_bytes: Optional[bytes] = None
    boleto_pdf_path: Optional[str] = None
    boleto_url: Optional[str] = None
    mensagem: Optional[str] = None


class PortalBase(ABC):

    def __init__(self, browser: object) -> None:

        self.browser = browser


    @property
    def driver(self) -> WebDriver:
        # no FlowRunner você passou o driver como "browser"
        return self.browser  # type: ignore

    def _wait(self, timeout_s: int = 30) -> WebDriverWait:
        return WebDriverWait(self.driver, timeout_s)

    def _click(self, by: By, selector: str, timeout_s: int = 30) -> None:
        try:
            el = self._wait(timeout_s).until(EC.element_to_be_clickable((by, selector)))
            el.click()
        except Exception as e:
            raise ElementNotFoundError(
                message="Elemento não encontrado/clicável (clique falhou).",
                details=f"by={by} selector={selector} err={e}",
            )
        

    def _type(self, by: By, selector: str, value: str, timeout_s: int = 30) -> None:
        try:
            el = self._wait(timeout_s).until(EC.presence_of_element_located((by, selector)))
            el.clear()
            el.send_keys(value)
        except Exception as e:
            raise ElementNotFoundError(
                message="Elemento de input não encontrado (digitação falhou).",
                details=f"by={by} selector={selector} err={e}",
        
            )
        
    def _select_by_value(self, by: By, selector: str, value: str, timeout_s: int = 30, click_first: bool = False) -> None:
        try:
            el = self._wait(timeout_s).until(EC.element_to_be_clickable((by, selector)))
            if click_first:
                el.click()
            Select(el).select_by_value(value)
        except Exception as e:
            raise ElementNotFoundError(
                message="Select não encontrado ou opção por VALUE não disponível.",
                details=f"by={by} selector={selector} value={value} click_first={click_first} err={e}",
        )

    def _select_by_text(self, by: By, selector: str, text: str, timeout_s: int = 30) -> None:
        try:
            el = self._wait(timeout_s).until(EC.presence_of_element_located((by, selector)))
            Select(el).select_by_visible_text(text)
        except Exception as e:
            raise ElementNotFoundError(
                message="Select não encontrado ou opção por TEXTO não disponível.",
                details=f"by={by} selector={selector} text={text} err={e}",
        )   


    def _switch_to_new_tab(self, old_handles: list[str], timeout_s: int = 20) -> str:
        def _new_tab_opened(driver):
            return len(driver.window_handles) > len(old_handles)

        self._wait(timeout_s).until(_new_tab_opened)

        new_handles = self.driver.window_handles
        new_tab = next(h for h in new_handles if h not in old_handles)

        self.driver.switch_to.window(new_tab)
        return new_tab


    def _wait_url_change(self, timeout_s: int = 30) -> None:
        def _url_ready(driver):
            url = driver.current_url or ""
            return url and url != "about:blank"

        self._wait(timeout_s).until(_url_ready)

    def _switch_to_boleto_context(self, old_handles: list[str], timeout_s: int = 30) -> None:
        try:
            # tenta nova aba
            self._switch_to_new_tab(old_handles, timeout_s=timeout_s)
        except Exception:
            # se n?o abriu aba nova, segue na mesma
            pass

        # em ambos os casos, espera sair do about:blank / ter url
        self._wait_url_change(timeout_s=timeout_s)

    def _get_text(self, by: By, selector: str, timeout_s: int = 30) -> str:
        try:
            el = self._wait(timeout_s).until(EC.presence_of_element_located((by, selector)))
            return (el.text or "").strip()
        except Exception as e:
            raise ElementNotFoundError(
            message="Elemento não encontrado (leitura de texto falhou).",
            details=f"by={by} selector={selector} err={e}",
        )


    @property
    @abstractmethod
    def key(self) -> str:
        """Chave única do portal, ex.: 'SINDCOMERCIARIOS_CE'."""
        raise NotImplementedError

    @property
    @abstractmethod
    def base_url(self) -> str:
        """URL base do sindicato."""
        raise NotImplementedError

    @abstractmethod
    def open_home(self) -> None:
        """Abre a página inicial/área de boletos do portal."""
        raise NotImplementedError

    @abstractmethod
    def login(self, request: BoletoRequest) -> None:
        """
        Faz login usando CNPJ e senha do request.
        Deve lançar exceção se falhar (ex.: senha errada).
        """
        raise NotImplementedError

    @abstractmethod
    def gerar_contribuicao(self, request: BoletoRequest) -> None:
        """
        Preenche tipo de contribuição, competência (ano/mês), valor etc.
        Deve preparar o ambiente para gerar/abrir o boleto.
        """
        raise NotImplementedError

    @abstractmethod
    def obter_boleto(self) -> PortalResult:
        """
        Etapa final:
        - abre o boleto (modal about:blank ou download)
        - devolve bytes do PDF OU caminho do arquivo já salvo
        """
        raise NotImplementedError

    def close(self) -> None:
        """
        Opcional: fecha recursos do portal.
        Alguns drivers precisam fechar aba/janela específica.
        """
        return
