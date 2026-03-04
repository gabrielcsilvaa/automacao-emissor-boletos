from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from ...automation.flow_runner import FlowRunner, FlowRunnerOptions
from ...config.settings import Settings
from ...domain.enums import SINDICATOS, listar_tipos_contribuicao, listar_tipos_por_sindicato
from ...domain.validators import BatchValidationError, validar_e_montar_requests
from ...services.report_service import ExecutionReport
from ..components import BoletoCard
from ..theme import COLORS, FONTS


class MainScreen(ctk.CTkFrame):
    def __init__(self, master) -> None:
        super().__init__(master=master, fg_color="transparent")
        self._cards: list[BoletoCard] = []
        self._running = False
        self._sindicato_options = [(key, info.nome) for key, info in SINDICATOS.items()]

        self._build()
        if not self._load_last_session():
            self._add_card()

    def _build(self) -> None:
        self.pack_propagate(False)

        title = ctk.CTkLabel(
            self,
            text="Robô Emitente de Boletos",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
        )
        title.pack(anchor="center", pady=(26, 8))

        description = ctk.CTkLabel(
            self,
            text=(
                "Essa ferramenta foi desenvolvida para facilitar a emissão de boletos por\n"
                "sindicato, podendo ser usado para emissões individuais ou em lotes."
            ),
            font=FONTS["body"],
            justify="left",
            text_color=COLORS["text_secondary"],
        )
        description.pack(anchor="w", padx=24, pady=(0, 12))

        subtitle = ctk.CTkLabel(
            self,
            text="Emitir Boletos:",
            font=FONTS["section_title"],
            text_color=COLORS["text_primary"],
        )
        subtitle.pack(anchor="w", padx=24, pady=(0, 10))

        self.cards_frame = ctk.CTkScrollableFrame(
            self,
            width=552,
            height=390,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color="#9CA3AF",
            scrollbar_button_hover_color="#6B7280",
        )
        self.cards_frame.pack(fill="x", padx=24, pady=(0, 8))
        self._configure_scroll_speed()

        self.actions_row = ctk.CTkFrame(self, fg_color="transparent")
        self.actions_row.pack(fill="x", padx=24, pady=(0, 12))

        self.add_button = ctk.CTkButton(
            self.actions_row,
            text="+ Adicionar Boletos p/ Gerar em Lote",
            font=FONTS["body"],
            fg_color="transparent",
            hover_color="#E5E7EB",
            text_color=COLORS["text_primary"],
            anchor="w",
            command=self._add_card,
        )
        self.add_button.pack(side="left", fill="x", expand=True)

        self.save_session_var = ctk.BooleanVar(value=False)
        self.save_session_checkbox = ctk.CTkCheckBox(
            self.actions_row,
            text="Salvar sessao",
            font=FONTS["small"],
            variable=self.save_session_var,
            checkbox_width=20,
            checkbox_height=20,
            width=126,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            border_color="#9CA3AF",
            checkmark_color="#FFFFFF",
            text_color=COLORS["text_primary"],
            command=self._on_save_session_toggled,
        )
        self.save_session_checkbox.pack(side="right", padx=(10, 0))

        self.submit_button = ctk.CTkButton(
            self,
            text="Emitir Boletos",
            font=FONTS["button"],
            fg_color=COLORS["button"],
            hover_color=COLORS["button_hover"],
            text_color="#F9FAFB",
            width=280,
            height=52,
            corner_radius=8,
            command=self._submit,
        )
        self.submit_button.pack(anchor="center", pady=(0, 8))

        self.status_label = ctk.CTkLabel(
            self,
            text="",
            font=FONTS["small"],
            text_color=COLORS["muted"],
        )
        self.status_label.pack(anchor="center", pady=(0, 6))

    def _default_payload(self) -> dict:
        sindicato_key = self._sindicato_options[0][0]
        tipos = self._tipos_for_sindicato(sindicato_key)
        return {
            "sindicato_key": sindicato_key,
            "tipo_contribuicao": tipos[0] if tipos else "",
            "cnpj": "",
            "senha": "",
            "valor": "",
            "ano": datetime.now().year,
            "mes": datetime.now().month,
        }

    def _tipos_for_sindicato(self, sindicato_key: str) -> list[str]:
        tipos = listar_tipos_por_sindicato(sindicato_key)
        if tipos:
            return tipos
        return listar_tipos_contribuicao()

    def _add_card(self, data: dict | None = None) -> None:
        if self._running:
            return

        data = self._sanitize_card_data(data)
        card = BoletoCard(
            master=self.cards_frame,
            index=len(self._cards) + 1,
            sindicato_options=self._sindicato_options,
            tipo_options=self._tipos_for_sindicato(data["sindicato_key"]),
            data=data,
            on_remove=self._remove_card,
            on_sindicato_change=self._on_sindicato_change,
        )
        card.pack(fill="x", pady=(0, 10))
        self._bind_mouse_wheel_recursive(card)
        self._cards.append(card)
        self._refresh_cards()

    def _remove_card(self, card: BoletoCard) -> None:
        if self._running or len(self._cards) <= 1:
            return

        card.destroy()
        self._cards = [item for item in self._cards if item is not card]
        self._refresh_cards()

    def _on_sindicato_change(self, card: BoletoCard, sindicato_key: str) -> None:
        card.set_tipo_options(
            self._tipos_for_sindicato(sindicato_key),
            preserve_value=card.get_tipo_value(),
        )

    def _refresh_cards(self) -> None:
        can_remove = len(self._cards) > 1 and not self._running
        for idx, card in enumerate(self._cards, start=1):
            card.set_index(idx)
            card.set_remove_enabled(can_remove)

    def _set_running(self, running: bool) -> None:
        self._running = running
        controls_state = "disabled" if running else "normal"
        self.add_button.configure(state=controls_state)
        self.save_session_checkbox.configure(state=controls_state)
        self.submit_button.configure(state=controls_state)
        self.submit_button.configure(text="Processando..." if running else "Emitir Boletos")

        for card in self._cards:
            card.set_interaction_enabled(not running)

        self._refresh_cards()

    def _collect_payload(self) -> list[dict]:
        return [card.get_payload() for card in self._cards]

    def _collect_session_payload(self) -> list[dict]:
        session_payload: list[dict] = []
        for card_payload in self._collect_payload():
            session_payload.append(
                self._sanitize_card_data(
                    {
                        "sindicato_key": card_payload.get("sindicato_key"),
                        "tipo_contribuicao": card_payload.get("tipo_contribuicao"),
                        "cnpj": card_payload.get("cnpj"),
                        "senha": card_payload.get("senha"),
                        "ano": card_payload.get("ano"),
                        "mes": card_payload.get("mes"),
                    }
                )
            )
        return session_payload

    def _sanitize_card_data(self, raw: dict | None) -> dict:
        data = self._default_payload()
        if not raw:
            return data

        available_sindicatos = {key for key, _label in self._sindicato_options}
        sindicato_key = str(raw.get("sindicato_key", "")).strip()
        if sindicato_key not in available_sindicatos:
            sindicato_key = data["sindicato_key"]

        tipo_options = self._tipos_for_sindicato(sindicato_key)
        tipo = str(raw.get("tipo_contribuicao", "")).strip()
        if tipo not in tipo_options and tipo_options:
            tipo = tipo_options[0]

        cnpj = str(raw.get("cnpj", "")).strip()
        senha = str(raw.get("senha", "")).strip()

        ano_default = int(data["ano"])
        mes_default = int(data["mes"])
        try:
            ano = int(raw.get("ano", ano_default))
        except (TypeError, ValueError):
            ano = ano_default

        try:
            mes = int(raw.get("mes", mes_default))
        except (TypeError, ValueError):
            mes = mes_default

        if mes < 1 or mes > 12:
            mes = mes_default

        return {
            "sindicato_key": sindicato_key,
            "tipo_contribuicao": tipo,
            "cnpj": cnpj,
            "senha": senha,
            "valor": "",
            "ano": ano,
            "mes": mes,
        }

    def _session_file_path(self) -> Path:
        storage_root = Settings.from_env().STORAGE_ROOT
        return storage_root / ".ultima_sessao.json"

    def _save_last_session(self) -> None:
        if self._running:
            return

        try:
            cards = self._collect_session_payload()
            payload = {
                "version": 1,
                "saved_at": datetime.now().isoformat(timespec="seconds"),
                "cards": cards,
            }
            session_file = self._session_file_path()
            session_file.parent.mkdir(parents=True, exist_ok=True)
            session_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            self.status_label.configure(text="Falha ao salvar sessao.")
            messagebox.showerror("Salvar sessao", str(exc))
            return

    def _on_save_session_toggled(self) -> None:
        if not self.save_session_var.get():
            return
        self._save_last_session()

    def _load_last_session(self) -> bool:
        try:
            session_file = self._session_file_path()
            if not session_file.exists():
                return False

            raw_payload = json.loads(session_file.read_text(encoding="utf-8"))
        except Exception:
            return False

        if not isinstance(raw_payload, dict):
            return False

        cards = raw_payload.get("cards")
        if not isinstance(cards, list):
            return False

        loaded_count = 0
        for card in cards:
            if not isinstance(card, dict):
                continue
            self._add_card(card)
            loaded_count += 1

        return loaded_count > 0

    def _submit(self) -> None:
        if self._running:
            return

        payload = self._collect_payload()
        try:
            requests = validar_e_montar_requests(payload, ordenar_por_sindicato=True)
        except BatchValidationError as exc:
            self.status_label.configure(text="Existem erros de validação.")
            messagebox.showerror("Validação", self._format_batch_errors(exc))
            return

        self.status_label.configure(text="Iniciando emissão...")
        self._set_running(True)

        thread = threading.Thread(target=self._run_automation, args=(requests,), daemon=True)
        thread.start()

    def _configure_scroll_speed(self) -> None:
        # Aumenta o deslocamento por "unidade" de scroll para reduzir o
        # número de giros necessários na roda do mouse.
        canvas = getattr(self.cards_frame, "_parent_canvas", None)
        if canvas is None:
            return

        canvas.configure(yscrollincrement=24)
        self.cards_frame.bind("<MouseWheel>", self._on_mouse_wheel, add="+")
        canvas.bind("<MouseWheel>", self._on_mouse_wheel, add="+")
        self.cards_frame.bind("<Button-4>", self._on_mouse_wheel, add="+")
        self.cards_frame.bind("<Button-5>", self._on_mouse_wheel, add="+")
        canvas.bind("<Button-4>", self._on_mouse_wheel, add="+")
        canvas.bind("<Button-5>", self._on_mouse_wheel, add="+")

    def _bind_mouse_wheel_recursive(self, widget) -> None:
        widget.bind("<MouseWheel>", self._on_mouse_wheel, add="+")
        widget.bind("<Button-4>", self._on_mouse_wheel, add="+")
        widget.bind("<Button-5>", self._on_mouse_wheel, add="+")
        for child in widget.winfo_children():
            self._bind_mouse_wheel_recursive(child)

    def _on_mouse_wheel(self, event) -> str | None:
        canvas = getattr(self.cards_frame, "_parent_canvas", None)
        if canvas is None:
            return None

        if getattr(event, "delta", 0):
            raw_steps = -int(event.delta / 120)
            steps = raw_steps * 3 if raw_steps != 0 else 0
        elif getattr(event, "num", None) == 4:
            steps = -3
        elif getattr(event, "num", None) == 5:
            steps = 3
        else:
            steps = 0

        if steps != 0:
            canvas.yview_scroll(steps, "units")
            return "break"
        return None

    def _run_automation(self, requests) -> None:
        try:
            settings = Settings.from_env()
            options = FlowRunnerOptions(group_by_sindicato=True, pause_after=False)
            report = FlowRunner(settings=settings, options=options).run(requests)
            self.after(0, lambda: self._on_automation_success(report))
        except Exception as exc:
            self.after(0, lambda: self._on_automation_error(exc))

    def _on_automation_success(self, report: ExecutionReport) -> None:
        self._set_running(False)
        summary = report.summary_dict()
        text = (
            f"Concluído. Sucesso: {summary['success']} | "
            f"Erro: {summary['error']} | Total: {summary['total']}"
        )
        self.status_label.configure(text=text)

        if summary["error"] == 0:
            messagebox.showinfo("Emissão concluída", text)
            return

        errors = [item for item in report.items if item.status == "ERROR"]
        error_lines = "\n".join(f"- {item.message}" for item in errors[:5])
        if len(errors) > 5:
            error_lines += "\n- ..."
        messagebox.showwarning("Emissão com falhas", f"{text}\n\nErros:\n{error_lines}")

    def _on_automation_error(self, exc: Exception) -> None:
        self._set_running(False)
        self.status_label.configure(text="Falha inesperada ao emitir boletos.")
        messagebox.showerror("Erro inesperado", str(exc))

    def _format_batch_errors(self, exc: BatchValidationError) -> str:
        lines: list[str] = []
        for idx, item_errors in sorted(exc.errors.items()):
            lines.append(f"Boleto #{idx + 1}")
            for field, message in item_errors.items():
                lines.append(f"- {field}: {message}")
            lines.append("")
        return "\n".join(lines).strip()
