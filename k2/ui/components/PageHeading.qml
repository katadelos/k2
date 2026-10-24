import QtQuick 2.15
import QtQuick.Layouts 1.15
RowLayout {
    property string title
    property string description
    property string symbol
    width: parent.width; spacing: 16
    KSurface {
        visible: !!symbol; Layout.preferredWidth: 52; Layout.preferredHeight: 52; Layout.alignment: Qt.AlignTop
        radius: Theme.radius; color: Theme.wash
        KIcon { name: symbol; width: 28; height: 28; anchors.centerIn: parent }
    }
    ColumnLayout {
        Layout.fillWidth: true; Layout.topMargin: 2; spacing: 4
        KText { text: title; heading: true; font.pixelSize: Theme.titleSize; Layout.fillWidth: true }
        KText { visible: !!description; text: description; color: Theme.secondary; Layout.fillWidth: true }
    }
}
