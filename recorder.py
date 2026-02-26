"""録音制御 + 沈黙検知モジュール."""

from __future__ import annotations

import io
import threading
import time
from typing import Callable

import numpy as np
import sounddevice as sd
import soundfile as sf

import config


class AudioRecorder:
    """マイク録音と RMS ベースの沈黙検知を行う."""

    def __init__(
        self,
        on_silence: Callable[[], None] | None = None,
        on_volume: Callable[[float], None] | None = None,
    ) -> None:
        self._on_silence = on_silence
        self._on_volume = on_volume

        self._is_recording = False
        self._audio_data: list[np.ndarray] = []
        self._lock = threading.Lock()

        # 沈黙検知用
        self._silence_start: float | None = None

        # 音声入力ストリーム（アプリ生存中ずっと開いておく）
        self._stream = sd.InputStream(
            samplerate=config.SAMPLE_RATE,
            channels=config.CHANNELS,
            dtype=config.DTYPE,
            callback=self._audio_callback,
        )
        self._stream.start()

    # --- Public API ---

    def start(self) -> None:
        """録音を開始する."""
        with self._lock:
            self._audio_data = []
            self._silence_start = None
            self._is_recording = True

    def stop(self) -> np.ndarray | None:
        """録音を停止し、録音データを返す. データがなければ None."""
        with self._lock:
            self._is_recording = False
            if not self._audio_data:
                return None
            return np.concatenate(self._audio_data, axis=0)

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def get_audio_bytes(self) -> bytes | None:
        """現在のバッファを WAV バイト列として返す（API 送信用）."""
        data = self.stop()
        if data is None:
            return None
        buf = io.BytesIO()
        sf.write(buf, data, config.SAMPLE_RATE, format="WAV")
        return buf.getvalue()

    def close(self) -> None:
        """ストリームを閉じる."""
        self._stream.stop()
        self._stream.close()

    # --- Internal ---

    def _audio_callback(
        self, indata: np.ndarray, frames: int, time_info, status
    ) -> None:
        """sounddevice のコールバック."""
        if status:
            print(f"  ⚠ {status}", flush=True)

        # RMS 計算 → 音量コールバック
        rms = float(np.sqrt(np.mean(indata**2)))
        if self._on_volume:
            self._on_volume(rms)

        with self._lock:
            if not self._is_recording:
                return
            self._audio_data.append(indata.copy())

        # 沈黙検知
        now = time.time()
        if rms < config.SILENCE_THRESHOLD:
            if self._silence_start is None:
                self._silence_start = now
            elif now - self._silence_start >= config.SILENCE_DURATION:
                # 沈黙が規定秒数続いた
                if self._on_silence and self._is_recording:
                    self._on_silence()
        else:
            self._silence_start = None
