import QtQuick 2.15
import "../../../ui/components"
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
Flickable {
    property var shell
    property var viewModel
    id: page
    readonly property bool ready: !!viewModel.reader.variantLabel
    readonly property bool choosing: (viewModel.reader.installations || []).length > 1 && !viewModel.reader.path
    readonly property bool repair: !!viewModel.reader.installed && (!viewModel.reader.complete || viewModel.reader.compatible === false)
    readonly property bool installAtTop: !!viewModel.reader.installed && !!viewModel.reader.releaseVersion && (repair || !!viewModel.reader.updateAvailable)
    contentHeight: content.height; clip: true; boundsBehavior: Flickable.StopAtBounds
    ScrollIndicator.vertical: ScrollIndicator {}
    Column {
        id: content; width: parent.width; spacing: 24
        RowLayout {
            width: parent.width; spacing: 16
            PageHeading {
                Layout.fillWidth: true; symbol: "book"
                title: !page.ready ? (viewModel.readerError ? "Status unavailable" : "Checking installation…") : page.choosing ? "Choose an installation" : viewModel.reader.installed ? (viewModel.reader.complete && viewModel.reader.compatible !== false ? "Ready to read" : "Setup needs attention") : "Not installed"
                description: !page.ready ? "" : page.choosing ? "Choose which copy of KOReader to use." : viewModel.reader.installed ? "" : "Install KOReader for this device."
            }
            KButton {
                text: page.installAtTop ? (page.repair ? "Reinstall" : "Update") : ""
                symbol: page.installAtTop ? "download" : "refresh"
                primary: page.installAtTop
                enabled: viewModel.canChange && (page.installAtTop ? !!viewModel.reader.canInstall : !!viewModel.reader.supported)
                onClicked: page.installAtTop ? viewModel.requestReader("install", "") : viewModel.checkReaderRelease()
                Accessible.name: page.installAtTop ? text + " KOReader" : "Check for KOReader updates"
            }
        }
        KText { visible: !!viewModel.readerActivity; text: viewModel.readerActivity; width: parent.width; heading: true }
        KText { visible: !!viewModel.readerError; text: viewModel.readerError; width: parent.width }
        KText { visible: !!viewModel.readerMessage; text: viewModel.readerMessage; width: parent.width; color: Theme.secondary }
        Column {
            visible: !!viewModel.reader.reason; width: parent.width; spacing: 12
            KText { text: viewModel.reader.reason || ""; width: parent.width; color: Theme.secondary }
            Repeater {
                model: page.choosing ? viewModel.reader.installations : []
                KMenuRow {
                    width: parent.width; text: modelData.path; detail: (modelData.version || "Unknown version") + (!modelData.complete ? " · Incomplete" : ""); symbol: "book"; enabled: !viewModel.readerBusy
                    onClicked: viewModel.selectReaderInstallation(modelData.path)
                }
            }
        }
        RowLayout {
            width: parent.width; spacing: 12
            visible: !!viewModel.reader.installed && !page.choosing
            KButton { text: "Open KOReader"; symbol: "book"; primary: true; Layout.fillWidth: true; enabled: !!viewModel.reader.canOpen && viewModel.canChange; onClicked: viewModel.openReader() }
        }
        KMenuRow {
            width: parent.width; text: "Customise KOReader"; symbol: "plugin"; detail: "Layouts, reading tools and plugins"
            visible: !!viewModel.reader.installed && !page.choosing
            enabled: !!viewModel.reader.installed && !!viewModel.reader.path && !viewModel.readerBusy
            onClicked: shell.navigation.navigate("koreader-customise")
        }
        Column {
            width: parent.width; visible: page.ready && !page.choosing
            InfoRow { label: "Status"; value: viewModel.reader.installed ? (!viewModel.reader.complete ? "Incomplete" : viewModel.reader.compatible === false ? "Wrong build" : viewModel.reader.updateAvailable ? "Update available" : "Installed") : "Not installed"; badge: true; badgeEmphasized: !!viewModel.reader.updateAvailable || viewModel.reader.compatible === false || (!!viewModel.reader.installed && !viewModel.reader.complete) }
            InfoRow { visible: !!viewModel.reader.installed; label: "Installed version"; value: viewModel.reader.version || "Unknown" }
            InfoRow { label: "Latest release"; value: viewModel.reader.releaseVersion || "Not checked" }
            InfoRow { visible: !!viewModel.reader.path; label: "Location"; value: viewModel.reader.path || ""; stacked: true; last: true }
        }
        Column {
            width: parent.width; spacing: 12; visible: page.ready && !page.choosing
            KButton {
                visible: !viewModel.reader.installed
                width: parent.width; symbol: "download"; primary: true
                text: "Install KOReader"
                enabled: viewModel.canChange && !!viewModel.reader.canInstall
                onClicked: viewModel.requestReader("install", "")
            }
            KText {
                visible: !viewModel.reader.installed && !viewModel.reader.releaseVersion
                text: "Check for a release using the update button above."
                width: parent.width; color: Theme.secondary; font.pixelSize: Theme.smallSize
            }
            KButton {
                visible: shell.controls.info.family === "kindle" && !!viewModel.reader.installed
                width: parent.width; symbol: viewModel.reader.scriptletInstalled ? "check" : "book"
                text: viewModel.reader.scriptletInstalled ? "Library shortcut added" : "Add to Kindle library"
                enabled: viewModel.canChange && !!viewModel.reader.canAddScriptlet && !viewModel.reader.scriptletInstalled
                onClicked: viewModel.addReaderScriptlet()
            }
            KButton {
                visible: !!viewModel.reader.installed
                width: parent.width; text: "Uninstall KOReader"; symbol: "trash"
                enabled: viewModel.canChange && !!viewModel.reader.canRemove
                onClicked: viewModel.requestReader("uninstall", "")
            }
            KText { visible: !!viewModel.reader.detail; text: viewModel.reader.detail || ""; width: parent.width; color: Theme.secondary; font.pixelSize: Theme.smallSize }
        }
    }
}
