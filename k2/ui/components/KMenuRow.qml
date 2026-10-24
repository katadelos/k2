import QtQuick 2.15
KButton {
    id: row
    property string detail: ""
    property string badge: ""
    implicitHeight: detail ? 80 : 60
    flat: true; padding: 0
    contentItem: Item {
        KIcon { name: row.symbol; width: 24; height: 24; anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; ink: row.foreground }
        Column {
            anchors.left: parent.left; anchors.leftMargin: 44; anchors.right: trailing.left; anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter; spacing: 6
            KText { text: row.text; heading: true; width: parent.width; color: row.foreground }
            KText { visible: !!row.detail; text: row.detail; font.pixelSize: Theme.smallSize; color: row.down ? Theme.paper : Theme.secondary; width: parent.width }
        }
        Row {
            id: trailing; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 12
            KBadge { visible: !!row.badge; text: row.badge; anchors.verticalCenter: parent.verticalCenter }
            KIcon { name: "arrow"; width: 18; height: 18; anchors.verticalCenter: parent.verticalCenter; ink: row.foreground }
        }
    }
    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.faint }
}
