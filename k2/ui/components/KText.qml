import QtQuick 2.15
Text {
    property bool heading: false
    textFormat: Text.PlainText
    color: Theme.ink
    font.family: heading ? Theme.displayFont : Theme.bodyFont
    font.pixelSize: Theme.bodySize
    font.weight: Font.Normal
    lineHeight: heading ? 1 : 1.15
    wrapMode: Text.Wrap
}
