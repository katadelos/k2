import QtQuick 2.15
import "../../../ui/components"
import QtQuick.Controls 2.15
Flickable {
    property var shell
    property var viewModel
    contentHeight: content.height; clip: true; boundsBehavior: Flickable.StopAtBounds
    ScrollIndicator.vertical: ScrollIndicator {}
    Column {
        id: content; width: parent.width; spacing: 24
        KText { visible: viewModel.infoLoading; text: "Reading device information…"; width: parent.width; color: Theme.secondary }
        KText { visible: !!viewModel.infoError; text: viewModel.infoError; width: parent.width; color: Theme.secondary }
        KButton { visible: !!viewModel.infoError; enabled: !viewModel.infoLoading; text: "Retry"; onClicked: viewModel.refreshInfo() }
        KSurface {
            width: parent.width; height: storageSummary.height + 40; radius: Theme.radius; color: Theme.wash
            Column {
                id: storageSummary; x: 20; y: 20; width: parent.width - 40; spacing: 12
                KText { text: "Internal storage"; heading: true; font.pixelSize: Theme.sectionSize }
                KText { text: viewModel.info.free + " free"; heading: true; font.pixelSize: Theme.titleSize }
                Rectangle { width: parent.width; height: 6; color: Theme.faint; Rectangle { width: parent.width * viewModel.info.usedFraction; height: parent.height; color: Theme.ink } }
                KText { text: viewModel.info.total + " total"; font.pixelSize: Theme.smallSize; color: Theme.secondary }
            }
        }
        Column {
            width: parent.width
            InfoRow { label: "User files"; value: viewModel.info.store }
            InfoRow { label: "Package files"; value: viewModel.info.sdk }
            InfoRow { label: "Package database"; value: viewModel.info.sdk ? viewModel.info.sdk + "/opkg" : ""; last: true }
        }
        Column {
            width: parent.width; spacing: 4
            KText { text: "Package feeds"; heading: true; font.pixelSize: Theme.sectionSize }
            Repeater { model: viewModel.info.feeds; InfoRow { label: modelData.name; value: modelData.url; stacked: true; last: index === viewModel.info.feeds.length - 1 } }
            KText { visible: !viewModel.infoLoading && !viewModel.infoError && viewModel.info.feeds.length === 0; text: "No feeds configured."; color: Theme.secondary; width: parent.width }
        }
    }
}
