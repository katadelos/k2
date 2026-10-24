import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

RowLayout {
    id: bar
    property var model: []
    property string currentId: ""
    property string objectNamePrefix: "tab-"
    signal activated(string identifier)
    spacing: 0
    Repeater {
        model: bar.model
        Button {
            id: tabButton
            readonly property bool selected: bar.currentId === modelData.id
            objectName: bar.objectNamePrefix + modelData.id
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            implicitHeight: 48
            padding: 0
            opacity: enabled ? 1 : 0.4
            onClicked: bar.activated(modelData.id)
            Accessible.role: Accessible.PageTab
            Accessible.name: modelData.accessibleName || modelData.title
            Accessible.checkable: true
            Accessible.checked: selected
            contentItem: KText {
                text: modelData.title
                font.pixelSize: Theme.controlSize
                heading: true
                color: tabButton.down ? Theme.paper : tabButton.selected ? Theme.ink : Theme.secondary
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle {
                color: tabButton.down ? Theme.ink : Theme.paper
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: tabButton.selected ? 3 : 1
                    color: tabButton.selected ? Theme.ink : Theme.line
                }
            }
        }
    }
}
