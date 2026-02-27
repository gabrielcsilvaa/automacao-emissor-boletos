from __future__ import annotations

from datetime import datetime
from typing import Callable, Sequence

import customtkinter as ctk

from ..theme import COLORS, FONTS

SindicatoOption = tuple[str, str]


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _blend_hex(start: str, end: str, progress: float) -> str:
    progress = max(0.0, min(1.0, progress))
    sr, sg, sb = _hex_to_rgb(start)
    er, eg, eb = _hex_to_rgb(end)
    mixed = (
        round(sr + (er - sr) * progress),
        round(sg + (eg - sg) * progress),
        round(sb + (eb - sb) * progress),
    )
    return _rgb_to_hex(mixed)


class BoletoCard(ctk.CTkFrame):
    def __init__(
        self,
        master,
        *,
        index: int,
        sindicato_options: Sequence[SindicatoOption],
        tipo_options: Sequence[str],
        data: dict | None = None,
        on_remove: Callable[["BoletoCard"], None] | None = None,
        on_sindicato_change: Callable[["BoletoCard", str], None] | None = None,
    ) -> None:
        super().__init__(
            master=master,
            fg_color=COLORS["card_bg"],
            border_width=1,
            border_color=COLORS["card_border"],
            corner_radius=10,
        )
        self._on_remove = on_remove
        self._on_sindicato_change = on_sindicato_change
        self._labels_by_key = {key: label for key, label in sindicato_options}
        self._keys_by_label = {label: key for key, label in sindicato_options}
        self._select_progress: dict[ctk.CTkOptionMenu, float] = {}
        self._select_target: dict[ctk.CTkOptionMenu, float] = {}
        self._select_jobs: dict[ctk.CTkOptionMenu, str | None] = {}

        default_data = {
            "sindicato_key": sindicato_options[0][0],
            "tipo_contribuicao": tipo_options[0] if tipo_options else "",
            "cnpj": "",
            "senha": "",
            "valor": "",
            "ano": datetime.now().year,
            "mes": datetime.now().month,
        }
        if data:
            default_data.update(data)

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(14, 10))
        self.header.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self.header,
            text=f"Boleto #{index}",
            font=FONTS["label"],
            text_color=COLORS["text_primary"],
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        self.remove_button = ctk.CTkButton(
            self.header,
            text="Remover",
            width=84,
            height=30,
            fg_color="transparent",
            hover_color="#FEE2E2",
            text_color=COLORS["danger"],
            font=FONTS["small"],
            command=self._remove_clicked,
        )
        self.remove_button.grid(row=0, column=1, sticky="e")

        sindicato_label = ctk.CTkLabel(self, text="Sindicato:", font=FONTS["body"], text_color=COLORS["text_secondary"])
        sindicato_label.grid(row=1, column=0, padx=(16, 8), sticky="w")
        tipo_label = ctk.CTkLabel(
            self,
            text="Tipo de contribuição:",
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
        )
        tipo_label.grid(row=1, column=1, padx=(8, 16), sticky="w")

        sindicato_values = [label for _, label in sindicato_options]
        initial_key = str(default_data["sindicato_key"])
        initial_label = self._labels_by_key.get(initial_key, sindicato_values[0])
        self.sindicato_var = ctk.StringVar(value=initial_label)
        self.sindicato_menu = ctk.CTkOptionMenu(
            self,
            values=sindicato_values,
            variable=self.sindicato_var,
            font=FONTS["small"],
            dropdown_font=FONTS["small"],
            command=self._sindicato_changed,
            fg_color=COLORS["select_bg"],
            button_color=COLORS["select_button"],
            button_hover_color=COLORS["select_button_hover"],
            text_color=COLORS["text_primary"],
        )
        self.sindicato_menu.grid(row=2, column=0, padx=(16, 8), pady=(6, 10), sticky="ew")
        self._setup_select_animation(self.sindicato_menu)

        tipo_values = list(tipo_options) or [""]
        self.tipo_var = ctk.StringVar(value=str(default_data["tipo_contribuicao"]))
        if self.tipo_var.get() not in tipo_values:
            self.tipo_var.set(tipo_values[0])
        self.tipo_menu = ctk.CTkOptionMenu(
            self,
            values=tipo_values,
            variable=self.tipo_var,
            font=FONTS["small"],
            dropdown_font=FONTS["small"],
            fg_color=COLORS["select_bg"],
            button_color=COLORS["select_button"],
            button_hover_color=COLORS["select_button_hover"],
            text_color=COLORS["text_primary"],
        )
        self.tipo_menu.grid(row=2, column=1, padx=(8, 16), pady=(6, 10), sticky="ew")
        self._setup_select_animation(self.tipo_menu)

        cnpj_label = ctk.CTkLabel(self, text="CNPJ:", font=FONTS["body"], text_color=COLORS["text_secondary"])
        cnpj_label.grid(row=3, column=0, padx=(16, 8), sticky="w")
        senha_label = ctk.CTkLabel(self, text="Senha:", font=FONTS["body"], text_color=COLORS["text_secondary"])
        senha_label.grid(row=3, column=1, padx=(8, 16), sticky="w")

        self.cnpj_entry = ctk.CTkEntry(self, font=FONTS["small"], placeholder_text="06323147000107")
        self.cnpj_entry.grid(row=4, column=0, padx=(16, 8), pady=(6, 10), sticky="ew")
        self.cnpj_entry.insert(0, str(default_data["cnpj"]))

        # --- senha com ícone dentro do "input" ---
        self._senha_visible = False

        # pega o estilo do CNPJ pra ficar igualzinho
        entry_fg = self.cnpj_entry.cget("fg_color")
        entry_border = self.cnpj_entry.cget("border_color")
        entry_border_w = self.cnpj_entry.cget("border_width")
        entry_radius = self.cnpj_entry.cget("corner_radius")
        entry_h = self.cnpj_entry.cget("height")  # pode vir None dependendo do tema

        self.senha_container = ctk.CTkFrame(
            self,
            fg_color=entry_fg,
            border_color=entry_border,
            border_width=entry_border_w,
            corner_radius=entry_radius,
        )
        self.senha_container.grid(row=4, column=1, padx=(8, 16), pady=(6, 10), sticky="ew")
        self.senha_container.grid_columnconfigure(0, weight=1)
        self.senha_container.grid_columnconfigure(1, weight=0)

        # Entry sem borda (a borda fica no container)
        self.senha_entry = ctk.CTkEntry(
            self.senha_container,
            font=FONTS["small"],
            placeholder_text="123456",
            show="*",
            fg_color=entry_fg,
            border_width=0,
        )
        self.senha_entry.grid(row=0, column=0, sticky="ew", padx=(8, 0), pady=2)
        self.senha_entry.insert(0, str(default_data["senha"]))

        self.senha_toggle_btn = ctk.CTkButton(
            self.senha_container,
            text="👁️",
            width=36,
            height=entry_h or 32,
            fg_color=entry_fg,                 # fica “dentro” do input
            hover_color=COLORS["select_bg_hover"],
            text_color=COLORS["text_primary"],
            font=FONTS["small"],
            corner_radius=entry_radius,
            command=self._toggle_senha_visibility,
        )
        self.senha_toggle_btn.grid(row=0, column=1, sticky="e", padx=(6, 6), pady=2)

        self._update_senha_toggle_ui()

        valor_label = ctk.CTkLabel(self, text="Valor:", font=FONTS["body"], text_color=COLORS["text_secondary"])
        valor_label.grid(row=5, column=0, padx=(16, 8), sticky="w")
        ano_label = ctk.CTkLabel(self, text="Ano:", font=FONTS["body"], text_color=COLORS["text_secondary"])
        ano_label.grid(row=5, column=1, padx=(8, 16), sticky="w")

        self.valor_entry = ctk.CTkEntry(self, font=FONTS["small"], placeholder_text="60,00")
        self.valor_entry.grid(row=6, column=0, padx=(16, 8), pady=(6, 10), sticky="ew")
        self.valor_entry.insert(0, str(default_data["valor"]))

        self.ano_entry = ctk.CTkEntry(self, font=FONTS["small"])
        self.ano_entry.grid(row=6, column=1, padx=(8, 16), pady=(6, 10), sticky="ew")
        self.ano_entry.insert(0, str(default_data["ano"]))

        mes_label = ctk.CTkLabel(self, text="Mês:", font=FONTS["body"], text_color=COLORS["text_secondary"])
        mes_label.grid(row=7, column=0, padx=(16, 8), pady=(0, 4), sticky="w")

        mes_values = [str(m) for m in range(1, 13)]
        mes_value = str(default_data["mes"])
        if mes_value not in mes_values:
            mes_value = "1"
        self.mes_var = ctk.StringVar(value=mes_value)
        self.mes_menu = ctk.CTkOptionMenu(
            self,
            values=mes_values,
            variable=self.mes_var,
            font=FONTS["small"],
            dropdown_font=FONTS["small"],
            fg_color=COLORS["select_bg"],
            button_color=COLORS["select_button"],
            button_hover_color=COLORS["select_button_hover"],
            text_color=COLORS["text_primary"],
        )
        self.mes_menu.grid(row=8, column=0, padx=(16, 8), pady=(6, 16), sticky="ew")
        self._setup_select_animation(self.mes_menu)

    def set_index(self, index: int) -> None:
        self.title_label.configure(text=f"Boleto #{index}")

    def set_remove_enabled(self, enabled: bool) -> None:
        self.remove_button.configure(state="normal" if enabled else "disabled")

    def set_tipo_options(self, tipo_options: Sequence[str], preserve_value: str | None = None) -> None:
        values = list(tipo_options) or [""]
        current = preserve_value if preserve_value is not None else self.tipo_var.get()
        self.tipo_menu.configure(values=values)
        self.tipo_var.set(current if current in values else values[0])

    def get_sindicato_key(self) -> str:
        label = self.sindicato_var.get()
        return self._keys_by_label.get(label, "")

    def get_tipo_value(self) -> str:
        return self.tipo_var.get()

    def get_payload(self) -> dict:
        return {
            "sindicato_key": self.get_sindicato_key(),
            "tipo_contribuicao": self.tipo_var.get(),
            "cnpj": self.cnpj_entry.get(),
            "senha": self.senha_entry.get(),
            "valor": self.valor_entry.get(),
            "ano": self.ano_entry.get(),
            "mes": self.mes_var.get(),
        }

    def set_interaction_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.sindicato_menu.configure(state=state)
        self.tipo_menu.configure(state=state)
        self.cnpj_entry.configure(state=state)
        self.senha_entry.configure(state=state)
        self.valor_entry.configure(state=state)
        self.ano_entry.configure(state=state)
        self.mes_menu.configure(state=state)
        self.remove_button.configure(state=state if enabled else "disabled")
        if not enabled:
            self._animate_select_to(self.sindicato_menu, 0.0)
            self._animate_select_to(self.tipo_menu, 0.0)
            self._animate_select_to(self.mes_menu, 0.0)

    def destroy(self) -> None:
        for job_id in self._select_jobs.values():
            if job_id:
                self.after_cancel(job_id)
        super().destroy()

    def _remove_clicked(self) -> None:
        if self._on_remove:
            self._on_remove(self)

    def _sindicato_changed(self, selected_label: str) -> None:
        if not self._on_sindicato_change:
            return
        sindicato_key = self._keys_by_label.get(selected_label, "")
        self._on_sindicato_change(self, sindicato_key)

    def _setup_select_animation(self, menu: ctk.CTkOptionMenu) -> None:
        self._select_progress[menu] = 0.0
        self._select_target[menu] = 0.0
        self._select_jobs[menu] = None
        self._apply_select_colors(menu, 0.0)
        menu.bind("<Enter>", lambda _event, m=menu: self._animate_select_to(m, 1.0), add="+")
        menu.bind("<Leave>", lambda _event, m=menu: self._animate_select_to(m, 0.0), add="+")

    def _animate_select_to(self, menu: ctk.CTkOptionMenu, target: float) -> None:
        self._select_target[menu] = max(0.0, min(1.0, target))
        if self._select_jobs.get(menu) is None:
            self._step_select_animation(menu)

    def _step_select_animation(self, menu: ctk.CTkOptionMenu) -> None:
        if not menu.winfo_exists():
            return

        current = self._select_progress.get(menu, 0.0)
        target = self._select_target.get(menu, 0.0)
        diff = target - current

        if abs(diff) < 0.03:
            current = target
        else:
            current += diff * 0.35

        self._select_progress[menu] = current
        self._apply_select_colors(menu, current)

        if current == target:
            self._select_jobs[menu] = None
            return

        job_id = self.after(16, lambda m=menu: self._step_select_animation(m))
        self._select_jobs[menu] = job_id

    def _apply_select_colors(self, menu: ctk.CTkOptionMenu, progress: float) -> None:
        bg = _blend_hex(COLORS["select_bg"], COLORS["select_bg_hover"], progress)
        button = _blend_hex(COLORS["select_button"], COLORS["select_button_hover"], progress)
        menu.configure(
            fg_color=bg,
            button_color=button,
            button_hover_color=COLORS["select_button_hover"],
            text_color=COLORS["text_primary"],
        )
    def _toggle_senha_visibility(self) -> None:
        self._senha_visible = not self._senha_visible
        self.senha_entry.configure(show="" if self._senha_visible else "*")
        self._update_senha_toggle_ui()

    def _update_senha_toggle_ui(self) -> None:
        # ícone muda conforme estado
        # (se não curtir 🙈, troca por outro texto tipo "👁‍🗨" ou "Ocultar")
        self.senha_toggle_btn.configure(text="🚫" if self._senha_visible else "👁")