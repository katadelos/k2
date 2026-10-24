import QtQuick 2.15
KSurface {
    property string text
    property bool emphasized: false
    implicitWidth: label.implicitWidth + 16; implicitHeight: 26
    width: implicitWidth; height: implicitHeight
    radius: 4; color: emphasized ? Theme.ink : Theme.wash
    borderColor: emphasized ? Theme.ink : Theme.line
    KText {
        id: label; anchors.centerIn: parent
        text: parent.text; font.pixelSize: 13 + Theme.textSizeAdjustment; lineHeight: 1
        color: parent.emphasized ? Theme.paper : Theme.secondary
    }
}
