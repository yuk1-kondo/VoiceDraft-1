"""Native macOS アプリケーションオーケストレーター.

customtkinter の app.py を AppKit (PyObjC) で完全に置き換える。
Gemini API キーがなければ自動的にローカル Whisper にフォールバックする。
"""

from __future__ import annotations

import enum
import threading

import objc
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSEvent,
    NSKeyDownMask,
    NSEventModifierFlagControl,
    NSEventModifierFlagShift,
)
from Foundation import NSObject, NSOperationQueue

import config
from recorder import AudioRecorder
from injector import TextInjector
from native_window import NativeFloatingWindow
from native_statusbar import StatusBarController


# ── メインスレッド dispatch ────────────────────────────────
def _main(func) -> None:
    """func をメインスレッドで実行（スレッドセーフ）."""
    NSOperationQueue.mainQueue().addOperationWithBlock_(func)


# ── フェーズ ────────────────────────────────────────────────
class Phase(enum.Enum):
    IDLE       = "idle"
    RECORDING  = "recording"
    PROCESSING = "processing"
    PREVIEW    = "preview"
    INJECTING  = "injecting"


# ── AppDelegate ─────────────────────────────────────────────
class _AppDelegate(NSObject):
    """NSApplicationDelegate: 起動完了後にアプリを初期化する."""

    @objc.python_method
    def set_controller(self, controller: "NativeVoiceDraftApp") -> None:
        self._ctrl = controller

    def applicationDidFinishLaunching_(self, notif) -> None:
        self._ctrl._on_app_launched()

    def applicationShouldTerminateAfterLastWindowClosed_(self, sender) -> bool:
        return False


# ── メインコントローラ ────────────────────────────────────
class NativeVoiceDraftApp:
    """アプリ全体のフローを管理する（native macOS 版）."""

    def __init__(self) -> None:
        self._phase = Phase.IDLE
        self._draft: str = ""
        self._question: str | None = None
        self._emphasis: list[dict] = []
        self._hotkey_monitor = None

        # --- バックエンド ---
        self._recorder = AudioRecorder(
            on_silence=self._on_silence_detected,
            on_volume=self._on_volume_update,
        )
        self._injector = TextInjector()

        # STT クライアント選択
        if config.GEMINI_API_KEY:
            from gemini_client import GeminiClient
            self._stt = GeminiClient()
        else:
            print("ℹ  GEMINI_API_KEY 未設定 → ローカル Whisper モード")
            from whisper_client import WhisperClient
            self._stt = WhisperClient()

        # --- Cocoa アプリ ---
        self._app = NSApplication.sharedApplication()
        self._app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

        self._delegate = _AppDelegate.alloc().init()
        self._delegate.set_controller(self)
        self._app.setDelegate_(self._delegate)

    def run(self) -> None:
        """メインイベントループを開始する."""
        print("=" * 50)
        print("  VoiceDraft — Native macOS")
        print("=" * 50)
        print(f"  起動/停止 : [Ctrl+Shift+A]")
        print(f"  終了      : メニューバー → 終了")
        print("=" * 50)
        self._app.run()

    def _on_app_launched(self) -> None:
        """applicationDidFinishLaunching_ から呼ばれる."""
        # UI 初期化（メインスレッドで）
        self._window = NativeFloatingWindow(
            callbacks={
                "stop":    self._manual_stop_recording,
                "retry":   self._start_followup_recording,
                "confirm": self._confirm_and_inject,
                "cancel":  self._cancel,
            }
        )
        self._statusbar = StatusBarController.alloc().init()
        self._statusbar.setup(quit_callback=self.shutdown)

        # グローバルホットキー登録
        self._register_hotkey()
        print("✅  VoiceDraft 起動完了")

    # ── ホットキー ────────────────────────────────────────

    def _register_hotkey(self) -> None:
        """NSEvent でグローバルキーイベントを監視する."""
        def handle(event) -> None:
            flags = event.modifierFlags()
            key   = event.keyCode()
            ctrl  = bool(flags & NSEventModifierFlagControl)
            shift = bool(flags & NSEventModifierFlagShift)

            if ctrl and shift and key == 0:  # Ctrl+Shift+A (keyCode 0 = A)
                if self._phase == Phase.IDLE:
                    _main(self._start_session)
                elif self._phase == Phase.RECORDING:
                    _main(self._manual_stop_recording)
            elif key == 53 and self._phase != Phase.IDLE:  # Esc
                _main(self._cancel)

        self._hotkey_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSKeyDownMask, handle
        )

    # ── フロー制御 ─────────────────────────────────────────

    def _start_session(self) -> None:
        print("\n🚀 セッション開始")
        self._draft = ""
        self._question = None
        self._emphasis = []
        self._injector.save_active_window()

        self._phase = Phase.RECORDING
        self._statusbar.set_icon("🔴")
        self._statusbar.set_status("録音中...")
        self._window.show_recording()
        self._recorder.start()

    def _start_followup_recording(self) -> None:
        print("🎙  追加録音中...")
        self._phase = Phase.RECORDING
        self._statusbar.set_icon("🔴")
        self._statusbar.set_status("録音中（追加）...")
        self._window.show_recording()
        self._recorder.start()

    def _manual_stop_recording(self) -> None:
        if self._phase == Phase.RECORDING:
            self._process_audio()

    def _on_silence_detected(self) -> None:
        if self._phase == Phase.RECORDING:
            _main(self._process_audio)

    def _on_volume_update(self, rms: float) -> None:
        if self._phase == Phase.RECORDING:
            _main(lambda: self._window.update_volume(rms))

    def _process_audio(self) -> None:
        print("⏹  録音停止 — 処理中...")
        audio_bytes = self._recorder.get_audio_bytes()
        if not audio_bytes:
            print("⚠  音声データなし")
            self._cancel()
            return

        self._phase = Phase.PROCESSING
        self._statusbar.set_icon("⏳")
        self._statusbar.set_status("処理中...")
        self._window.show_processing()

        threading.Thread(
            target=self._call_stt, args=(audio_bytes,), daemon=True
        ).start()

    def _call_stt(self, audio_bytes: bytes) -> None:
        try:
            result = self._stt.transcribe_and_structure(
                audio_bytes,
                self._draft or None,
                self._emphasis or None,
            )
            self._draft    = result.get("draft", "")
            self._question = result.get("question")
            new_em = result.get("emphasis", [])
            if new_em:
                self._emphasis.extend(new_em)
            print(f"📝  清書: {self._draft[:80]}...")
            _main(self._show_preview)
        except Exception as e:
            print(f"❌ STT エラー: {e}")
            _main(self._cancel)

    def _show_preview(self) -> None:
        self._phase = Phase.PREVIEW
        self._statusbar.set_icon("📝")
        self._statusbar.set_status("プレビュー確認中...")
        self._window.show_preview(self._draft, self._question)

    def _confirm_and_inject(self) -> None:
        print("✅  確定 — テキスト注入中...")
        self._window.hide()
        self._phase = Phase.INJECTING
        self._statusbar.set_icon("🎙")
        self._statusbar.set_status("待機中")
        threading.Thread(target=self._delayed_inject, daemon=True).start()

    def _delayed_inject(self) -> None:
        import time
        time.sleep(0.2)
        success = self._injector.inject_text(self._draft)
        print("💾  テキストを入力しました" if success else "⚠  テキスト入力に失敗")
        self._phase = Phase.IDLE

    def _cancel(self) -> None:
        print("❌  キャンセル")
        if self._recorder.is_recording:
            self._recorder.stop()
        self._window.hide()
        self._statusbar.set_icon("🎙")
        self._statusbar.set_status("待機中")
        self._phase = Phase.IDLE

    def shutdown(self) -> None:
        """アプリを終了する."""
        if self._hotkey_monitor:
            NSEvent.removeMonitor_(self._hotkey_monitor)
        self._recorder.close()
        self._window.destroy()
        self._app.terminate_(None)
