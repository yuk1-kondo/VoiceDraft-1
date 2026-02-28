"""メニューバーアイコン (NSStatusItem) コントローラ."""

from __future__ import annotations

import objc
from AppKit import (
    NSStatusBar,
    NSVariableStatusItemLength,
    NSMenu,
    NSMenuItem,
    NSApplication,
)
from Foundation import NSObject


class StatusBarController(NSObject):
    """VoiceDraft のメニューバーアイコンを管理する."""

    @objc.python_method
    def setup(self, quit_callback=None) -> None:
        self._quit_cb = quit_callback
        statusbar = NSStatusBar.systemStatusBar()
        self._item = statusbar.statusItemWithLength_(NSVariableStatusItemLength)
        self._item.button().setTitle_("🎙")
        self._item.button().setToolTip_("VoiceDraft — Ctrl+Shift+A で録音開始")

        menu = NSMenu.alloc().init()

        # 状態表示（非活性）
        self._status_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "待機中", None, ""
        )
        self._status_item.setEnabled_(False)
        menu.addItem_(self._status_item)
        menu.addItem_(NSMenuItem.separatorItem())

        # 終了
        quit_mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "VoiceDraft を終了", "quitAction:", "q"
        )
        quit_mi.setTarget_(self)
        menu.addItem_(quit_mi)

        self._item.setMenu_(menu)

    def quitAction_(self, sender) -> None:
        if self._quit_cb:
            self._quit_cb()
        else:
            NSApplication.sharedApplication().terminate_(None)

    @objc.python_method
    def set_status(self, text: str) -> None:
        """メニューの状態テキストを更新する."""
        if self._status_item:
            self._status_item.setTitle_(text)

    @objc.python_method
    def set_icon(self, emoji: str) -> None:
        """メニューバーアイコンの絵文字を変更する."""
        if self._item:
            self._item.button().setTitle_(emoji)
