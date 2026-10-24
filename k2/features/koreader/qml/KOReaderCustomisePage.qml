import QtQuick 2.15
import "../../../ui/components"
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
ColumnLayout {
    property var shell
    property var viewModel
    id: page
    readonly property string tab: viewModel.readerCustomiseTab
    readonly property int currentPage: viewModel.readerCustomisePage
    readonly property var items: (viewModel.readerCustomisations || []).filter(function(item) {
        return page.tab === "Installed" ? item.installed : page.tab === "Updates" ? item.update : true
    })
    readonly property int pageSize: Math.max(1, Math.floor(rows.height / 88))
    readonly property int pageCount: Math.max(1, Math.ceil(items.length / pageSize))
    readonly property bool idle: viewModel.canRead && !viewModel.readerBusy
    spacing: 12
    onPageCountChanged: if (currentPage >= pageCount) viewModel.setReaderCustomisePage(pageCount - 1)

    RowLayout {
        Layout.fillWidth: true; spacing: 12
        KText { text: "Choose how KOReader looks and works."; Layout.fillWidth: true; color: Theme.secondary }
        KButton {
            symbol: "refresh"; enabled: page.idle
            onClicked: viewModel.refreshReaderCustomisations(true)
            Accessible.name: "Check for updates"
        }
    }
    RowLayout {
        Layout.fillWidth: true; spacing: 0
        Repeater {
            model: ["All", "Installed", "Updates"]
            Button {
                id: tabButton
                Layout.fillWidth: true; Layout.preferredWidth: 1; implicitHeight: 48; padding: 0
                onClicked: viewModel.setReaderCustomiseTab(modelData)
                Accessible.name: modelData + " customisations"
                contentItem: KText {
                    text: modelData; font.pixelSize: Theme.controlSize; heading: true
                    color: tabButton.down ? Theme.paper : page.tab === modelData ? Theme.ink : Theme.secondary
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    color: tabButton.down ? Theme.ink : Theme.paper
                    Rectangle {
                        anchors.bottom: parent.bottom; width: parent.width
                        height: page.tab === modelData ? 3 : 1
                        color: page.tab === modelData ? Theme.ink : Theme.line
                    }
                }
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true; spacing: 12
        KText { text: page.items.length + (page.items.length === 1 ? " customisation" : " customisations"); font.pixelSize: Theme.smallSize; color: Theme.secondary }
        KText {
            text: viewModel.readerCustomiseCheckedAt || "Updates not checked"
            Layout.fillWidth: true; font.pixelSize: Theme.smallSize; color: Theme.secondary
            horizontalAlignment: Text.AlignRight; maximumLineCount: 1; elide: Text.ElideRight
        }
    }
    KText { visible: !!viewModel.readerActivity; text: viewModel.readerActivity; heading: true; Layout.fillWidth: true }
    KText { visible: !!viewModel.readerCustomiseError; text: viewModel.readerCustomiseError; Layout.fillWidth: true }
    KText { visible: !!viewModel.readerError && viewModel.readerError !== viewModel.readerCustomiseError; text: viewModel.readerError; Layout.fillWidth: true }
    KText { visible: !!viewModel.readerMessage; text: viewModel.readerMessage; Layout.fillWidth: true; color: Theme.secondary }

    Item {
        id: rows
        Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 0; clip: true
        Repeater {
            model: page.items.slice(page.currentPage * page.pageSize, (page.currentPage + 1) * page.pageSize)
            ItemDelegate {
                id: customisationRow
                width: rows.width; height: 88; y: index * 88; padding: 0
                onClicked: viewModel.selectReaderCustomisation(modelData.id)
                Accessible.name: modelData.name + (modelData.update ? ", update available" : modelData.installed ? modelData.enabled === false ? ", disabled" : ", installed" : "")
                background: Rectangle { color: customisationRow.down ? Theme.wash : Theme.paper }
                contentItem: Item {
                    KSurface {
                        id: itemIcon
                        width: 40; height: 40; radius: Theme.radius; color: Theme.wash
                        anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                        KIcon { name: "plugin"; width: 24; height: 24; anchors.centerIn: parent }
                    }
                    Column {
                        anchors.left: itemIcon.right; anchors.leftMargin: 16
                        anchors.right: trailing.left; anchors.rightMargin: 16
                        anchors.verticalCenter: parent.verticalCenter; spacing: 6
                        KText { text: modelData.name; heading: true; font.pixelSize: Theme.sectionSize; width: parent.width; wrapMode: Text.NoWrap; elide: Text.ElideRight }
                        KText { text: modelData.summary; font.pixelSize: Theme.smallSize; color: Theme.secondary; width: parent.width; maximumLineCount: 2; elide: Text.ElideRight }
                    }
                    Row {
                        id: trailing
                        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 12
                        KBadge {
                            visible: !!modelData.installed
                            text: modelData.update ? "Update" : modelData.enabled === false ? "Disabled" : "Installed"
                            emphasized: !!modelData.update; anchors.verticalCenter: parent.verticalCenter
                        }
                        KIcon { name: "arrow"; width: 16; height: 20 }
                    }
                    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.faint }
                }
            }
        }
        Column {
            visible: page.items.length === 0
            width: parent.width - 48; anchors.horizontalCenter: parent.horizontalCenter
            y: Math.max(0, (parent.height - height) / 2); spacing: 16
            KIcon { name: page.tab === "Updates" && !viewModel.readerCustomiseError ? "check" : "plugin"; width: 32; height: 32; anchors.horizontalCenter: parent.horizontalCenter }
            KText {
                text: viewModel.readerBusy ? "Loading customisations…" : page.tab === "Installed" ? "Nothing installed yet" : page.tab === "Updates" ? viewModel.readerCustomiseError ? "Couldn’t check for updates" : "No updates available" : "Customisations unavailable"
                heading: true; font.pixelSize: 24; width: parent.width; horizontalAlignment: Text.AlignHCenter
            }
            KText {
                text: page.tab === "Installed" ? "Browse All to find layouts and reading tools." : page.tab === "Updates" ? viewModel.readerCustomiseError ? "Check your connection and try again." : "Check for updates to see if anything new is available." : "Check for updates to load the list."
                width: parent.width; horizontalAlignment: Text.AlignHCenter; color: Theme.secondary
            }
            KButton {
                anchors.horizontalCenter: parent.horizontalCenter; enabled: page.idle
                text: page.tab === "Installed" ? "Browse all" : "Check for updates"
                onClicked: page.tab === "Installed" ? viewModel.setReaderCustomiseTab("All") : viewModel.refreshReaderCustomisations(true)
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true; visible: page.pageCount > 1
        KButton { symbol: "back"; flat: true; enabled: page.currentPage > 0; onClicked: viewModel.setReaderCustomisePage(page.currentPage - 1); Accessible.name: "Previous page" }
        KText { text: "Page " + (page.currentPage + 1) + " of " + page.pageCount; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; font.pixelSize: Theme.smallSize; color: Theme.secondary }
        KButton { symbol: "arrow"; flat: true; enabled: page.currentPage + 1 < page.pageCount; onClicked: viewModel.setReaderCustomisePage(page.currentPage + 1); Accessible.name: "Next page" }
    }
    KMenuRow {
        Layout.fillWidth: true; text: "Manage other plugins"; symbol: "plugin"
        detail: "Install from an archive or manage existing plugins"
        enabled: !viewModel.readerBusy
        onClicked: shell.navigation.navigate("koreader-plugins")
    }
}
