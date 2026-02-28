"""py2app build script — VoiceDraft.app を生成する.

使い方:
    pip install py2app
    python setup.py py2app

生成物: dist/VoiceDraft.app
"""

from setuptools import setup

APP = ["main_native.py"]

DATA_FILES = [
    # 必要なら画像・設定ファイルをここに追加
    # ("resources", ["resources/icon.icns"]),
]

OPTIONS = {
    "argv_emulation": False,  # macOS 13+ では False 推奨
    "packages": [
        "customtkinter",    # 万が一 fallback で使う場合
        "sounddevice",
        "soundfile",
        "numpy",
        "whisper",
        "google",
        "dotenv",
        "keyboard",
        "pyperclip",
    ],
    "frameworks": [],
    "includes": [
        "AppKit",
        "Foundation",
        "Quartz",
        "objc",
        "recorder",
        "gemini_client",
        "whisper_client",
        "injector",
        "config",
        "native_window",
        "native_statusbar",
        "app_native",
    ],
    "excludes": ["tkinter", "customtkinter"],
    "plist": {
        "CFBundleName":             "VoiceDraft",
        "CFBundleDisplayName":      "VoiceDraft",
        "CFBundleIdentifier":       "com.yk.voicedraft",
        "CFBundleVersion":          "1.0.0",
        "CFBundleShortVersionString": "1.0",
        "NSMicrophoneUsageDescription":
            "音声入力のためマイクを使用します。",
        "NSAccessibilityUsageDescription":
            "グローバルホットキーとテキスト入力のためアクセシビリティを使用します。",
        # メニューバーのみ表示（Dock に表示しない）
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
    },
    "iconfile": "resources/AppIcon.icns",  # アイコンがあれば使用
}

setup(
    app=APP,
    name="VoiceDraft",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
