"""win-voice-injector: Windows 常駐型音声入力アシスタント.

Win+Shift+V でフローティングウィンドウを表示し、
音声 → Gemini API で清書 → アクティブウィンドウに入力する。
"""

from app import App


def main() -> None:
    """エントリーポイント."""
    app = App()
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n終了します...")
    finally:
        app.shutdown()


if __name__ == "__main__":
    main()
