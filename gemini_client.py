"""Gemini API クライアント: 音声 → 清書テキスト + 問いかけ."""

from __future__ import annotations

import json
import re

from google import genai
from google.genai import types

import config

# --- システムプロンプト ---
SYSTEM_PROMPT = """\
あなたは音声入力アシスタントです。
ユーザーがマイクで口頭で述べた内容の音声データを受け取ります。

## 音声の分析
音声データから以下の特徴を読み取り、ユーザーが重要視しているポイントを推測してください:
- 話速の変化: ゆっくり話している部分は慎重に言葉を選んでいる
- 言い淀み・間: 「えーっと」や長い沈黙の後に続く内容は本当に伝えたいこと
- 繰り返し: 同じ内容を言い換えている部分は強調したいポイント
- 声のトーン変化: 熱を込めて話している部分は感情的に重要

## レスポンス形式
以下を **必ず JSON のみ** で返してください。余計な説明やコードフェンスは不要です。
{
  "draft": "ユーザーの発言をマークダウン形式で綺麗に清書したテキスト。文脈(context)が与えられている場合は、過去の清書と統合して1つの完成テキストにまとめる。emphasis情報がある場合は、ユーザーが重要視している部分をより丁寧に表現する。",
  "question": "テキストをさらに良くするための短い問いかけ（1文）。emphasis情報を活用し、ユーザーが言い淀んでいた部分や強調していた部分を優先的に深掘りする。これ以上深掘りが不要と判断したら null。",
  "emphasis": [{"text": "重要と判断したキーワードやフレーズ", "reason": "判断根拠"}]
}
"""


class GeminiClient:
    """Gemini API を使って音声を清書テキスト + 問いに変換する."""

    def __init__(self) -> None:
        if not config.GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY が設定されていません。.env ファイルを確認してください。"
            )
        self._client = genai.Client(
            api_key=config.GEMINI_API_KEY,
            http_options={"timeout": 20_000},  # 20秒タイムアウト (ms)
        )
        self._config = types.GenerateContentConfig(
            system_instruction=[types.Part.from_text(text=SYSTEM_PROMPT)],
            response_mime_type="application/json",
        )

    def transcribe_and_structure(
        self,
        audio_bytes: bytes,
        context: str | None = None,
        emphasis: list[dict] | None = None,
    ) -> dict:
        """音声バイトを送信し、清書テキストと問いを返す.

        Args:
            audio_bytes: WAV 形式のバイト列.
            context: 過去の清書テキスト（マージ用）.
            emphasis: 前回の音声分析で検出された重要ポイント.

        Returns:
            {"draft": str, "question": str | None, "emphasis": list}
        """
        parts: list[types.Part] = [
            types.Part.from_bytes(mime_type="audio/wav", data=audio_bytes),
        ]

        user_text = "この音声を清書してください。"
        if context:
            user_text += f"\n\n【これまでの清書テキスト（統合して更新してください）】\n{context}"
        if emphasis:
            lines = "\n".join(f"- {e['text']}: {e['reason']}" for e in emphasis)
            user_text += f"\n\n【前回の音声で検出された重要ポイント — 深掘りや清書に活用してください】\n{lines}"
        parts.append(types.Part.from_text(text=user_text))

        contents = [types.Content(role="user", parts=parts)]

        # ストリーミングで受信し、最終テキストを結合
        full_text = ""
        for chunk in self._client.models.generate_content_stream(
            model=config.GEMINI_MODEL,
            contents=contents,
            config=self._config,
        ):
            if chunk.text:
                full_text += chunk.text

        return self._parse_response(full_text)

    @staticmethod
    def _parse_response(text: str) -> dict:
        """API レスポンスから JSON をパースする."""
        # コードフェンスが含まれている場合は除去
        cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # パース失敗時はそのままテキストを draft として返す
            data = {"draft": text.strip(), "question": None}

        return {
            "draft": data.get("draft", ""),
            "question": data.get("question"),
            "emphasis": data.get("emphasis", []),
        }
