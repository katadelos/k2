import QtQuick 2.15
import "../components"
Item {
    property var shell
    id: header
    property string title
    property Component actions
    implicitHeight: 50
    KButton {
        x: -12; y: 0; width: 44; height: 44
        visible: shell.navigation.page !== "home"; symbol: "back"; flat: true
        onClicked: shell.back(); Accessible.name: "Back"
    }
    TextMetrics { id: capital; font: titleLabel.font; text: "H" }
    KText {
        id: titleLabel
        x: shell.navigation.page === "home" ? 0 : 40
        y: Math.round((44 - capital.tightBoundingRect.height) / 2 - baselineOffset - capital.tightBoundingRect.y)
        width: controls.x - x - 12
        text: header.title; heading: true; font.pixelSize: 24; lineHeight: 1
        wrapMode: Text.NoWrap; elide: Text.ElideRight
    }
    Row {
        id: controls
        anchors.right: parent.right; anchors.rightMargin: -12
        height: 44; spacing: 8
        Loader {
            sourceComponent: header.actions
            width: item ? item.implicitWidth : 0; height: 44
            visible: !!sourceComponent
        }
        KButton {
            width: 44; height: 44; symbol: "settings"; flat: true
            onClicked: shell.controls.toggleControls(); Accessible.name: "Device controls"
        }
    }
    Rectangle { anchors.bottom: parent.bottom; x: -Theme.margin; width: parent.width + Theme.margin * 2; height: 1; color: Theme.ink }
}
