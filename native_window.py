"""AppKit NSPanel ベースのフローティングウィンドウ (native macOS 版).

Dynamic Island 風のピル型 / 展開型ウィンドウを NSPanel で実装する。
customtkinter の FloatingWindow と同じインターフェースを提供する。
"""

from __future__ import annotations

import enum
import math
from typing import Callable

import objc
from AppKit import (
    NSPanel,
    NSView,
    NSTextField,
    NSButton,
    NSScrollView,
    NSColor,
    NSFont,
    NSScreen,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
    NSBackingStoreBuffered,
    NSFloatingWindowLevel,
    NSTextAlignmentLeft,
    NSTextAlignmentCenter,
    NSLineBreakByWordWrapping,
)
from Foundation import NSMakeRect, NSObject

import config


# ── カラーヘルパー ─────────────────────────────────────────
def _c(h: str) -> NSColor:
    """#RRGGBB → NSColor."""
    h = h.lstrip("#")
    r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return NSColor.colorWithRed_green_blue_alpha_(r / 255, g / 255, b / 255, 1.0)


BG_COL   = _c(config.WINDOW_BG)
ACC_COL  = _c(config.ACCENT_COLOR)
TXT_COL  = _c(config.TEXT_COLOR)
SUB_COL  = _c(config.SUBTEXT_COLOR)
YEL_COL  = _c("#ffd866")
GRN_COL  = _c("#2d8f4e")
DARK_COL = _c("#0f0f23")
BORDER_COL = _c("#333355")

PILL_W, PILL_H     = 320, 60
EXPAND_W, EXPAND_H = 480, 420
TOP_MARGIN         = 50  # メニューバー下


# ── ボタンアクションハンドラ ────────────────────────────────
class _ActionHandler(NSObject):
    """ObjC ボタンのアクションを Python コールバックに転送する."""

    @objc.python_method
    def setup(self, callbacks: dict) -> None:
        self._callbacks = callbacks

    def stopAction_(self, sender) -> None:
        cb = self._callbacks.get("stop")
        if cb:
            cb()

    def confirmAction_(self, sender) -> None:
        cb = self._callbacks.get("confirm")
        if cb:
            cb()

    def cancelAction_(self, sender) -> None:
        cb = self._callbacks.get("cancel")
        if cb:
            cb()

    def retryAction_(self, sender) -> None:
        cb = self._callbacks.get("retry")
        if cb:
            cb()


# ── ユーティリティ関数 ──────────────────────────────────────
def _label(
    parent: NSView,
    text: str,
    rect,
    color: NSColor,
    size: float,
    bold: bool = False,
    align: int = NSTextAlignmentLeft,
    wrap: bool = False,
) -> NSTextField:
    """NSTextField（ラベル）を生成して parent に追加."""
    tf = NSTextField.alloc().initWithFrame_(rect)
    tf.setStringValue_(text)
    tf.setEditable_(False)
    tf.setBezeled_(False)
    tf.setDrawsBackground_(False)
    tf.setSelectable_(False)
    tf.setTextColor_(color)
    tf.setAlignment_(align)
    if bold:
        tf.setFont_(NSFont.boldSystemFontOfSize_(size))
    else:
        tf.setFont_(NSFont.systemFontOfSize_(size))
    if wrap:
        tf.setLineBreakMode_(NSLineBreakByWordWrapping)
    parent.addSubview_(tf)
    return tf


def _button(
    parent: NSView,
    title: str,
    rect,
    target: NSObject,
    action: str,
    bg: NSColor | None = None,
    fg: NSColor = TXT_COL,
    corner: float = 8.0,
    bordered: bool = False,
) -> NSButton:
    """スタイル済み NSButton を生成して parent に追加."""
    btn = NSButton.alloc().initWithFrame_(rect)
    btn.setTitle_(title)
    btn.setBordered_(bordered)
    btn.setBezelStyle_(0)
    btn.setFont_(NSFont.boldSystemFontOfSize_(13))
    btn.setTarget_(target)
    btn.setAction_(action)
    btn.setWantsLayer_(True)
    if bg:
        btn.layer().setBackgroundColor_(bg.CGColor())
    btn.layer().setCornerRadius_(corner)
    btn.setContentTintColor_(fg)
    parent.addSubview_(btn)
    return btn


def _colored_view(parent: NSView, rect, color: NSColor, corner: float = 0) -> NSView:
    """背景色付き NSView を生成して parent に追加."""
    v = NSView.alloc().initWithFrame_(rect)
    v.setWantsLayer_(True)
    v.layer().setBackgroundColor_(color.CGColor())
    if corner:
        v.layer().setCornerRadius_(corner)
    parent.addSubview_(v)
    return v


# ── メインクラス ────────────────────────────────────────────
class NativeFloatingWindow:
    """NSPanel ベースの Dynamic Island 風フローティングウィンドウ."""

    def __init__(self, callbacks: dict[str, Callable] | None = None) -> None:
        self._callbacks = callbacks or {}
        self._panel: NSPanel | None = None
        self._handler = _ActionHandler.alloc().init()
        self._handler.setup(self._callbacks)
        self._vol_fill: NSView | None = None
        self._draft_field: NSTextField | None = None
        self._question_field: NSTextField | None = None
        self._create_panel()

    # ── Public API ────────────────────────────────────────

    def show_recording(self) -> None:
        """録音中状態でウィンドウを表示."""
        self._resize(PILL_W, PILL_H, corner=26.0)
        self._clear()
        self._build_recording_ui()
        self._panel.orderFrontRegardless()

    def show_processing(self) -> None:
        """処理中状態に切り替え."""
        self._resize(PILL_W, PILL_H, corner=26.0)
        self._clear()
        self._build_processing_ui()

    def show_preview(self, draft: str, question: str | None) -> None:
        """プレビュー状態に切り替え."""
        self._resize(EXPAND_W, EXPAND_H, corner=16.0)
        self._clear()
        self._build_preview_ui()
        if self._draft_field:
            self._draft_field.setStringValue_(draft)
        if self._question_field:
            if question:
                self._question_field.setStringValue_(f"💬  {question}")
            else:
                self._question_field.setStringValue_("✅  「確定」でテキストを入力します")

    def update_volume(self, rms: float) -> None:
        """音量バーを更新 (0.0〜1.0)."""
        if self._vol_fill is None:
            return
        level = min(1.0, rms / 0.1)
        bar_total_w = PILL_W - 110  # ← アイコン・ラベル・ボタン除いた幅
        frame = self._vol_fill.frame()
        new_w = max(4.0, bar_total_w * level)
        self._vol_fill.setFrame_(NSMakeRect(
            frame.origin.x, frame.origin.y, new_w, frame.size.height
        ))

    def hide(self) -> None:
        """ウィンドウを非表示."""
        if self._panel:
            self._panel.orderOut_(None)

    def destroy(self) -> None:
        """ウィンドウを破棄."""
        if self._panel:
            self._panel.close()
            self._panel = None

    # ── 内部: パネル生成 ───────────────────────────────────

    def _create_panel(self) -> None:
        style = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel
        self._panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, PILL_W, PILL_H),
            style,
            NSBackingStoreBuffered,
            False,
        )
        self._panel.setLevel_(NSFloatingWindowLevel)
        self._panel.setBackgroundColor_(NSColor.clearColor())
        self._panel.setOpaque_(False)
        self._panel.setHasShadow_(True)
        self._panel.setMovableByWindowBackground_(True)
        self._panel.setHidesOnDeactivate_(False)

        # コンテナビュー（角丸ダーク背景）
        content = self._panel.contentView()
        content.setWantsLayer_(True)
        content.layer().setBackgroundColor_(BG_COL.CGColor())
        content.layer().setCornerRadius_(26.0)
        content.layer().setBorderWidth_(1.0)
        content.layer().setBorderColor_(BORDER_COL.CGColor())

        self._position(PILL_W, PILL_H)

    def _position(self, w: int, h: int) -> None:
        """画面上部中央に配置."""
        screen = NSScreen.mainScreen()
        sw = screen.frame().size.width
        sh = screen.visibleFrame().size.height + screen.visibleFrame().origin.y
        x = (sw - w) / 2
        y = sh - h - (TOP_MARGIN - 24)
        self._panel.setFrame_display_(
            NSMakeRect(x, y, w, h), False
        )

    def _resize(self, tw: int, th: int, corner: float = 26.0) -> None:
        """ウィンドウサイズ変更 + 角丸更新."""
        self._position(tw, th)
        cv = self._panel.contentView()
        cv.layer().setCornerRadius_(corner)

    def _clear(self) -> None:
        """コンテンツビューのサブビューを全削除."""
        cv = self._panel.contentView()
        for sub in list(cv.subviews()):
            sub.removeFromSuperview()
        self._vol_fill = None
        self._draft_field = None
        self._question_field = None

    # ── 内部: 録音中 UI ────────────────────────────────────

    def _build_recording_ui(self) -> None:
        cv = self._panel.contentView()
        W, H = PILL_W, PILL_H

        # 🎙 アイコン
        _label(cv, "🎙", NSMakeRect(12, (H - 24) / 2, 24, 24), ACC_COL, 16, align=NSTextAlignmentCenter)

        # ラベル
        _label(cv, "録音中", NSMakeRect(42, (H - 20) / 2, 60, 20), ACC_COL, 13, bold=True)

        # 音量バー（トラック）
        bar_x = 108
        bar_w = W - bar_x - 48
        track = _colored_view(cv, NSMakeRect(bar_x, (H - 4) / 2, bar_w, 4), _c("#2a2a4a"), corner=2.0)
        # 音量フィル
        self._vol_fill = _colored_view(track, NSMakeRect(0, 0, 4, 4), ACC_COL, corner=2.0)

        # ⏹ ボタン
        _button(
            cv, "⏹",
            NSMakeRect(W - 42, (H - 32) / 2, 32, 32),
            self._handler, "stopAction:",
            bg=ACC_COL, fg=NSColor.whiteColor(), corner=16.0,
        )

    # ── 内部: 処理中 UI ────────────────────────────────────

    def _build_processing_ui(self) -> None:
        cv = self._panel.contentView()
        W, H = PILL_W, PILL_H
        label = (
            "🔄  Whisper 文字起こし中..."
            if not config.GEMINI_API_KEY
            else "⏳  Gemini に送信中..."
        )
        _label(
            cv, label,
            NSMakeRect(0, (H - 20) / 2, W, 20),
            YEL_COL, 13, bold=True,
            align=NSTextAlignmentCenter,
        )

    # ── 内部: プレビュー UI ────────────────────────────────

    def _build_preview_ui(self) -> None:
        cv = self._panel.contentView()
        W, H = EXPAND_W, EXPAND_H
        PAD = 20

        # タイトル
        _label(cv, "📝  清書プレビュー",
               NSMakeRect(PAD, H - 44, W - PAD * 2, 24),
               TXT_COL, 16, bold=True)

        # 区切り線
        sep = _colored_view(cv, NSMakeRect(PAD, H - 52, W - PAD * 2, 1), BORDER_COL)

        # テキストエリア（NSTextField, スクロールなし for simplicity）
        TEXT_H = H - 52 - 24 - 50 - 60  # ≒ 234
        self._draft_field = _label(
            cv, "",
            NSMakeRect(PAD, H - 52 - TEXT_H, W - PAD * 2, TEXT_H),
            TXT_COL, 14, wrap=True,
        )
        self._draft_field.setSelectable_(True)
        self._draft_field.setDrawsBackground_(True)
        self._draft_field.setBackgroundColor_(DARK_COL)
        self._draft_field.setWantsLayer_(True)
        self._draft_field.layer().setCornerRadius_(8.0)

        # 問いかけラベル
        self._question_field = _label(
            cv, "💬  ...",
            NSMakeRect(PAD, 60, W - PAD * 2, 40),
            YEL_COL, 14, bold=True, wrap=True,
        )

        # ボタン行
        BTN_Y = 12
        _button(cv, "🎙  もっと話す",
                NSMakeRect(PAD, BTN_Y, 140, 34),
                self._handler, "retryAction:",
                fg=TXT_COL, corner=8.0)

        _button(cv, "✅  確定",
                NSMakeRect(PAD + 148, BTN_Y, 110, 34),
                self._handler, "confirmAction:",
                bg=GRN_COL, fg=NSColor.whiteColor(), corner=8.0)

        _button(cv, "❌  やめる",
                NSMakeRect(PAD + 268, BTN_Y, 110, 34),
                self._handler, "cancelAction:",
                fg=SUB_COL, corner=8.0)
