import QtQuick 2.15
import QtQuick.Controls 2.15
Button {
    id: control
    property bool primary: false
    property bool alignLeft: false
    property string symbol: ""
    readonly property color foreground: primary || down ? Theme.paper : Theme.ink
    implicitHeight: Theme.touchSize
    implicitWidth: Math.max(Theme.touchSize, label.implicitWidth + (symbol ? 30 : 0) + (text ? 32 : 20))
    padding: text ? 12 : 0
    font.family: Theme.displayFont
    font.pixelSize: Theme.controlSize
    font.weight: Font.Normal
    opacity: enabled ? 1 : 0.4
    background: Item {
        Rectangle {
            visible: control.flat
            anchors.fill: parent
            color: control.down ? Theme.ink : Theme.paper
            border.color: Theme.ink; border.width: control.visualFocus ? 2 : 0
        }
        KSurface {
            visible: !control.flat
            anchors.fill: parent
            color: control.down ? (control.primary ? Theme.primaryPressed : Theme.ink) : control.primary ? Theme.ink : Theme.paper
            borderColor: control.visualFocus ? Theme.ink : Theme.line
            borderWidth: control.visualFocus ? 2 : 1
            radius: Theme.radius
        }
    }
    TextMetrics { id: labelMetrics; font: control.font; text: "H" }
    contentItem: Item {
        id: content
        readonly property real labelOffset: control.symbol ? 22 + (control.text ? 8 : 0) : 0
        readonly property real groupWidth: Math.min(width, label.implicitWidth + labelOffset)
        readonly property real groupX: control.alignLeft ? 0 : Math.round((width - groupWidth) / 2)
        implicitWidth: label.implicitWidth + labelOffset
        implicitHeight: 24
        KIcon {
            visible: !!control.symbol; name: control.symbol
            x: content.groupX; width: 22; height: 22
            ink: control.foreground; anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            id: label
            visible: !!control.text
            x: content.groupX + content.labelOffset
            width: Math.max(0, content.groupWidth - content.labelOffset)
            text: control.text; textFormat: Text.PlainText; font: control.font
            color: control.foreground; elide: Text.ElideRight
            y: Math.round((parent.height - labelMetrics.tightBoundingRect.height) / 2 - baselineOffset - labelMetrics.tightBoundingRect.y)
        }
    }
}
