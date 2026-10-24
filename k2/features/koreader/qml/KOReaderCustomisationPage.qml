import QtQuick 2.15
import "../../../ui/components"
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
Flickable {
    property var shell
    property var viewModel
    id: page
    property bool previewExpanded: false
    readonly property var item: viewModel.readerCustomisation || ({})
    readonly property bool idle: viewModel.canChange
    readonly property string setup: Array.isArray(item.instructions) ? item.instructions.join("\n\n") : item.instructions || ""
    contentHeight: content.height; clip: true; boundsBehavior: Flickable.StopAtBounds
    ScrollIndicator.vertical: ScrollIndicator {}
    Column {
        id: content; width: parent.width; spacing: 24
        RowLayout {
            width: parent.width; spacing: 16
            PageHeading { Layout.fillWidth: true; title: page.item.name || "Customisation"; description: page.item.summary || ""; symbol: "plugin" }
            KButton { symbol: "refresh"; enabled: page.idle; onClicked: viewModel.refreshReaderCustomisations(true); Accessible.name: "Check for updates" }
        }
        KText { visible: !!page.item.description; text: page.item.description || ""; width: parent.width }
        KButton {
            visible: viewModel.readerPreviewAvailable
            width: parent.width; text: page.previewExpanded ? "Hide preview" : "View preview"; enabled: page.idle
            onClicked: {
                page.previewExpanded = !page.previewExpanded
                if (page.previewExpanded && !viewModel.readerPreview) viewModel.loadReaderPreview()
            }
        }
        Column {
            visible: page.previewExpanded && !!viewModel.readerPreview; width: parent.width; spacing: 8
            Image {
                source: page.previewExpanded ? viewModel.readerPreview : ""; width: parent.width; height: 340
                fillMode: Image.PreserveAspectFit; asynchronous: true; smooth: true
                sourceSize: Qt.size(1000, 1000)
            }
            KText { text: "Preview from the developer. Appearance depends on your settings."; width: parent.width; font.pixelSize: Theme.smallSize; color: Theme.secondary }
        }
        KText { visible: !!viewModel.readerPreviewError; text: viewModel.readerPreviewError; width: parent.width }
        KText { visible: !!viewModel.readerActivity; text: viewModel.readerActivity; heading: true; width: parent.width }
        KText { visible: !!viewModel.readerCustomiseError; text: viewModel.readerCustomiseError; width: parent.width }
        KText { visible: !!viewModel.readerError && viewModel.readerError !== viewModel.readerCustomiseError; text: viewModel.readerError; width: parent.width }
        KText { visible: !!viewModel.readerMessage; text: viewModel.readerMessage; width: parent.width; color: Theme.secondary }
        Column {
            width: parent.width
            InfoRow { label: "Status"; value: page.item.installed ? page.item.update ? "Update available" : page.item.enabled === false ? "Disabled" : "Installed" : "Not installed"; badge: true; badgeEmphasized: !!page.item.update }
            InfoRow { visible: !!page.item.installed; label: "Installed version"; value: page.item.version || "Unknown" }
            InfoRow { label: "Available version"; value: page.item.availableVersion || "Not checked"; last: true }
        }
        RowLayout {
            width: parent.width; spacing: 12
            KButton {
                visible: !page.item.installed || !!page.item.update
                text: !page.item.availableVersion ? "Check for updates" : page.item.update ? "Update" : "Install"
                symbol: page.item.availableVersion ? "download" : "refresh"; primary: true
                enabled: page.idle && (!page.item.availableVersion || !!page.item.canInstall)
                Layout.fillWidth: true
                onClicked: page.item.availableVersion ? viewModel.requestReaderCustomisation("install") : viewModel.refreshReaderCustomisations(true)
            }
            KButton {
                visible: !!page.item.installed && (!!page.item.canEnable || !!page.item.canDisable)
                text: page.item.canEnable ? "Enable" : "Disable"; primary: !page.item.update && !!page.item.canEnable
                enabled: page.idle; Layout.fillWidth: true
                onClicked: viewModel.requestReaderCustomisation(page.item.canEnable ? "enable" : "disable")
            }
            KButton {
                visible: !!page.item.installed && !!page.item.canRemove
                text: "Remove"; symbol: "trash"; enabled: page.idle; Layout.preferredWidth: 156
                onClicked: viewModel.requestReaderCustomisation("remove")
            }
        }
        KText { visible: !!page.item.reason; text: page.item.reason || ""; width: parent.width }
        Column {
            visible: !!page.setup; width: parent.width; spacing: 8
            KText { text: "Setup"; heading: true; font.pixelSize: Theme.sectionSize; width: parent.width }
            KText { text: page.setup; width: parent.width; color: Theme.secondary }
        }
    }
}
