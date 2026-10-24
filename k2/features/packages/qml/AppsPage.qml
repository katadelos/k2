import QtQuick 2.15
import "../../../ui/components"
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
ColumnLayout {
    property var shell
    property var viewModel
    id: apps
    property bool keyboardOpen: false
    Timer {
        id: searchDebounce
        interval: 180
        onTriggered: viewModel.search(searchField.text)
    }
    readonly property bool showingFeatured: viewModel.tab === "Featured"
    property int pageSize: Math.max(1, Math.floor(rows.height / 80))
    readonly property int pageCount: viewModel.pageCount
    Timer {
        id: pageSizeUpdate
        interval: 0
        // Layout changes can arrive while the Loader is creating or removing
        // delegates. Update the shared model after that work has finished.
        onTriggered: viewModel.setPageSize(apps.pageSize)
    }
    function dismissKeyboard() {
        if (!keyboardOpen) return false
        searchDebounce.stop(); viewModel.search(searchField.text)
        searchField.focus = false; keyboardOpen = false
        return true
    }
    function dismissKeyboardAt(x, y) {
        if (!keyboardOpen) return
        var keyPoint = keyboard.mapFromItem(apps, x, y)
        var fieldPoint = searchBox.mapFromItem(apps, x, y)
        var inKeyboard = keyPoint.x >= 0 && keyPoint.x < keyboard.width && keyPoint.y >= 0 && keyPoint.y < keyboard.height
        var inField = fieldPoint.x >= 0 && fieldPoint.x < searchBox.width && fieldPoint.y >= 0 && fieldPoint.y < searchBox.height
        if (!inKeyboard && !inField) dismissKeyboard()
    }
    spacing: keyboardOpen ? 8 : 12
    Component.onCompleted: pageSizeUpdate.restart()
    onPageSizeChanged: pageSizeUpdate.restart()
    RowLayout {
        Layout.fillWidth: true; spacing: 12
        KSurface {
            id: searchBox
            Layout.fillWidth: true; implicitHeight: 48
            borderColor: searchField.activeFocus ? Theme.ink : Theme.line; radius: Theme.radius; color: Theme.paper
            KIcon { name: "search"; width: 20; height: 20; anchors.left: parent.left; anchors.leftMargin: 14; anchors.verticalCenter: parent.verticalCenter; ink: Theme.secondary }
            TextField {
                id: searchField
                anchors.fill: parent; leftPadding: 44; rightPadding: clearSearch.visible ? 52 : 12
                placeholderText: "Find a package"; text: viewModel.query
                font.family: Theme.bodyFont; font.pixelSize: Theme.bodySize
                color: Theme.ink; selectByMouse: true; background: Item {}
                onTextEdited: searchDebounce.restart()
                onActiveFocusChanged: if (activeFocus) apps.keyboardOpen = true
                onAccepted: apps.dismissKeyboard()
                Keys.onEscapePressed: apps.dismissKeyboard()
                Accessible.name: "Search packages"
            }
            KButton {
                id: clearSearch; visible: !!searchField.text
                anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                anchors.rightMargin: 2
                symbol: "close"; flat: true; implicitWidth: 44
                background: KSurface {
                    anchors.fill: parent; anchors.margins: 4; radius: 3
                    color: clearSearch.down ? Theme.ink : "transparent"
                }
                onClicked: { viewModel.search(""); searchField.forceActiveFocus() }
                Accessible.name: "Clear search"
            }
        }
        KButton { symbol: "refresh"; implicitHeight: 48; implicitWidth: 48; enabled: viewModel.canChange; onClicked: { apps.dismissKeyboard(); viewModel.refresh() } Accessible.name: "Refresh App Store" }
    }
    KTabBar {
        Layout.fillWidth: true
        model: ["Featured", "All", "Installed", "Updates"].map(function(title) {
            return {id: title, title: title, accessibleName: title === "Featured" ? "Featured apps" : title + " packages"}
        })
        currentId: viewModel.tab
        onActivated: { apps.dismissKeyboard(); viewModel.setTab(identifier) }
    }
    RowLayout {
        visible: !apps.keyboardOpen && !apps.showingFeatured; Layout.fillWidth: true; spacing: 12
        KText { visible: viewModel.packageCount > 0; text: viewModel.packageCount + (viewModel.packageCount === 1 ? " package" : " packages"); font.pixelSize: Theme.smallSize; color: Theme.secondary }
        KText { text: viewModel.freshnessText; Layout.fillWidth: true; font.pixelSize: 13; color: viewModel.freshness.error ? Theme.ink : Theme.secondary; horizontalAlignment: Text.AlignRight; maximumLineCount: 1; elide: Text.ElideRight }
        KButton {
            visible: viewModel.tab === "Updates" && viewModel.updateCount > 0
            text: "Update all"
            enabled: viewModel.canChange && !viewModel.catalogWarning
            onClicked: { apps.dismissKeyboard(); viewModel.request("upgrade", "") }
        }
    }
    FeaturedPage {
        visible: apps.showingFeatured
        Layout.fillHeight: true; Layout.fillWidth: true; Layout.minimumHeight: 0
        viewModel: apps.viewModel
    }
    Item {
        id: rows; objectName: "packageRows"
        visible: !apps.showingFeatured
        Layout.fillHeight: true; Layout.fillWidth: true; Layout.minimumHeight: 0; clip: true
        Repeater {
            model: viewModel.rows
            ItemDelegate {
                id: packageRow
                property var modelData: record
                width: rows.width; height: 80; y: index * 80; padding: 0
                onClicked: viewModel.selectPackage(modelData.name)
                Accessible.name: modelData.name + (modelData.update ? ", update available" : modelData.installed ? ", installed" : "")
                background: Rectangle { color: packageRow.down ? Theme.wash : Theme.paper }
                contentItem: Item {
                    KSurface {
                        id: packageIcon; width: 40; height: 40; radius: Theme.radius; color: Theme.wash; anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                        KIcon { name: "apps"; width: 24; height: 24; anchors.centerIn: parent }
                    }
                    Column {
                        anchors.left: packageIcon.right; anchors.leftMargin: 16; anchors.right: badge.left; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                        KText { text: modelData.name; font.pixelSize: Theme.sectionSize; heading: true; width: parent.width; wrapMode: Text.NoWrap; elide: Text.ElideRight }
                        KText { text: modelData.summary; font.pixelSize: Theme.smallSize; color: Theme.secondary; width: parent.width; maximumLineCount: 2; elide: Text.ElideRight }
                    }
                    Row {
                        id: badge; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 12
                        KBadge { visible: !!modelData.installed; text: !modelData.configured ? "Setup needed" : modelData.update ? "Update" : "Installed"; emphasized: !!modelData.update || !modelData.configured; anchors.verticalCenter: parent.verticalCenter }
                        KIcon { name: "arrow"; width: 16; height: 20 }
                    }
                    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.faint }
                }
            }
        }
        Column {
            visible: viewModel.packageCount === 0
            anchors.horizontalCenter: parent.horizontalCenter; y: Math.max(0, (parent.height - height) / 2); width: parent.width - 48; spacing: apps.keyboardOpen ? 8 : 16
            KIcon { name: !viewModel.query && viewModel.tab === "Updates" ? "check" : "search"; width: apps.keyboardOpen ? 24 : 32; height: width; anchors.horizontalCenter: parent.horizontalCenter }
            KText { text: viewModel.busy ? viewModel.activityTitle : viewModel.query ? "No matching packages" : viewModel.tab === "Updates" ? "No updates available" : viewModel.tab === "Installed" ? "No installed packages" : "No packages found"; font.pixelSize: apps.keyboardOpen ? 20 : 24; heading: true; width: parent.width; horizontalAlignment: Text.AlignHCenter }
            KText { visible: !viewModel.busy; text: viewModel.query ? "Try another name or clear your search." : viewModel.tab === "Updates" ? "Check for updates to see if anything new is available." : viewModel.tab === "Installed" ? "Browse All to find apps and tools." : "Check for updates to load the package list."; font.pixelSize: apps.keyboardOpen ? Theme.smallSize : Theme.bodySize; color: Theme.secondary; width: parent.width; horizontalAlignment: Text.AlignHCenter }
            KButton {
                anchors.horizontalCenter: parent.horizontalCenter; enabled: viewModel.canChange
                text: viewModel.query ? "Clear search" : viewModel.tab === "Installed" ? "Browse all" : "Check for updates"
                onClicked: { apps.dismissKeyboard(); if (viewModel.query) viewModel.search(""); else if (viewModel.tab === "Installed") viewModel.setTab("All"); else viewModel.request("update", "") }
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true; visible: !apps.showingFeatured && apps.pageCount > 1
        KButton { symbol: "back"; flat: true; enabled: viewModel.appPage > 0; onClicked: viewModel.setAppPage(viewModel.appPage - 1); Accessible.name: "Previous page" }
        KText { text: "Page " + (viewModel.appPage + 1) + " of " + apps.pageCount; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; font.pixelSize: Theme.smallSize; color: Theme.secondary }
        KButton { symbol: "arrow"; flat: true; enabled: viewModel.appPage + 1 < apps.pageCount; onClicked: viewModel.setAppPage(viewModel.appPage + 1); Accessible.name: "Next page" }
    }
    OnScreenKeyboard {
        id: keyboard; visible: apps.keyboardOpen
        Layout.fillWidth: true; Layout.preferredHeight: 258
        Layout.leftMargin: -24; Layout.rightMargin: -24; Layout.bottomMargin: -24
        submitLabel: "Done"
        target: searchField
        onEdited: searchDebounce.restart()
        onSubmitRequested: apps.dismissKeyboard()
    }
}
