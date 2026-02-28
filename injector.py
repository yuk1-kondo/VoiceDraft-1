"""テキスト注入: macOS でアクティブウィンドウへの貼り付け."""

from __future__ import annotations

import subprocess
import time

import pyperclip


class TextInjector:
    """アクティブアプリを記憶し、テキストをペーストする (macOS版)."""

    def __init__(self) -> None:
        self._target_app: str | None = None

    def save_active_window(self) -> None:
        """現在のフロントアプリを保存する."""
        try:
            result = subprocess.run(
                [
                    "osascript", "-e",
                    'tell application "System Events" to get name of '
                    'first application process whose frontmost is true',
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )
            self._target_app = result.stdout.strip() or None
        except Exception as e:
            print(f"⚠ アクティブウィンドウの取得失敗: {e}")
            self._target_app = None

    def inject_text(self, text: str) -> bool:
        """保存したアプリにテキストをペーストする.

        Returns:
            成功時 True.
        """
        # クリップボードにコピー
        pyperclip.copy(text)

        # 保存したアプリをフロントに復帰
        if self._target_app:
            try:
                subprocess.run(
                    ["osascript", "-e", f'tell application "{self._target_app}" to activate'],
                    capture_output=True,
                    timeout=3,
                )
                time.sleep(0.3)  # ウィンドウ切替待ち
            except Exception as e:
                print(f"⚠ アプリ復帰失敗: {e}")

        # Cmd+V でペースト (osascript)
        try:
            subprocess.run(
                [
                    "osascript", "-e",
                    'tell application "System Events" to keystroke "v" using command down',
                ],
                capture_output=True,
                timeout=3,
            )
        except Exception as e:
            print(f"⚠ ペースト失敗: {e}")
            return False

        return True
