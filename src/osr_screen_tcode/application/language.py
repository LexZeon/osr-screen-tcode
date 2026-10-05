"""Language selection, age confirmation and analysis labels.

Moved without changing behavior for 2.1.0; application state remains on self.
"""
from __future__ import annotations
import os
import sys
import locale
from pathlib import Path
from ..screen_geometry import move_physical_window
import tkinter as tk
from ..ui_widgets import monitor_workarea
from .translations import TRACKER_MODE_CHOICES, TRACKER_MODE_EN, UI_TEXT_EN, UI_TEXT_REVERSE_EN


class LanguageMixin:
    def _resolve_ui_language(self, requested: str = "auto", allow_saved: bool = True) -> str:
        requested = (requested or "auto").lower()
        if requested in {"zh", "cn"}:
            return "zh"
        if requested == "en":
            return "en"
        env_language = os.environ.get("OSR_SCREEN_TCODE_LANG", "").lower()
        if env_language in {"zh", "cn"}:
            return "zh"
        if env_language == "en":
            return "en"

        path_hint = " ".join(
            [
                str(Path(getattr(sys, "executable", ""))),
                str(Path.cwd()),
            ]
        ).lower()
        if "windows-en" in path_hint or "english" in path_hint:
            return "en"
        if "windows-cn" in path_hint or "chinese" in path_hint:
            return "zh"

        if allow_saved and hasattr(self, "config_model"):
            saved_language = str(self.config_model.extra.get("ui_language", "")).lower()
            if saved_language in {"zh", "cn"}:
                return "zh"
            if saved_language == "en":
                return "en"
        locale_name = (locale.getlocale()[0] or "").lower()
        return "zh" if locale_name.startswith("zh") else "en"

    def _confirm_adult_use_or_exit(self) -> None:
        accepted = tk.BooleanVar(value=False)
        dialog = tk.Toplevel(self)
        dialog.title("Simulation Test / 模拟测试")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)

        body = tk.Frame(dialog, padx=22, pady=18)
        body.pack(fill="both", expand=True)
        tk.Label(
            body,
            text="SIMULATION TEST",
            font=("TkDefaultFont", 18, "bold"),
            foreground="#8a1f11",
        ).pack(anchor="w")
        tk.Label(
            body,
            text="模拟测试确认 / Simulation test notice",
            font=("TkDefaultFont", 11),
            foreground="#8a1f11",
        ).pack(anchor="w", pady=(2, 10))
        tk.Label(
            body,
            text=(
                "For visual-analysis and robot-arm simulation experiments.\n"
                "Physical robot-arm mapping is unverified. Start with Log only and no hardware. "
                "The preview is not sensor feedback.\n\n"
                "用于视觉分析与机械臂模拟实验。实际机械臂映射尚未验证；"
                "请先使用 Log only，不连接硬件。预览不代表传感器反馈。"
            ),
            justify="left",
            wraplength=560,
            padx=0,
            pady=14,
        ).pack(anchor="w")
        button_row = tk.Frame(body)
        button_row.pack(fill="x", pady=(8, 0))

        def accept() -> None:
            accepted.set(True)
            dialog.destroy()

        def decline() -> None:
            accepted.set(False)
            dialog.destroy()

        tk.Button(
            button_row,
            text="Continue / 继续",
            command=accept,
            width=28,
        ).pack(side="left")
        tk.Button(
            button_row,
            text="Exit / 退出",
            command=decline,
            width=24,
        ).pack(side="right")
        dialog.bind("<Return>", lambda _event: accept())
        dialog.bind("<Escape>", lambda _event: decline())
        dialog.protocol("WM_DELETE_WINDOW", decline)
        dialog.update_idletasks()
        left, top, right, bottom = monitor_workarea(self)
        x = left + max(0, (right-left-dialog.winfo_width()) // 2)
        y = top + max(0, (bottom-top-dialog.winfo_height()) // 2)
        move_physical_window(dialog, x, y)
        dialog.lift()
        dialog.focus_force()
        dialog.grab_set()
        self.wait_window(dialog)
        if not accepted.get():
            self.destroy()
            raise SystemExit(0)

    def _choose_ui_language(self, requested: str = "auto") -> str:
        requested = (requested or "auto").lower()
        default_language = self._resolve_ui_language(requested, allow_saved=True)
        if requested in {"zh", "cn", "en"}:
            return default_language

        chosen = tk.StringVar(value=default_language)
        dialog = tk.Toplevel(self)
        dialog.title("Choose Language / 选择语言")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)

        body = tk.Frame(dialog, padx=24, pady=18)
        body.pack(fill="both", expand=True)
        tk.Label(
            body,
            text="Choose Interface Language",
            font=("TkDefaultFont", 16, "bold"),
        ).pack(anchor="w")
        tk.Label(
            body,
            text="选择界面语言",
            foreground="#555555",
            pady=4,
        ).pack(anchor="w")
        button_row = tk.Frame(body)
        button_row.pack(fill="x", pady=(14, 0))

        def pick(value: str) -> None:
            chosen.set(value)
            dialog.destroy()

        tk.Button(button_row, text="English", command=lambda: pick("en"), width=18).pack(side="left", padx=(0, 10))
        tk.Button(button_row, text="中文", command=lambda: pick("zh"), width=18).pack(side="left")
        dialog.bind("<Return>", lambda _event: pick(default_language))
        dialog.bind("<Escape>", lambda _event: pick(default_language))
        dialog.protocol("WM_DELETE_WINDOW", lambda: pick(default_language))
        dialog.update_idletasks()
        left, top, right, bottom = monitor_workarea(self)
        x = left + max(0, (right-left-dialog.winfo_width()) // 2)
        y = top + max(0, (bottom-top-dialog.winfo_height()) // 2)
        move_physical_window(dialog, x, y)
        dialog.lift()
        dialog.focus_force()
        dialog.grab_set()
        self.wait_window(dialog)
        return "zh" if chosen.get() == "zh" else "en"

    def _t(self, text: str) -> str:
        if self.ui_language != "en":
            return UI_TEXT_REVERSE_EN.get(text, text)
        return UI_TEXT_EN.get(text, text)

    def _tracker_choices(self) -> tuple[str, ...]:
        if self.ui_language != "en":
            return TRACKER_MODE_CHOICES
        return tuple(TRACKER_MODE_EN.get(choice, choice) for choice in TRACKER_MODE_CHOICES)

    def _tracker_display(self, value: str) -> str:
        value = self._normalize_tracker_mode(value)
        if self.ui_language != "en":
            return value
        return TRACKER_MODE_EN.get(value, value)

    def _tracker_internal(self, value: str) -> str:
        reverse = {display: internal for internal, display in TRACKER_MODE_EN.items()}
        return self._normalize_tracker_mode(reverse.get(value, value))

    def _set_tracker_mode(self, value: str) -> None:
        self.tracker_mode.set(self._tracker_display(value))
