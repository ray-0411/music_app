import customtkinter as ctk

from config import (
    APP_BASE_FONT_SIZE,
    APP_BUTTON_FONT_SIZE,
    APP_FONT_FAMILY,
    APP_LARGE_TITLE_FONT_SIZE,
    APP_SMALL_TITLE_FONT_SIZE,
    APP_TITLE_FONT_SIZE,
)


def base_font() -> ctk.CTkFont:
    return ctk.CTkFont(family=APP_FONT_FAMILY, size=APP_BASE_FONT_SIZE)


def button_font() -> ctk.CTkFont:
    return ctk.CTkFont(family=APP_FONT_FAMILY, size=APP_BUTTON_FONT_SIZE, weight="bold")


def small_title_font() -> ctk.CTkFont:
    return ctk.CTkFont(family=APP_FONT_FAMILY, size=APP_SMALL_TITLE_FONT_SIZE, weight="bold")


def title_font() -> ctk.CTkFont:
    return ctk.CTkFont(family=APP_FONT_FAMILY, size=APP_TITLE_FONT_SIZE, weight="bold")


def large_title_font() -> ctk.CTkFont:
    return ctk.CTkFont(family=APP_FONT_FAMILY, size=APP_LARGE_TITLE_FONT_SIZE, weight="bold")
