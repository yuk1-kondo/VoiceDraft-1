"""アプリケーション全体の設定定数."""

import os
from pathlib import Path

from dotenv import load_dotenv

# .env ファイルの読み込み
load_dotenv(Path(__file__).parent / ".env")

# --- ホットキー ---
# macOS では ctrl+shift+a = ⌃⇧A（アクセシビリティ権限が必要）
HOTKEY = "ctrl+shift+a"

# --- 録音 ---
SAMPLE_RATE = 16000  # Whisper 互換
CHANNELS = 1
DTYPE = "float32"

# --- 沈黙検知 ---
SILENCE_THRESHOLD = 0.01  # RMS 閾値 (高めで環境音に寛容)
SILENCE_DURATION = 2.5  # 秒 (フォールバック; 手動停止を推奨)

# --- Gemini API ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# GEMINI_MODEL = "gemini-3-flash-preview"
GEMINI_MODEL = "gemini-2.5-flash"

# --- ローカル Whisper (API キー未設定時の自動フォールバック) ---
# モデルサイズ: tiny / base / small / medium / large
# tiny=最速・精度低, base=バランス良好(推奨), small=高精度, medium=日本語向け最良
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

# --- UI ---
WINDOW_BG = "#1a1a2e"
ACCENT_COLOR = "#e94560"
TEXT_COLOR = "#eaeaea"
SUBTEXT_COLOR = "#a0a0b0"
