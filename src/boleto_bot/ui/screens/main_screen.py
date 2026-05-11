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
from ...services.history_service import BoletoHistoryService
from ...services.report_service import ExecutionReport
from ..components import BoletoCard
from ..theme import COLORS, FONTS


class MainScreen(ctk.CTkFrame):
    def __init__(self, master) -> None:
        super().__init__(master=master, fg_color="transparent")
        self._cards: list[BoletoCard] = []
        self._running = False
        self._sindicato_options = [(key, info.nome) for key, info in SINDICATOS.items()]
        self._settings = Settings.from_env()
        self._history_service = BoletoHistoryService(self._settings)
        self._history_frame = None
        self._showing_history = False
        self._pending_history_payloads: list[dict] = []

        self._build()
        if not self._load_history():
            self._load_last_session()
        if not self._cards:
            self._add_card()

    def _build(self) -> None:
        self.pack_propagate(False)

        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.pack(fill="x", padx=24, pady=(26, 8))
        title_row.grid_columnconfigure(0, weight=0, minsize=48)
        title_row.grid_columnconfigure(1, weight=1)
        title_row.grid_columnconfigure(2, weight=0, minsize=48)

        self.history_button = ctk.CTkButton(
            title_row,
            text="☰",
            width=40,
            height=36,
            font=FONTS["body"],
            fg_color="transparent",
            hover_color="#E5E7EB",
            text_color=COLORS["text_primary"],
            command=self._toggle_history_view,
        )
        self.history_button.grid(row=0, column=0, sticky="w")

        title = ctk.CTkLabel(
            title_row,
            text="Robô Emitente de Boletos",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
        )
        title.grid(row=0, column=1)

        self.master.bind("<Escape>", lambda _event: self._hide_history_view())

        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)

        description = ctk.CTkLabel(
            self.content_frame,
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
            self.content_frame,
            text="Emitir Boletos:",
            font=FONTS["section_title"],
            text_color=COLORS["text_primary"],
        )
        subtitle.pack(anchor="w", padx=24, pady=(0, 10))

        self.search_entry = ctk.CTkEntry(
            self.content_frame,
            font=FONTS["small"],
            placeholder_text="Pesquisar por CNPJ...",
        )
        self.search_entry.pack(fill="x", padx=24, pady=(0, 10))
        self.search_entry.bind("<KeyRelease>", lambda _event: self._apply_search_filter())

        self.cards_frame = ctk.CTkScrollableFrame(
            self.content_frame,
            width=552,
            height=390,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color="#9CA3AF",
            scrollbar_button_hover_color="#6B7280",
        )
        self.cards_frame.pack(fill="x", padx=24, pady=(0, 8))
        self._configure_scroll_speed()

        self.actions_row = ctk.CTkFrame(self.content_frame, fg_color="transparent")
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

        self.select_all_var = ctk.BooleanVar(value=True)
        self.select_all_checkbox = ctk.CTkCheckBox(
            self.actions_row,
            text="Selecionar todos",
            font=FONTS["small"],
            variable=self.select_all_var,
            checkbox_width=20,
            checkbox_height=20,
            width=124,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            border_color="#9CA3AF",
            checkmark_color="#FFFFFF",
            text_color=COLORS["text_primary"],
            command=self._set_all_selected,
        )
        self.select_all_checkbox.pack(side="right", padx=(10, 0))

        self.save_session_var = ctk.BooleanVar(value=True)
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
            self.content_frame,
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
            self.content_frame,
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
        data.setdefault("selected", bool(self.select_all_var.get()))
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
        self._apply_search_filter()

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
        self.search_entry.configure(state=controls_state)
        self.select_all_checkbox.configure(state=controls_state)
        self.save_session_checkbox.configure(state=controls_state)
        self.submit_button.configure(state=controls_state)
        self.submit_button.configure(text="Processando..." if running else "Emitir Boletos")

        for card in self._cards:
            card.set_interaction_enabled(not running)

        self._refresh_cards()

    def _collect_payload(self) -> list[dict]:
        return [card.get_payload() for card in self._cards if card.is_selected()]

    def _collect_all_payload(self) -> list[dict]:
        return [card.get_payload() for card in self._cards]

    def _set_all_selected(self) -> None:
        selected = bool(self.select_all_var.get())
        for card in self._cards:
            card.set_selected(selected)

    def _toggle_history_view(self) -> None:
        if self._showing_history:
            self._hide_history_view()
            return
        self._show_history_view()

    def _show_history_view(self) -> None:
        self._showing_history = True
        self.content_frame.pack_forget()
        self._build_history_frame()
        self._history_frame.pack(fill="both", expand=True)

    def _hide_history_view(self) -> None:
        if not self._showing_history:
            return
        self._showing_history = False
        if self._history_frame is not None:
            self._history_frame.pack_forget()
        self.content_frame.pack(fill="both", expand=True)

    def _build_history_frame(self) -> None:
        if self._history_frame is not None:
            self._history_frame.destroy()

        self._history_frame = ctk.CTkFrame(self, fg_color="transparent")

        title = ctk.CTkLabel(
            self._history_frame,
            text="Historico de Boletos",
            font=FONTS["label"],
            text_color=COLORS["text_primary"],
        )
        title.pack(anchor="w", padx=24, pady=(8, 12))

        history = self._history_service.load()
        if not history:
            empty_label = ctk.CTkLabel(
                self._history_frame,
                text="Nenhum boleto salvo no historico.",
                font=FONTS["body"],
                text_color=COLORS["muted"],
            )
            empty_label.pack(anchor="center", expand=True)
            return

        table = ctk.CTkFrame(self._history_frame, fg_color=COLORS["card_bg"], corner_radius=8)
        table.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        table.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        table.grid_rowconfigure(1, weight=1)

        headings = ("Sindicato", "Tipo", "CNPJ", "Valor", "Senha")
        for column, heading in enumerate(headings):
            label = ctk.CTkLabel(
                table,
                text=heading,
                font=FONTS["section_title"],
                text_color=COLORS["text_primary"],
                anchor="w",
            )
            label.grid(row=0, column=column, sticky="ew", padx=8, pady=(10, 6))

        rows_frame = ctk.CTkScrollableFrame(
            table,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color="#9CA3AF",
            scrollbar_button_hover_color="#6B7280",
        )
        rows_frame.grid(row=1, column=0, columnspan=5, sticky="nsew", padx=0, pady=(0, 10))
        rows_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        for row_index, payload in enumerate(history):
            values = (
                self._sindicato_label(str(payload.get("sindicato_key", ""))),
                str(payload.get("tipo_contribuicao", "")),
                str(payload.get("cnpj", "")),
                str(payload.get("valor", "")),
                str(payload.get("senha", "")),
            )
            bg_color = "#F9FAFB" if row_index % 2 == 0 else "#FFFFFF"
            for column, value in enumerate(values):
                cell = ctk.CTkLabel(
                    rows_frame,
                    text=value,
                    font=FONTS["small"],
                    text_color=COLORS["text_secondary"],
                    fg_color=bg_color,
                    anchor="w",
                    corner_radius=0,
                )
                cell.grid(row=row_index, column=column, sticky="ew", padx=0, pady=1, ipady=8)

    def _sindicato_label(self, sindicato_key: str) -> str:
        for key, label in self._sindicato_options:
            if key == sindicato_key:
                return label
        return sindicato_key

    def _apply_search_filter(self) -> None:
        search_text = self.search_entry.get()
        query = "".join(ch for ch in search_text if ch.isdigit())
        text_query = search_text.strip().lower()

        for card in self._cards:
            payload = card.get_payload()
            cnpj_digits = "".join(ch for ch in str(payload.get("cnpj", "")) if ch.isdigit())
            cnpj_text = str(payload.get("cnpj", "")).lower()
            should_show = not query and not text_query
            if query:
                should_show = query in cnpj_digits
            elif text_query:
                should_show = text_query in cnpj_text

            if should_show:
                if not card.winfo_manager():
                    card.pack(fill="x", pady=(0, 10))
            else:
                card.pack_forget()

        self._refresh_cards()

    def _collect_session_payload(self) -> list[dict]:
        session_payload: list[dict] = []
        for card_payload in self._collect_all_payload():
            session_payload.append(
                self._sanitize_card_data(
                    {
                        "sindicato_key": card_payload.get("sindicato_key"),
                        "tipo_contribuicao": card_payload.get("tipo_contribuicao"),
                        "cnpj": card_payload.get("cnpj"),
                        "senha": card_payload.get("senha"),
                        "valor": card_payload.get("valor"),
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
        valor = str(raw.get("valor", "")).strip()

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
            "valor": valor,
            "ano": ano,
            "mes": mes,
            "selected": bool(raw.get("selected", True)),
        }

    def _session_file_path(self) -> Path:
        return self._settings.STORAGE_ROOT / ".ultima_sessao.json"

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

    def persist_session_before_close(self) -> None:
        """Persist the latest card state when the user closes the app."""
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

    def _load_history(self) -> bool:
        history = self._history_service.load()
        if not history:
            return False

        loaded_count = 0
        for payload in history:
            data = dict(payload)
            data["selected"] = True
            self._add_card(data)
            loaded_count += 1

        if loaded_count:
            self.status_label.configure(text=f"Historico carregado: {loaded_count} boleto(s).")
        return loaded_count > 0

    def _submit(self) -> None:
        if self._running:
            return

        payload = self._collect_payload()
        if not payload:
            self.status_label.configure(text="Selecione pelo menos um boleto.")
            messagebox.showwarning("Selecao", "Selecione pelo menos um boleto para emitir.")
            return

        try:
            requests = validar_e_montar_requests(payload, ordenar_por_sindicato=True)
        except BatchValidationError as exc:
            self.status_label.configure(text="Existem erros de validação.")
            messagebox.showerror("Validação", self._format_batch_errors(exc))
            return

        if self.save_session_var.get():
            payloads_by_key = {self._history_key_from_payload(item): item for item in payload}
            self._pending_history_payloads = [
                payloads_by_key.get(self._history_key_from_request(request), {})
                for request in requests
            ]
            self._save_last_session()
            self.status_label.configure(text="Sessao salva. Historico sera atualizado apos a emissao.")
        else:
            self._pending_history_payloads = []

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
            options = FlowRunnerOptions(
                group_by_sindicato=True,
                pause_after=False,
                manual_captcha_prompt=self._confirm_manual_captcha,
            )
            report = FlowRunner(settings=self._settings, options=options).run(requests)
            self.after(0, lambda: self._on_automation_success(report))
        except Exception as exc:
            self.after(0, lambda: self._on_automation_error(exc))

    def _confirm_manual_captcha(self, request) -> None:
        confirmed = threading.Event()

        def show_prompt() -> None:
            self.status_label.configure(text="Aguardando verificacao manual no Chrome...")
            messagebox.showinfo(
                "Verificacao manual",
                (
                    "Se aparecer captcha/verificacao no site do Sindicomerciario, "
                    "resolva no Chrome que foi aberto.\n\n"
                    "Depois clique em OK para o robo continuar."
                ),
            )
            confirmed.set()

        self.after(0, show_prompt)
        confirmed.wait()

    def _on_automation_success(self, report: ExecutionReport) -> None:
        self._set_running(False)
        summary = report.summary_dict()
        saved_history_count = 0
        if self._pending_history_payloads:
            successful_payloads = [
                payload
                for item, payload in zip(report.items, self._pending_history_payloads)
                if item.status == "SUCCESS" and payload
            ]
            if successful_payloads:
                saved_history_count = self._history_service.save_many(successful_payloads)
            self._pending_history_payloads = []
        text = (
            f"Concluído. Sucesso: {summary['success']} | "
            f"Erro: {summary['error']} | Total: {summary['total']}"
        )
        if saved_history_count:
            text = f"{text} | Historico: {saved_history_count}"
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
        self._pending_history_payloads = []
        self.status_label.configure(text="Falha inesperada ao emitir boletos.")
        messagebox.showerror("Erro inesperado", str(exc))

    def _history_key_from_payload(self, payload: dict) -> tuple[str, str, str, str, str]:
        cnpj = "".join(ch for ch in str(payload.get("cnpj", "")) if ch.isdigit())
        return (
            str(payload.get("sindicato_key", "")),
            str(payload.get("tipo_contribuicao", "")),
            cnpj,
            str(payload.get("ano", "")),
            str(payload.get("mes", "")),
        )

    def _history_key_from_request(self, request) -> tuple[str, str, str, str, str]:
        cnpj = "".join(ch for ch in str(request.cnpj) if ch.isdigit())
        return (
            str(request.sindicato_key),
            str(request.tipo_contribuicao.value),
            cnpj,
            str(request.competencia.ano),
            str(request.competencia.mes),
        )

    def _format_batch_errors(self, exc: BatchValidationError) -> str:
        lines: list[str] = []
        for idx, item_errors in sorted(exc.errors.items()):
            lines.append(f"Boleto #{idx + 1}")
            for field, message in item_errors.items():
                lines.append(f"- {field}: {message}")
            lines.append("")
        return "\n".join(lines).strip()
