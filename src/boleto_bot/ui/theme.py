from __future__ import annotations

from typing import Any

WINDOW_WIDTH = 600
WINDOW_HEIGHT = 724
WINDOW_GEOMETRY = f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}"

COLORS = {
    "bg": "#F3F4F6",
    "card_bg": "#FFFFFF",
    "card_border": "#D1D5DB",
    "text_primary": "#111827",
    "text_secondary": "#374151",
    "muted": "#6B7280",
    "danger": "#DC2626",
    "button": "#111827",
    "button_hover": "#1F2937",
    "select_bg": "#E5E7EB",
    "select_bg_hover": "#D1D5DB",
    "select_button": "#9CA3AF",
    "select_button_hover": "#6B7280",
}

FONTS = {
    "title": ("Segoe UI", 30, "bold"),
    "subtitle": ("Segoe UI", 15),
    "section_title": ("Segoe UI", 13, "bold"),
    "label": ("Segoe UI", 18),
    "body": ("Segoe UI", 16),
    "small": ("Segoe UI", 14),
    "button": ("Segoe UI", 18, "bold"),
}


def apply_theme(root: Any) -> None:
    import customtkinter as ctk

    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    root.configure(fg_color=COLORS["bg"])
