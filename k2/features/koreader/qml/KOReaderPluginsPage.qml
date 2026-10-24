import QtQuick 2.15
import "../../../ui/components"
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
ColumnLayout {
    property var shell
    property var viewModel
    id: page
    property bool adding: false
    property bool keyboardOpen: false
    property string tab: "Added"
    readonly property var plugins: viewModel.readerPlugins.filter(function(plugin) { return tab === "Included" ? plugin.builtin : !plugin.builtin })
    function dismissKeyboard() {
        if (!keyboardOpen) return false
        sourceField.focus = false; keyboardOpen = false
        return true
    }
    function dismissKeyboardAt(x, y) {
        if (!keyboardOpen) return
        var kp = keyboard.mapFromItem(page, x, y)
        var fp = sourceBox.mapFromItem(page, x, y)
        if (!(kp.x >= 0 && kp.x < keyboard.width && kp.y >= 0 && kp.y < keyboard.height)
                && !(fp.x >= 0 && fp.x < sourceBox.width && fp.y >= 0 && fp.y < sourceBox.height)) dismissKeyboard()
    }
    spacing: 16
    KButton {
        visible: !page.adding; Layout.fillWidth: true; text: "Add plugin"; symbol: "download"
        enabled: viewModel.canChange
        onClicked: { viewModel.clearReaderFeedback(); page.adding = true; sourceField.forceActiveFocus() }
    }
    ColumnLayout {
        visible: page.adding; Layout.fillWidth: true; spacing: 12
        RowLayout {
            Layout.fillWidth: true
            KText { text: "Plugin archive"; heading: true; Layout.fillWidth: true }
            KButton { symbol: "close"; flat: true; onClicked: { page.dismissKeyboard(); page.adding = false } Accessible.name: "Close plugin installer" }
        }
        KSurface {
            id: sourceBox; Layout.fillWidth: true; implicitHeight: 48
            borderColor: sourceField.activeFocus ? Theme.ink : Theme.line; radius: Theme.radius
            TextField {
                id: sourceField; anchors.fill: parent; padding: 12
                placeholderText: "https://… or a file path"; background: Item {}
                font.family: Theme.bodyFont; font.pixelSize: Theme.bodySize; color: Theme.ink
                selectByMouse: true; inputMethodHints: Qt.ImhUrlCharactersOnly | Qt.ImhNoAutoUppercase | Qt.ImhNoPredictiveText
                onActiveFocusChanged: if (activeFocus) page.keyboardOpen = true
                onAccepted: page.dismissKeyboard()
                Accessible.name: "Plugin archive URL or local path"
            }
        }
        KText { text: "Use a ZIP or tar archive containing a .koplugin folder."; color: Theme.secondary; font.pixelSize: Theme.smallSize; Layout.fillWidth: true }
        KButton {
            Layout.fillWidth: true; text: "Install plugin"; primary: true; enabled: !!sourceField.text.trim() && viewModel.canChange
            onClicked: { page.dismissKeyboard(); viewModel.requestReader("plugin-install", sourceField.text) }
        }
    }
    KText { visible: !!viewModel.readerActivity; text: viewModel.readerActivity; heading: true; Layout.fillWidth: true }
    KText { visible: !!viewModel.readerError; text: viewModel.readerError; Layout.fillWidth: true }
    KText { visible: !!viewModel.readerMessage; text: viewModel.readerMessage; color: Theme.secondary; Layout.fillWidth: true }
    RowLayout {
        Layout.fillWidth: true; spacing: 0
        Repeater {
            model: ["Added", "Included"]
            Button {
                id: tabButton; Layout.fillWidth: true; Layout.preferredWidth: 1; implicitHeight: 48; padding: 0
                onClicked: { page.dismissKeyboard(); page.tab = modelData }
                contentItem: KText { text: modelData; font.pixelSize: Theme.controlSize; heading: true; color: tabButton.down ? Theme.paper : page.tab === modelData ? Theme.ink : Theme.secondary; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                background: Rectangle {
                    color: tabButton.down ? Theme.ink : Theme.paper
                    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: page.tab === modelData ? 3 : 1; color: page.tab === modelData ? Theme.ink : Theme.line }
                }
            }
        }
    }
    Flickable {
        Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 0
        contentHeight: content.height; clip: true; boundsBehavior: Flickable.StopAtBounds
        ScrollIndicator.vertical: ScrollIndicator {}
        Column {
            id: content; width: parent.width; spacing: 0
            Repeater {
                model: page.plugins
                Item {
                    width: content.width; height: Math.max(92, details.height + 32)
                    Column {
                        id: details; y: 16; width: parent.width - (removePlugin.visible ? 60 : 0); spacing: 6
                        RowLayout {
                            width: parent.width
                            KText { text: modelData.name; heading: true; font.pixelSize: Theme.sectionSize; Layout.fillWidth: true; maximumLineCount: 1; elide: Text.ElideRight }
                            KBadge { visible: !!modelData.version; text: modelData.version || "" }
                        }
                        KText { visible: !!modelData.description; text: modelData.description; width: parent.width; color: Theme.secondary; font.pixelSize: Theme.smallSize; maximumLineCount: 2; elide: Text.ElideRight }
                        KText { visible: !modelData.removable && !modelData.builtin; text: modelData.protectionReason || "Existing plugin · managed outside k2"; width: parent.width; color: Theme.secondary; font.pixelSize: Theme.smallSize }
                    }
                    KButton {
                        id: removePlugin; visible: !!modelData.removable; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                        symbol: "trash"; flat: true; enabled: viewModel.canChange
                        onClicked: viewModel.requestReader("plugin-remove", modelData.id)
                        Accessible.name: "Remove " + modelData.name
                    }
                    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.faint }
                }
            }
            Column {
                visible: page.plugins.length === 0 && !viewModel.readerBusy
                width: parent.width; spacing: 12
                Item { width: 1; height: 12 }
                KText { text: page.tab === "Added" ? "No added plugins" : "No included plugins found"; heading: true; width: parent.width }
                KText { text: page.tab === "Added" ? "Add a plugin archive to extend KOReader. Plugins bundled with the reader are listed under Included." : "This installation does not contain any recognised bundled plugins."; width: parent.width; color: Theme.secondary }
            }
            KText { visible: page.tab === "Included" && page.plugins.length > 0; topPadding: 20; text: "Included plugins are managed by KOReader. Enable or disable them in KOReader’s plugin settings."; width: parent.width; color: Theme.secondary; font.pixelSize: Theme.smallSize }
        }
    }
    OnScreenKeyboard {
        id: keyboard; visible: page.keyboardOpen
        Layout.fillWidth: true; Layout.preferredHeight: 258
        Layout.leftMargin: -24; Layout.rightMargin: -24; Layout.bottomMargin: -24; submitLabel: "Done"
        target: sourceField
        onSubmitRequested: page.dismissKeyboard()
    }
}
