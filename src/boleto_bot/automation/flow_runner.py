from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from ..config.settings import Settings
from ..domain.models import BoletoRequest
from ..domain.validators import ordenar_requests_por_sindicato
from ..services.storage_service import StorageService
from ..services.report_service import ExecutionReport
from ..services.portal_registry import get_portal_class
from ..portals.base import PortalBase, PortalResult
from .browser import create_browser
from .download_manager import DownloadManager
from .errors import (
    AutomationError,
    PageLoadError,
    ElementNotFoundError,
    LoginFailedError,
    ContributionGenerationError,
    BoletoNotAvailableError,
    DownloadError,
    SaveFileError,
)


@dataclass(frozen=True)
class FlowRunnerOptions:
    """
    Opções do runner.
    """
    download_timeout_s: int = 120  # quanto tempo esperar o PDF aparecer
    stable_for_s: float = 1.0      # por quanto tempo o arquivo tem que ficar estável (download finalizou)
    stop_after: str | None = None  # opção de debug: roda só até chegar nesse sindicato (ex.: "SINDCOMERCIARIOS_CE")
    
    group_by_sindicato: bool = True  # executa em blocos por sindicato (ordem da primeira aparicao)
    pause_after: bool = False


class FlowRunner:
    def __init__(
        self,
        settings: Settings,
        storage: Optional[StorageService] = None,
        downloader: Optional[DownloadManager] = None,
        options: Optional[FlowRunnerOptions] = None,
    ) -> None:
        self.settings = settings
        self.storage = storage or StorageService(settings)
        self.downloader = downloader or DownloadManager(settings)
        self.options = options or FlowRunnerOptions()

    def run(self, requests: Iterable[BoletoRequest]) -> ExecutionReport:

        report = ExecutionReport()
        queue = list(requests)
        if self.options.group_by_sindicato:
            queue = ordenar_requests_por_sindicato(queue)

        for req in queue:
            self._run_one_with_retries(req, report)

        report.finalize()
        return report

    def _run_one_with_retries(self, req: BoletoRequest, report: ExecutionReport) -> None:
        max_retries = max(0, int(self.settings.MAX_RETRIES))
        attempt = 0
        max_attempts = max_retries + 1

        while True:
            attempt += 1
            try:
                self._run_one(req, report)
                return  # sucesso

            except AutomationError as e:
                # erro "conhecido" da automação
                if attempt >= max_attempts or not self._should_retry(e):
                    report.add_error(req, f"{e.code}: {e.message}")
                    return

            except Exception as e:
                # erro inesperado (bug/selenium/loucura)
                if attempt >= max_attempts:
                    report.add_error(req, f"UNEXPECTED_ERROR: {e}")
                    return
                # tenta de novo se ainda tiver retries

    def _should_retry(self, e: AutomationError) -> bool:

        if isinstance(e, (LoginFailedError, ElementNotFoundError, ContributionGenerationError, BoletoNotAvailableError)):
            return False
        if isinstance(e, (PageLoadError, DownloadError)):
            return True

        # default: tenta 1x se ainda houver retries
        return True


    def _run_one(self, req: BoletoRequest, report: ExecutionReport) -> None:
        with create_browser(self.settings) as br:
            driver = br.driver

            portal_cls = get_portal_class(req.sindicato_key)
            portal: PortalBase = portal_cls(driver)

            try:
                portal.open_home()
                if self.options.stop_after == "open_home":
                    if self.options.pause_after:    
                        input("\n✅ Parei após open_home(). Enter pra fechar...")
                    report.add_success(req, "OK até open_home")
                    return
                
                portal.login(req)
                if self.options.stop_after == "login":
                    if self.options.pause_after:
                        input("\n✅ Parei após login(). Enter pra fechar...")
                    report.add_success(req, "OK até login")
                    return
                portal.gerar_contribuicao(req)
                if self.options.stop_after == "gerar_contribuicao":
                    if self.options.pause_after:
                        input("\n✅ Parei após gerar_contribuicao(). Enter pra fechar...")
                    report.add_success(req, "OK até gerar_contribuicao")
                    return

                target = self.storage.resolve_output(req, ext="pdf", avoid_overwrite=True)

                snap = self.downloader.snapshot()

                result = portal.obter_boleto()

                if self.options.stop_after == "obter_boleto":
                    if self.options.pause_after:
                        input("\n✅ Parei após obter_boleto(). Enter pra fechar...")
                    report.add_success(req, "OK até obter_boleto")
                    return

                final_path = self._resolve_and_save_pdf(result, snap, target)

                report.add_success(req, str(final_path))

            finally:
                try:
                    portal.close()
                except Exception:
                    pass

    def _resolve_and_save_pdf(self, result: PortalResult, snap, target) -> Path:
        if not result.sucesso:
            raise BoletoNotAvailableError(
                message=result.mensagem or "Boleto não ficou disponível no final.",
                details=f"url={result.boleto_url}",
            )

        if result.boleto_pdf_bytes:
            return self._write_pdf_bytes(result.boleto_pdf_bytes, Path(target.full_path))

        if result.boleto_pdf_path:
            downloaded = Path(result.boleto_pdf_path).expanduser().resolve()
            if not downloaded.exists():
                raise DownloadError(
                    message="Portal informou um caminho de PDF, mas o arquivo não existe.",
                    details=f"path={downloaded}",
                )
            return self.downloader.move_to_output(downloaded, target)

        downloaded = self.downloader.wait_new_pdf(
            snap,
            timeout_s=self.options.download_timeout_s,
            stable_for_s=self.options.stable_for_s,
        )
        return self.downloader.move_to_output(downloaded, target)

    def _write_pdf_bytes(self, data: bytes, path: Path) -> Path:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return path.resolve()
        except Exception as e:
            raise SaveFileError(
                message="Falha ao escrever bytes do PDF no destino final.",
                details=f"path={path} err={e}",
            )
