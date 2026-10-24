import QtQuick 2.15
import EBoard 1.0 as EBoard

EBoard.Keyboard {
    property var theme: Theme
    paper: theme.paper
    ink: theme.ink
    fontFamily: theme.bodyFont
    uiScale: theme.scale
    bodySize: theme.bodySize
    controlSize: theme.controlSize
    headingSize: theme.headingSize
}
