"""Dynamic Island 風フローティングウィンドウ.

customtkinter + Win32 API (WS_EX_NOACTIVATE) でフォーカスを奪わないウィンドウを実現する。
状態に応じてピル型 ↔ 展開型にアニメーション遷移する。
"""

from __future__ import annotations

import ctypes
import enum
from typing import Callable

import customtkinter as ctk

import config

# --- Win32 定数 ---
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
SWP_FRAMECHANGED = 0x0020
SWP_NOACTIVATE = 0x0010
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
HWND_TOPMOST = -1

user32 = ctypes.windll.user32


class AppState(enum.Enum):
    """フローティングウィンドウの表示状態."""

    RECORDING = "recording"
    PROCESSING = "processing"
    PREVIEW = "preview"


class FloatingWindow:
    """Dynamic Island 風フローティングウィンドウ."""

    # --- サイズ定数 ---
    PILL_W = 320
    PILL_H = 60
    EXPANDED_W = 480
    EXPANDED_H = 420
    TOP_MARGIN = 24

    def __init__(
        self,
        root: ctk.CTk,
        callbacks: dict[str, Callable[[], None]] | None = None,
    ) -> None:
        self._root = root
        self._callbacks = callbacks or {}
        self._window: ctk.CTkToplevel | None = None
        self._state = AppState.RECORDING

        # UI 要素への参照
        self._status_label: ctk.CTkLabel | None = None
        self._volume_bar: ctk.CTkProgressBar | None = None
        self._draft_textbox: ctk.CTkTextbox | None = None
        self._question_label: ctk.CTkLabel | None = None
        self._container: ctk.CTkFrame | None = None

    # --- Public API ---

    def show(self, state: AppState = AppState.RECORDING) -> None:
        """ウィンドウを表示して指定状態にする."""
        if self._window is None or not self._window.winfo_exists():
            self._create_window()
        self._switch_state(state)
        self._window.deiconify()
        self._root.after(50, self._apply_no_activate)

    def hide(self) -> None:
        """ウィンドウを非表示にする."""
        if self._window and self._window.winfo_exists():
            self._window.withdraw()

    def destroy(self) -> None:
        """ウィンドウを破棄する."""
        if self._window and self._window.winfo_exists():
            self._window.destroy()
            self._window = None

    def update_volume(self, rms: float) -> None:
        """音量メーターを更新する (0.0 ~ 1.0)."""
        if self._volume_bar and self._state == AppState.RECORDING:
            level = min(1.0, rms / 0.1)
            self._volume_bar.set(level)

    def show_processing(self) -> None:
        """処理中状態に切り替える."""
        self._switch_state(AppState.PROCESSING)

    def show_preview(self, draft: str, question: str | None) -> None:
        """プレビュー状態に切り替え、清書テキストと質問を表示する."""
        self._switch_state(AppState.PREVIEW)
        if self._draft_textbox:
            self._draft_textbox.configure(state="normal")
            self._draft_textbox.delete("1.0", "end")
            self._draft_textbox.insert("1.0", draft)
            self._draft_textbox.configure(state="disabled")
        if self._question_label:
            if question:
                self._question_label.configure(text=f"💬  {question}")
            else:
                self._question_label.configure(
                    text="✅  深掘り不要です。「確定」で入力できます。"
                )

    # --- Internal: ウィンドウ生成 ---

    def _create_window(self) -> None:
        """ウィンドウ本体を生成する."""
        self._window = ctk.CTkToplevel(self._root)
        self._window.title("")
        self._window.overrideredirect(True)
        self._window.attributes("-topmost", True)
        self._window.configure(fg_color=config.WINDOW_BG)
        self._set_geometry(self.PILL_W, self.PILL_H)

        self._container = ctk.CTkFrame(
            self._window,
            fg_color=config.WINDOW_BG,
            corner_radius=26,
            border_width=1,
            border_color="#333355",
        )
        self._container.pack(fill="both", expand=True, padx=2, pady=2)

    def _switch_state(self, state: AppState) -> None:
        """表示状態を切り替える."""
        self._state = state

        if state == AppState.PREVIEW:
            target_w, target_h, cr = self.EXPANDED_W, self.EXPANDED_H, 16
        else:
            target_w, target_h, cr = self.PILL_W, self.PILL_H, 26

        self._container.configure(corner_radius=cr)

        for widget in self._container.winfo_children():
            widget.destroy()

        if state == AppState.RECORDING:
            self._build_recording_ui()
        elif state == AppState.PROCESSING:
            self._build_processing_ui()
        elif state == AppState.PREVIEW:
            self._build_preview_ui()

        self._animate_resize(target_w, target_h)

    # --- Internal: アニメーション ---

    def _animate_resize(self, tw: int, th: int, steps: int = 8) -> None:
        """ウィンドウサイズを ease-out cubic で遷移する."""
        if not self._window or not self._window.winfo_exists():
            return
        self._window.update_idletasks()
        cw = self._window.winfo_width()
        ch = self._window.winfo_height()

        if cw <= 1 or (cw == tw and ch == th):
            self._set_geometry(tw, th)
            return

        interval = max(1, 120 // steps)

        def step(i: int) -> None:
            if not self._window or not self._window.winfo_exists():
                return
            if i >= steps:
                self._set_geometry(tw, th)
                return
            t = 1 - (1 - (i + 1) / steps) ** 3
            self._set_geometry(int(cw + (tw - cw) * t), int(ch + (th - ch) * t))
            self._window.after(interval, lambda: step(i + 1))

        step(0)

    def _set_geometry(self, w: int, h: int) -> None:
        """ウィンドウを画面上部中央に配置する."""
        if not self._window:
            return
        sw = self._window.winfo_screenwidth()
        x = (sw - w) // 2
        self._window.geometry(f"{w}x{h}+{x}+{self.TOP_MARGIN}")

    # --- Internal: 録音中 UI (ピル型) ---

    def _build_recording_ui(self) -> None:
        """コンパクトなピル型の録音 UI."""
        inner = ctk.CTkFrame(self._container, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=10)

        ctk.CTkLabel(
            inner, text="🎙", font=ctk.CTkFont(size=16),
            text_color=config.ACCENT_COLOR, width=24,
        ).pack(side="left", padx=(0, 6))

        self._status_label = ctk.CTkLabel(
            inner, text="録音中",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=config.ACCENT_COLOR,
        )
        self._status_label.pack(side="left", padx=(0, 10))

        self._volume_bar = ctk.CTkProgressBar(
            inner, height=4,
            progress_color=config.ACCENT_COLOR, fg_color="#2a2a4a",
            corner_radius=2,
        )
        self._volume_bar.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._volume_bar.set(0)

        ctk.CTkButton(
            inner, text="⏹", command=self._callbacks.get("stop"),
            font=ctk.CTkFont(size=13),
            fg_color=config.ACCENT_COLOR, hover_color="#c73850",
            corner_radius=16, width=34, height=34,
        ).pack(side="left")

    # --- Internal: 処理中 UI (ピル型) ---

    def _build_processing_ui(self) -> None:
        """コンパクトなピル型の処理中 UI."""
        ctk.CTkLabel(
            self._container, text="⏳  Gemini に送信中...",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#ffd866",
        ).pack(expand=True)

    # --- Internal: プレビュー UI (展開型) ---

    def _build_preview_ui(self) -> None:
        """展開型のプレビュー UI."""
        ctk.CTkLabel(
            self._container, text="📝  清書プレビュー",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=config.TEXT_COLOR, anchor="w",
        ).pack(fill="x", padx=20, pady=(16, 8))

        ctk.CTkFrame(
            self._container, height=1, fg_color="#333355",
        ).pack(fill="x", padx=20, pady=(0, 8))

        self._draft_textbox = ctk.CTkTextbox(
            self._container, font=ctk.CTkFont(size=14),
            fg_color="#0f0f23", text_color=config.TEXT_COLOR,
            wrap="word", activate_scrollbars=True, corner_radius=8,
        )
        self._draft_textbox.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        self._draft_textbox.configure(state="disabled")

        self._question_label = ctk.CTkLabel(
            self._container, text="💬  ...",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#ffd866", wraplength=self.EXPANDED_W - 60,
            anchor="w", justify="left",
        )
        self._question_label.pack(fill="x", padx=20, pady=(4, 8))

        # 操作ボタン
        bf = ctk.CTkFrame(self._container, fg_color="transparent")
        bf.pack(fill="x", padx=20, pady=(4, 12))

        ctk.CTkButton(
            bf, text="🎙  もっと話す", command=self._callbacks.get("retry"),
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="transparent", hover_color="#2a2a4a",
            border_width=1, border_color="#555577",
            text_color=config.TEXT_COLOR, corner_radius=8,
            width=140, height=34,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            bf, text="✅  確定", command=self._callbacks.get("confirm"),
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#2d8f4e", hover_color="#247a40",
            corner_radius=8, width=120, height=34,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            bf, text="❌  やめる", command=self._callbacks.get("cancel"),
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="transparent", hover_color="#2a2a4a",
            border_width=1, border_color="#444466",
            text_color="#888899", corner_radius=8,
            width=120, height=34,
        ).pack(side="left")

    # --- Internal: Win32 フォーカス制御 ---

    def _apply_no_activate(self) -> None:
        """WS_EX_NOACTIVATE を適用してフォーカスを奪わないようにする."""
        if not self._window or not self._window.winfo_exists():
            return
        hwnd = user32.GetParent(self._window.winfo_id())
        if not hwnd:
            hwnd = self._window.winfo_id()

        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ex_style |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
        user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0, 0, 0, 0,
            SWP_FRAMECHANGED | SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE,
        )
