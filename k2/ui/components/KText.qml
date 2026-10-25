import QtQuick 2.15
Text {
    id: label
    property bool heading: false
    FontMetrics { id: metrics; font: label.font }
    readonly property int naturalLineHeight: Math.ceil(metrics.height)
    textFormat: Text.PlainText
    color: Theme.ink
    font.family: heading ? Theme.displayFont : Theme.bodyFont
    font.pixelSize: Theme.bodySize
    font.weight: Font.Normal
    // Keep stacked labels and the controls below them on the native pixel grid.
    lineHeight: heading ? 1 : panelWidth === 600 && naturalLineHeight > 0
        ? Math.ceil(naturalLineHeight * 1.15) / naturalLineHeight : 1.15
    wrapMode: Text.Wrap
}
