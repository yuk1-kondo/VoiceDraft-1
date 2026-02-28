#!/bin/bash
# VoiceDraft.app ビルドスクリプト
# 実行: bash build_app.sh

set -e

echo "=== VoiceDraft ネイティブアプリ ビルド ==="

# 依存確認
if ! command -v uv &>/dev/null; then
    echo "エラー: uv がインストールされていません"
    echo "  brew install uv"
    exit 1
fi

if ! command -v ffmpeg &>/dev/null; then
    echo "エラー: ffmpeg がインストールされていません"
    echo "  brew install ffmpeg"
    exit 1
fi

# 仮想環境セットアップ
echo "→ 依存パッケージをインストール中..."
uv sync

# py2app インストール
echo "→ py2app をインストール中..."
uv add py2app pyobjc-framework-Cocoa

# resources ディレクトリ作成（アイコンがない場合はスキップ）
mkdir -p resources

# ビルド
echo "→ VoiceDraft.app をビルド中..."
uv run python setup.py py2app 2>&1

echo ""
echo "✅ ビルド完了！"
echo "   dist/VoiceDraft.app を Applications フォルダにコピーして使えます"
echo ""
echo "初回起動時:"
echo "  1. dist/VoiceDraft.app を右クリック → 開く"
echo "  2. システム設定 → プライバシー → アクセシビリティ → VoiceDraft を追加"
echo "  3. システム設定 → プライバシー → マイク → VoiceDraft を許可"
