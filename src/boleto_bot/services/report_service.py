# src/boleto_bot/services/report_service.py

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..domain.models import BoletoRequest


@dataclass
class ExecutionItem:
    status: str  # "SUCCESS" | "ERROR"
    message: str
    request: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


@dataclass
class ExecutionReport:
    """
    Relatório simples de execução.

    - add_success(req, path): registra sucesso
    - add_error(req, msg): registra erro
    - finalize(): fecha o relatório
    - summary_dict(): retorna um resumo pronto pra print/log/UI
    """
    items: List[ExecutionItem] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    finished_at: Optional[str] = None

    def add_success(self, req: Optional[BoletoRequest], message: str) -> None:
        self.items.append(
            ExecutionItem(
                status="SUCCESS",
                message=message,
                request=req.safe_log_dict() if req else None,
            )
        )

    def add_error(self, req: Optional[BoletoRequest], message: str) -> None:
        self.items.append(
            ExecutionItem(
                status="ERROR",
                message=message,
                request=req.safe_log_dict() if req else None,
            )
        )

    def finalize(self) -> None:
        if self.finished_at is None:
            self.finished_at = datetime.now().isoformat(timespec="seconds")

    def summary_dict(self) -> Dict[str, Any]:
        success = sum(1 for i in self.items if i.status == "SUCCESS")
        error = sum(1 for i in self.items if i.status == "ERROR")
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total": len(self.items),
            "success": success,
            "error": error,
        }
