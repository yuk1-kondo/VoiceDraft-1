# 🎙 VoiceDraft

> 喋るだけで、伝わるテキストに。

言語化が苦手でも大丈夫。話した内容を AI が自動で清書し、アクティブウィンドウにそのまま入力する Windows 常駐型アシスタントです。

![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue)
![Windows](https://img.shields.io/badge/OS-Windows-0078d4)
![Gemini API](https://img.shields.io/badge/AI-Gemini%20API-orange)

## ✨ 特徴

- **話すだけ** — キーボードで文章を打つ必要なし
- **AI が清書** — 「えーっと」や言い直しも綺麗に整形
- **対話で磨く** — AI の問いかけに答えて、テキストをブラッシュアップ
- **そのまま入力** — 確定するとアクティブウィンドウに自動ペースト
- **邪魔しない UI** — Dynamic Island 風のコンパクトなフローティングウィンドウ

## 🎬 フロー

```
Ctrl+Shift+A → 🎙 録音 → ⏳ AI清書 → 📝 プレビュー → ✅ 確定 → 入力完了！
                  ↑                        │
                  └── 🎙 もっと話す ────────┘
```

1. `Ctrl+Shift+A` でセッション開始（録音開始）
2. 自由に話す — 言い直し OK、詰まっても OK
3. `Ctrl+Shift+A` or ⏹ ボタンで録音停止（沈黙でも自動停止）
4. AI が清書テキストをプレビュー表示
5. 「もっと話す」で追加情報を伝えるか、「確定」でテキスト入力

## 📦 セットアップ

### 前提条件

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) パッケージマネージャー
- [Gemini API キー](https://aistudio.google.com/apikey)

### インストール

```bash
git clone https://github.com/yourname/voice-draft.git
cd voice-draft
uv sync
```

### 設定

```bash
cp .env.example .env
```

`.env` を編集して API キーを設定：

```
GEMINI_API_KEY=your_api_key_here
```

## 🚀 使い方

```bash
uv run main.py
```

### 操作方法

| 操作 | 方法 |
|------|------|
| 起動 / 録音停止 | `Ctrl+Shift+A`（トグル） |
| 録音停止 | ⏹ ボタン / 沈黙検知（自動） |
| もっと話す | 🎙 ボタン |
| 確定（テキスト入力） | ✅ ボタン |
| キャンセル | ❌ ボタン / `Esc` |

> **💡 ヒント**: ホットキーは `config.py` の `HOTKEY` で変更できます。

## 🏗 モジュール構成

```
voice-draft/
├── main.py              # エントリーポイント
├── app.py               # オーケストレーター（状態管理）
├── config.py            # 設定定数
├── recorder.py          # 録音 + 沈黙検知
├── gemini_client.py     # Gemini API クライアント
├── injector.py          # テキスト注入（Win32 API）
├── ui/
│   └── floating_window.py  # Dynamic Island 風 UI
├── .env.example         # 環境変数テンプレート
└── pyproject.toml       # プロジェクト設定
```

## ⚙ カスタマイズ

`config.py` で各種設定を変更できます：

| 設定 | デフォルト | 説明 |
|------|-----------|------|
| `HOTKEY` | `ctrl+shift+a` | 起動/停止ホットキー |
| `SILENCE_DURATION` | `2.5` | 沈黙検知の秒数 |
| `SILENCE_THRESHOLD` | `0.01` | 沈黙判定の RMS 閾値 |
| `GEMINI_MODEL` | `gemini-2.5-flash` | 使用する AI モデル |

## 📄 ライセンス

MIT
