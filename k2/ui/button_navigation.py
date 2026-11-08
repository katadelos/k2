"""Directional focus and activation for readers with physical navigation keys."""

from typing import ClassVar

from PyQt5 import sip
from PyQt5.QtCore import (
    Q_ARG,
    QEvent,
    QMetaObject,
    QObject,
    QPointF,
    QRectF,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtQuick import QQuickItem


def items(root):
    for child in root.childItems():
        if child.isVisible():
            yield child
            yield from items(child)


class ButtonNavigation(QObject):
    changed = pyqtSignal()
    requested = pyqtSignal(str)

    _KEYS: ClassVar[dict[int, str]] = {
        Qt.Key_Up: "up",
        Qt.Key_Down: "down",
        Qt.Key_Left: "left",
        Qt.Key_Right: "right",
        Qt.Key_Return: "select",
        Qt.Key_Enter: "select",
        Qt.Key_Space: "select",
        Qt.Key_Escape: "back",
        Qt.Key_Back: "back",
        Qt.Key_Home: "home",
        Qt.Key_Menu: "menu",
        Qt.Key_F6: "keyboard",
        Qt.Key_PageUp: "previous",
        Qt.Key_PageDown: "next",
    }

    def __init__(self, enabled, parent=None):
        super().__init__(parent)
        self.enabled = enabled
        self.window = None
        self._focus_rect = QRectF()
        self._scopes = []
        self._keyboards = []

    def attach(self, window):
        self.window = window
        if self.enabled:
            window.activeFocusItemChanged.connect(self._update_focus_rect)
            QGuiApplication.instance().installEventFilter(self)

    def close(self):
        if self.enabled:
            QGuiApplication.instance().removeEventFilter(self)
        self.window = None

    def eventFilter(self, watched, event):
        if event.type() not in (QEvent.KeyPress, QEvent.ShortcutOverride):
            return False
        action = self._KEYS.get(event.key())
        if action is None:
            return False
        if event.type() == QEvent.KeyPress:
            self.handleAction(action)
        event.accept()
        return True

    def _register(self, collection, item, priority=0):
        if self.enabled and isinstance(item, QQuickItem):
            entry = (priority, item)
            collection.append(entry)
            item.destroyed.connect(lambda: collection.remove(entry))

    @pyqtSlot(QObject, int)
    def registerScope(self, item, priority):
        self._register(self._scopes, item, priority)

    @pyqtSlot(QObject)
    def registerKeyboard(self, item):
        self._register(self._keyboards, item)

    def _keyboard(self):
        if self.window is None:
            return None
        scope = self._scope()
        return next(
            (
                item
                for _, item in self._keyboards
                if item.isVisible() and scope.isAncestorOf(item)
            ),
            None,
        )

    def _scope(self):
        if self.window is None:
            return None
        return max(
            (
                (priority, item)
                for priority, item in self._scopes
                if item.isVisible()
                and item.isEnabled()
                and item.window() is self.window
            ),
            key=lambda entry: entry[0],
            default=(0, self.window.contentItem()),
        )[1]

    def _candidates(self, root):
        return [
            item
            for item in items(root)
            if item.isEnabled()
            and item.activeFocusOnTab()
            and (
                item.metaObject().indexOfSignal(b"clicked()") >= 0
                or item.property("cursorPosition") is not None
            )
            and item.width() > 0
            and item.height() > 0
        ]

    def _rect(self, item):
        if self.window is None:
            return QRectF()
        position = item.mapToItem(self.window.contentItem(), QPointF(0, 0))
        end = item.mapToItem(
            self.window.contentItem(), QPointF(item.width(), item.height())
        )
        return QRectF(position, end)

    @pyqtProperty(QRectF, notify=changed)
    def focusRect(self):
        return self._focus_rect

    def _update_focus_rect(self):
        rect = QRectF()
        if self.window is not None and self._keyboard() is None:
            focused = self.window.activeFocusItem()
            if (
                focused is not None
                and not sip.isdeleted(focused)
                and focused.isVisible()
                and focused.activeFocusOnTab()
            ):
                rect = self._rect(focused)
        if rect != self._focus_rect:
            self._focus_rect = rect
            self.changed.emit()

    def _focus(self, item):
        item.forceActiveFocus(Qt.TabFocusReason)
        parent = item.parentItem()
        while parent is not None:
            if parent.property("contentY") is not None:
                position = item.mapToItem(parent, QPointF(0, 0))
                delta = min(0, position.y())
                if position.y() + item.height() > parent.height():
                    delta = position.y() + item.height() - parent.height()
                maximum = max(0, parent.property("contentHeight") - parent.height())
                parent.setProperty(
                    "contentY",
                    max(0, min(maximum, parent.property("contentY") + delta)),
                )
            parent = parent.parentItem()
        self._update_focus_rect()
        QTimer.singleShot(0, self._update_focus_rect)

    @pyqtSlot(QObject)
    def focusFirst(self, root):
        if not self.enabled or not isinstance(root, QQuickItem):
            return
        candidates = self._candidates(root)
        if candidates:
            self._focus(
                min(
                    candidates,
                    key=lambda item: (self._rect(item).top(), self._rect(item).left()),
                )
            )

    def _move(self, action):
        if self.window is None:
            return
        candidates = self._candidates(self._scope())
        focused = self.window.activeFocusItem()
        if focused not in candidates:
            self.focusFirst(self._scope())
            return
        origin = self._rect(focused).center()
        horizontal = action in {"left", "right"}
        direction = -1 if action in {"left", "up"} else 1
        options = []
        for item in candidates:
            if item is focused:
                continue
            target = self._rect(item).center() - origin
            distance = direction * (target.x() if horizontal else target.y())
            across = abs(target.y() if horizontal else target.x())
            if distance > 1:
                options.append((distance + across * 3, item))
        if options:
            self._focus(min(options, key=lambda option: option[0])[1])

    @pyqtSlot(str)
    def handleAction(self, action):
        if not self.enabled or self.window is None:
            return
        if action not in {"up", "down", "left", "right", "select"}:
            self.requested.emit(action)
            self._update_focus_rect()
            QTimer.singleShot(0, self._update_focus_rect)
            return
        keyboard = self._keyboard()
        if keyboard is not None:
            QMetaObject.invokeMethod(
                keyboard, "handleAction", Q_ARG("QVariant", action)
            )
            self._update_focus_rect()
        elif action == "select":
            focused = self.window.activeFocusItem()
            if (
                focused is not None
                and focused.isEnabled()
                and focused.metaObject().indexOfSignal(b"clicked()") >= 0
            ):
                QMetaObject.invokeMethod(focused, "clicked")
            elif focused is not None and focused.property("cursorPosition") is not None:
                self.requested.emit("keyboard")
            self._update_focus_rect()
            QTimer.singleShot(0, self._update_focus_rect)
        else:
            self._move(action)

    @pyqtSlot(int)
    def scrollPage(self, direction):
        if self.window is None:
            return
        scroll = next(
            (
                item
                for item in items(self._scope())
                if item.isEnabled()
                and item.property("contentY") is not None
                and item.property("contentHeight") > item.height()
            ),
            None,
        )
        if scroll is not None:
            maximum = scroll.property("contentHeight") - scroll.height()
            scroll.setProperty(
                "contentY",
                max(
                    0,
                    min(
                        maximum,
                        scroll.property("contentY") + direction * scroll.height() * 0.8,
                    ),
                ),
            )
            self._update_focus_rect()
            QTimer.singleShot(0, self._update_focus_rect)
