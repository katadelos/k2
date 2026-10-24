import QtQuick 2.15
import "../components"
import QtQuick.Controls 2.15
Flickable {
    property var shell
    property var viewModel
    contentHeight: content.height; clip: true; boundsBehavior: Flickable.StopAtBounds
    ScrollIndicator.vertical: ScrollIndicator {}
    Column {
        id: content; width: parent.width; spacing: 24
        Item {
            width: parent.width; height: 210; clip: true
            Image { anchors.right: parent.right; width: 270; height: 270; source: "../assets/mountain.png"; fillMode: Image.PreserveAspectFit }
            Column {
                y: 24; width: parent.width - 250; spacing: 12
                KText { text: "k2"; heading: true; font.pixelSize: 56 }
                KText { text: "More from\nyour device"; font.pixelSize: 22; width: parent.width }
            }
        }
        KText { text: "App Store for your reader"; width: parent.width; font.pixelSize: Theme.sectionSize; heading: true }
        KText { text: "Install apps, manage packages and check for updates."; width: parent.width; color: Theme.secondary }
        Column {
            width: parent.width
            InfoRow { label: "Version"; value: shell.version + " · alpha" }
            InfoRow { label: "Open k2 from"; value: shell.controls.info.launcher; last: true }
        }
        KText { text: "Built with Python, Qt Quick and opkg.\nMIT license."; font.pixelSize: Theme.smallSize; color: Theme.secondary; width: parent.width }
    }
}
