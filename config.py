"""アプリケーション全体の設定定数."""

import os
from pathlib import Path

from dotenv import load_dotenv

# .env ファイルの読み込み
load_dotenv(Path(__file__).parent / ".env")

# --- ホットキー ---
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

# --- UI ---
WINDOW_BG = "#1a1a2e"
ACCENT_COLOR = "#e94560"
TEXT_COLOR = "#eaeaea"
SUBTEXT_COLOR = "#a0a0b0"
