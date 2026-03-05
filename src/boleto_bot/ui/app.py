from __future__ import annotations

import customtkinter as ctk

from .screens import MainScreen
from .theme import WINDOW_GEOMETRY, WINDOW_HEIGHT, WINDOW_WIDTH, apply_theme


class BoletoBotApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        apply_theme(self)

        self.title("Robô Emitente de Boletos")
        self.geometry(WINDOW_GEOMETRY)
        self.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.maxsize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self.screen = MainScreen(self)
        self.screen.pack(fill="both", expand=True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self) -> None:
        try:
            self.screen.persist_session_before_close()
        finally:
            self.destroy()


def run() -> None:
    app = BoletoBotApp()
    app.mainloop()
