"""テキスト注入: アクティブウィンドウへの貼り付け."""

from __future__ import annotations

import ctypes
import time

import pyperclip


user32 = ctypes.windll.user32

# --- Win32 仮想キーコード ---
VK_CONTROL = 0x11
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002


class TextInjector:
    """アクティブウィンドウを記憶し、テキストをペーストする."""

    def __init__(self) -> None:
        self._target_hwnd: int | None = None

    def save_active_window(self) -> None:
        """現在のフォアグラウンドウィンドウを保存する."""
        self._target_hwnd = user32.GetForegroundWindow()

    def inject_text(self, text: str) -> bool:
        """保存したウィンドウにテキストをペーストする.

        Returns:
            成功時 True.
        """
        if not self._target_hwnd:
            print("⚠ 注入先ウィンドウが記録されていません。")
            return False

        # クリップボードにコピー
        pyperclip.copy(text)

        # 保存したウィンドウをフォアグラウンドに復帰
        user32.SetForegroundWindow(self._target_hwnd)
        time.sleep(0.15)  # ウィンドウ切替待ち

        # Ctrl+V でペースト (Win32 API 直接: keyboard ライブラリの状態を汚さない)
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_V, 0, 0, 0)
        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.1)

        return True
