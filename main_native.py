"""ネイティブ macOS モードのエントリーポイント."""

from app_native import NativeVoiceDraftApp


def main() -> None:
    app = NativeVoiceDraftApp()
    app.run()


if __name__ == "__main__":
    main()
