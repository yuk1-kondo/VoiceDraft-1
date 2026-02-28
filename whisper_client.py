"""ローカル Whisper を使ったオフライン音声文字起こしクライアント.

Gemini API の代替として動作し、同じインターフェースを提供する。
AI による清書はなく、Whisper の生テキストをそのまま返す。
"""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf

import config


class WhisperClient:
    """openai-whisper を使ってローカルで音声文字起こしを行う."""

    def __init__(self) -> None:
        try:
            import whisper  # type: ignore
        except ImportError as e:
            raise ImportError(
                "openai-whisper がインストールされていません。\n"
                "  pip install openai-whisper\n"
                "または\n"
                "  uv add openai-whisper"
            ) from e

        model_name = config.WHISPER_MODEL
        print(f"🔧 Whisper モデル '{model_name}' を読み込み中...")
        self._model = whisper.load_model(model_name)
        print(f"✅ Whisper '{model_name}' 準備完了（オフラインモード）")

    def transcribe_and_structure(
        self,
        audio_bytes: bytes,
        context: str | None = None,
        emphasis: list[dict] | None = None,
    ) -> dict:
        """WAV バイト列を文字起こしして draft として返す.

        GeminiClient と同じシグネチャ。context は文字列結合で対応。
        """
        import whisper  # type: ignore

        # WAV → numpy array (float32 / 16kHz mono)
        buf = io.BytesIO(audio_bytes)
        data, samplerate = sf.read(buf, dtype="float32")

        # ステレオの場合はモノラルに変換
        if data.ndim > 1:
            data = data.mean(axis=1)

        # Whisper は 16kHz float32 を期待 — config.SAMPLE_RATE は 16000 なので通常不要
        if samplerate != 16000:
            import resampy  # type: ignore[import-not-found]
            data = resampy.resample(data, samplerate, 16000)

        # fp16=False: CPU でも安定動作
        result = self._model.transcribe(
            data,
            language="ja",
            fp16=False,
            verbose=False,
        )
        transcript: str = result["text"].strip()

        # コンテキストがある場合は末尾に追記
        if context:
            draft = f"{context}\n\n{transcript}"
        else:
            draft = transcript

        return {
            "draft": draft,
            "question": None,   # ローカルモードでは AI 問いかけなし
            "emphasis": [],
        }
