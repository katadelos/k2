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
        PageHeading { title: viewModel.info.model; description: viewModel.info.family === "kindle" ? "Amazon Kindle" : "Rakuten Kobo"; symbol: "device" }
        KMenuRow {
            width: parent.width; text: "KOReader"; detail: "Install the reader and manage its plugins"; symbol: "book"
            onClicked: shell.navigation.navigate("koreader")
        }
        KMenuRow {
            width: parent.width; text: "Files"; detail: "Browse and organise books, documents and folders"; symbol: "folder"
            onClicked: shell.navigation.navigate("files")
        }
        Column {
            width: parent.width; visible: shell.packages.features.length > 0
            Repeater {
                model: shell.packages.features
                KButton {
                    id: featureLink
                    width: parent.width; implicitHeight: 84; flat: true; padding: 0
                    onClicked: shell.packages.selectFeature(modelData.id)
                    contentItem: Item {
                        KIcon { name: modelData.popover ? modelData.popover.icon : "apps"; width: 24; height: 24; anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; ink: featureLink.foreground }
                        Column {
                            anchors.left: parent.left; anchors.leftMargin: 44; anchors.right: parent.right; anchors.rightMargin: 28
                            anchors.verticalCenter: parent.verticalCenter; spacing: 6
                            KText { text: modelData.title; heading: true; width: parent.width; color: featureLink.foreground }
                            KText { text: modelData.description; font.pixelSize: Theme.smallSize; color: featureLink.down ? Theme.paper : Theme.secondary; width: parent.width }
                        }
                        KIcon { name: "arrow"; width: 18; height: 18; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; ink: featureLink.foreground }
                    }
                    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.faint }
                }
            }
        }
        KText { visible: !!shell.packages.featureErrors; text: shell.packages.featureErrors; width: parent.width; font.pixelSize: Theme.smallSize; color: Theme.secondary }
        Column {
            width: parent.width
            InfoRow { label: "Firmware"; value: viewModel.info.firmware }
            InfoRow { label: "Architecture"; value: viewModel.info.architecture }
            InfoRow { label: "Kernel"; value: viewModel.info.kernel }
            InfoRow { label: "Launcher"; value: viewModel.info.launcher; last: true }
        }
    }
}
