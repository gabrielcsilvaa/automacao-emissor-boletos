from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AutomationError(Exception):
    message: str
    code: str = "AUTOMATION_ERROR"
    details: Optional[str] = None

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class PageLoadError(AutomationError):
    """A página não carregou / timeout / site fora do ar."""
    code: str = "PAGE_LOAD_ERROR"


@dataclass(frozen=True)
class ElementNotFoundError(AutomationError):

    code: str = "ELEMENT_NOT_FOUND"


# ===== Erros de autenticação =====

@dataclass(frozen=True)
class LoginFailedError(AutomationError):
    """
    Falha de login:
    - senha errada
    - CNPJ não cadastrado
    - captcha/bloqueio
    - mensagem de erro do portal
    """
    code: str = "LOGIN_FAILED"


# ===== Erros de negócio (fluxo do boleto) =====

@dataclass(frozen=True)
class ContributionGenerationError(AutomationError):
    """
    Erro ao preencher/gerar a contribuição:
    - tipo de contribuição não aparece
    - mês/ano não aceita
    - valor rejeitado
    - botão gerar não funciona
    """
    code: str = "CONTRIBUTION_GENERATION_FAILED"


@dataclass(frozen=True)
class BoletoNotAvailableError(AutomationError):
    """
    O boleto não ficou disponível no final:
    - não abriu modal/aba do boleto
    - não apareceu opção imprimir/baixar
    """
    code: str = "BOLETO_NOT_AVAILABLE"


# ===== Erros de download/salvamento =====

@dataclass(frozen=True)
class DownloadError(AutomationError):
    """
    Falha ao baixar o PDF:
    - download não iniciou
    - ficou preso (.crdownload)
    - arquivo não apareceu na pasta
    """
    code: str = "DOWNLOAD_FAILED"


@dataclass(frozen=True)
class SaveFileError(AutomationError):
    """
    Falha ao mover/renomear/salvar o PDF no destino final:
    - permissão
    - arquivo em uso
    - caminho inválido
    """
    code: str = "SAVE_FILE_FAILED"
