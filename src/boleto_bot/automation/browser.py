from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from ..config.settings import Settings


@dataclass
class BrowserSession:
    driver: webdriver.Chrome
    settings: Settings

    def quit(self) -> None:
        """Fecha o navegador e encerra o processo do driver."""
        try:
            self.driver.quit()
        except Exception:
            pass

    def __enter__(self) -> "BrowserSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.quit()


def create_browser(settings: Settings) -> BrowserSession:
   # garante que a pasta existe
    Path(settings.DOWNLOADS_DIR).mkdir(parents=True, exist_ok=True)

    options = Options()

    # ======= HEADLESS =======
    # Se for rodar sem janela (robô invisível), ativa o headless.
    if settings.HEADLESS:
        # "new" é o headless mais moderno do Chrome
        options.add_argument("--headless=new")

    # ======= ARGUMENTOS ÚTEIS =======
    # Ajuda estabilidade em ambientes corporativos e/ou Windows
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # ======= DOWNLOADS =======
    # Faz o Chrome baixar automaticamente sem perguntar.
    prefs = {
        "download.default_directory": str(Path(settings.DOWNLOADS_DIR).resolve()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,

        # MUITO IMPORTANTE: se for PDF, baixa ao invés de abrir no Chrome
        "plugins.always_open_pdf_externally": True,

        # evita bloqueios bestas do Chrome
        "safebrowsing.enabled": True,
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=options)
    # Garante janela maximizada em modo visível
    try:
        driver.maximize_window()
    except Exception:
        pass

    # ======= TIMEOUTS =======
    driver.set_page_load_timeout(settings.NAV_TIMEOUT_MS / 1000)

    driver.implicitly_wait(0)

    # ======= GARANTIR DOWNLOAD EM HEADLESS (fallback) =======
    # Em alguns cenários, o headless precisa “forçar” comportamento de download via CDP.
    try:
        driver.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(Path(settings.DOWNLOADS_DIR).resolve())},
        )
    except Exception:
        pass

    # ======= BLOQUEAR PRINT PREVIEW AUTOMÁTICO =======
    # Alguns boletos chamam window.print() ao abrir e travam a UI.
    # Aqui neutralizamos isso para permitir o printToPDF via CDP.
    try:
        driver.execute_cdp_cmd("Page.enable", {})
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "window.print = () => {}; window.onbeforeprint = null; window.onafterprint = null;"},
        )
    except Exception:
        pass

    return BrowserSession(driver=driver, settings=settings)
