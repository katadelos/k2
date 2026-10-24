import QtQuick 2.15
import "../../../ui/components"
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
Flickable {
    property var shell
    property var viewModel
    contentHeight: content.height; clip: true; boundsBehavior: Flickable.StopAtBounds
    ScrollIndicator.vertical: ScrollIndicator {}
    Column {
        id: content; width: parent.width; spacing: 24
        PageHeading { title: viewModel.selected.name || ""; description: viewModel.selected.summary || ""; symbol: "apps" }
        Column {
            width: parent.width
            InfoRow { label: "Status"; value: viewModel.selected.installed && !viewModel.selected.configured ? "Setup incomplete" : viewModel.selected.update ? "Update available" : viewModel.selected.installed ? "Installed" : "Not installed"; badge: true; badgeEmphasized: !!viewModel.selected.update || (!!viewModel.selected.installed && !viewModel.selected.configured) }
            InfoRow { label: "Available version"; value: viewModel.selected.available ? viewModel.selected.version : "Not in current feeds"; last: !viewModel.selected.installed }
            InfoRow { visible: !!viewModel.selected.installed; label: "Installed version"; value: viewModel.selected.installed || ""; last: true }
        }
        KSurface {
            visible: !!viewModel.selected.installed; width: parent.width; height: usingPackage.height + 32
            color: Theme.wash; radius: Theme.radius
            Column {
                id: usingPackage; x: 16; y: 16; width: parent.width - 32; spacing: 12
                KText { text: "Using this package"; heading: true; font.pixelSize: Theme.sectionSize; width: parent.width }
                KText { visible: !!viewModel.application.instructions; text: viewModel.application.instructions || ""; font.pixelSize: Theme.smallSize; width: parent.width }
                KText { visible: !!viewModel.application.error; text: viewModel.application.error || ""; font.pixelSize: Theme.smallSize; width: parent.width }
                Repeater {
                    model: viewModel.packageFeatures
                    KButton { width: parent.width; text: modelData.title; symbol: "terminal"; onClicked: viewModel.selectFeature(modelData.id) }
                }
                KButton { visible: !!viewModel.application.canOpen; text: "Open " + (viewModel.application.name || ""); primary: true; enabled: viewModel.canLaunch; width: parent.width; onClicked: viewModel.openApplication() }
            }
        }
        KSurface {
            visible: !!viewModel.selected.protected; width: parent.width; height: note.height + 32
            radius: Theme.radius; color: Theme.wash
            KText { id: note; x: 16; y: 16; width: parent.width - 32; text: "Required by k2. This package can be updated, but cannot be removed here."; font.pixelSize: Theme.smallSize; color: Theme.secondary }
        }
        RowLayout {
            width: parent.width; spacing: 12
            KButton { text: viewModel.selected.installed && !viewModel.selected.configured ? "Finish setup" : viewModel.selected.update ? "Update" : "Install"; symbol: "download"; primary: true; visible: !viewModel.selected.installed || !viewModel.selected.configured || !!viewModel.selected.update; enabled: viewModel.canChange && !viewModel.catalogWarning && !!viewModel.selected.available; Layout.fillWidth: true; onClicked: viewModel.request(viewModel.selected.update ? "upgrade" : "install", viewModel.selected.name) }
            KButton { text: "Remove"; symbol: "trash"; visible: !!viewModel.selected.installed && !viewModel.selected.protected; enabled: viewModel.canChange && !viewModel.catalogWarning; Layout.preferredWidth: 156; onClicked: viewModel.request("remove", viewModel.selected.name) }
        }
    }
}
