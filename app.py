"""アプリケーションオーケストレーター: 全体のフローを管理する."""

from __future__ import annotations

import enum
import threading

import keyboard
import customtkinter as ctk

import config
from recorder import AudioRecorder
from injector import TextInjector
from ui.floating_window import AppState, FloatingWindow


def _create_stt_client():
    """API キーがあれば Gemini、なければローカル Whisper を返す."""
    if config.GEMINI_API_KEY:
        from gemini_client import GeminiClient
        return GeminiClient()
    else:
        print("ℹ  GEMINI_API_KEY 未設定 → ローカル Whisper モードで起動します")
        from whisper_client import WhisperClient
        return WhisperClient()


class Phase(enum.Enum):
    """アプリ全体のフェーズ."""

    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    PREVIEW = "preview"
    INJECTING = "injecting"


class App:
    """音声入力アシスタントのメインオーケストレーター."""

    def __init__(self) -> None:
        self._phase = Phase.IDLE
        self._draft: str = ""
        self._question: str | None = None
        self._emphasis: list[dict] = []

        # --- サブモジュール初期化 ---
        self._recorder = AudioRecorder(
            on_silence=self._on_silence_detected,
            on_volume=self._on_volume_update,
        )
        self._gemini = _create_stt_client()
        self._injector = TextInjector()

        # --- UI (customtkinter) ---
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self._root = ctk.CTk()
        self._root.withdraw()  # ルートウィンドウは非表示
        self._floating = FloatingWindow(
            self._root,
            callbacks={
                "stop": self._manual_stop_recording,
                "retry": self._start_followup_recording,
                "confirm": self._confirm_and_inject,
                "cancel": self._cancel,
            },
        )

        # --- グローバルホットキー ---
        keyboard.add_hotkey(config.HOTKEY, self._on_hotkey, suppress=True)
        keyboard.on_press_key("esc", self._on_esc_press)

    # --- Public ---

    def run(self) -> None:
        """アプリケーションを起動する (メインループ)."""
        print("=" * 50)
        print("  win-voice-injector v2")
        print("=" * 50)
        print(f"  起動/停止 : [{config.HOTKEY}]")
        print(f"  終了  : ターミナルで Ctrl+C")
        print("=" * 50)
        self._root.mainloop()

    def shutdown(self) -> None:
        """アプリケーションを終了する."""
        self._recorder.close()
        self._floating.destroy()
        self._root.quit()

    # --- ホットキーハンドラ ---

    def _on_hotkey(self) -> None:
        """ホットキーが押されたとき（トグル動作）."""
        if self._phase == Phase.IDLE:
            self._root.after(0, self._start_session)
        elif self._phase == Phase.RECORDING:
            self._root.after(0, self._manual_stop_recording)

    def _on_esc_press(self, event) -> None:
        """Esc: キャンセルして閉じる."""
        if self._phase == Phase.IDLE:
            return
        self._root.after(0, self._cancel)

    def _manual_stop_recording(self) -> None:
        """手動で録音を停止して処理に進む."""
        if self._phase == Phase.RECORDING:
            self._process_audio()

    # --- フロー制御 ---

    def _start_session(self) -> None:
        """新規セッション開始: ウィンドウ表示 + 録音開始."""
        print("\n🚀 セッション開始")
        self._draft = ""
        self._question = None
        self._emphasis = []

        # アクティブウィンドウを記憶
        self._injector.save_active_window()

        # UI 表示 → 録音開始
        self._phase = Phase.RECORDING
        self._floating.show(AppState.RECORDING)
        self._recorder.start()
        print("🎙  録音中...")

    def _start_followup_recording(self) -> None:
        """フォローアップ録音 (Space で追加回答)."""
        print("🎙  追加録音中...")
        self._phase = Phase.RECORDING
        self._floating.show(AppState.RECORDING)
        self._recorder.start()

    def _on_silence_detected(self) -> None:
        """沈黙検知コールバック (録音スレッドから呼ばれる)."""
        if self._phase != Phase.RECORDING:
            return
        # UI スレッドに処理を委譲
        self._root.after(0, self._process_audio)

    def _on_volume_update(self, rms: float) -> None:
        """音量更新コールバック (録音スレッドから呼ばれる)."""
        if self._phase == Phase.RECORDING:
            self._root.after(0, lambda: self._floating.update_volume(rms))

    def _process_audio(self) -> None:
        """録音停止 → Gemini API 送信."""
        print("⏹  沈黙検知 — 録音停止")
        audio_bytes = self._recorder.get_audio_bytes()
        if not audio_bytes:
            print("⚠  音声データなし")
            self._cancel()
            return

        self._phase = Phase.PROCESSING
        self._floating.show_processing()
        print("⏳  Gemini API に送信中...")

        # API 呼び出しはバックグラウンドスレッドで
        thread = threading.Thread(
            target=self._call_gemini, args=(audio_bytes,), daemon=True
        )
        thread.start()

    def _call_gemini(self, audio_bytes: bytes) -> None:
        """Gemini API をバックグラウンドで呼び出す."""
        try:
            context = self._draft if self._draft else None
            emphasis = self._emphasis if self._emphasis else None
            result = self._gemini.transcribe_and_structure(
                audio_bytes, context, emphasis,
            )
            self._draft = result.get("draft", "")
            self._question = result.get("question")
            new_emphasis = result.get("emphasis", [])
            if new_emphasis:
                self._emphasis.extend(new_emphasis)
                for e in new_emphasis:
                    print(f"🔍  重要: {e.get('text', '')} ({e.get('reason', '')})")
            print(f"📝  清書: {self._draft[:80]}...")
            if self._question:
                print(f"💬  問い: {self._question}")
            # UI 更新はメインスレッドで
            self._root.after(0, self._show_preview)
        except Exception as e:
            print(f"❌ Gemini API エラー: {e}")
            self._root.after(0, self._cancel)

    def _show_preview(self) -> None:
        """プレビュー画面を表示する."""
        self._phase = Phase.PREVIEW
        self._floating.show_preview(self._draft, self._question)

    def _confirm_and_inject(self) -> None:
        """確定: テキストを注入してセッション終了."""
        print("✅  確定 — テキスト注入中...")
        self._floating.hide()
        self._phase = Phase.INJECTING

        # 少し待ってからペースト (ウィンドウ切替のため)
        self._root.after(200, self._do_inject)

    def _do_inject(self) -> None:
        """実際のテキスト注入."""
        success = self._injector.inject_text(self._draft)
        if success:
            print("💾  テキストを入力しました")
        else:
            print("⚠  テキスト入力に失敗しました")
        self._phase = Phase.IDLE

    def _cancel(self) -> None:
        """キャンセル: 録音停止 + ウィンドウ非表示."""
        print("❌  キャンセル")
        if self._recorder.is_recording:
            self._recorder.stop()
        self._floating.hide()
        self._phase = Phase.IDLE
