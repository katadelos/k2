import QtQuick 2.15
import "../components"
Item {
    property string statusText: "Starting k2…"
    property real progress: 0
    Image {
        anchors.left: parent.left; anchors.right: parent.right
        anchors.bottom: loading.top; anchors.bottomMargin: 30
        height: width * sourceSize.height / Math.max(1, sourceSize.width)
        source: "../assets/mountain.png"
        fillMode: Image.PreserveAspectFit
        horizontalAlignment: Image.AlignRight
        verticalAlignment: Image.AlignBottom
        smooth: true
    }
    Column {
        x: 44; y: 38; spacing: 4
        KText { text: "k2"; font.family: Theme.displayFont; font.pixelSize: 80; heading: true; font.weight: Font.Bold; font.letterSpacing: -2 }
        KText { text: "More from\nyour device."; font.pixelSize: 24; lineHeight: 1.1 }
    }
    Column {
        id: loading
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        anchors.leftMargin: 44; anchors.rightMargin: 44; anchors.bottomMargin: 44
        spacing: 16
        KText { text: statusText; font.pixelSize: 16; color: Theme.secondary }
        Rectangle {
            width: parent.width; height: 5; color: Theme.faint
            Rectangle { width: parent.width * Math.max(0, Math.min(1, progress)); height: parent.height; color: Theme.ink }
        }
    }
}
