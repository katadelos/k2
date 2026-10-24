import QtQuick 2.15
import "../components"
import QtQuick.Layouts 1.15
ColumnLayout {
    property var shell
    property var viewModel
    spacing: 24
    Column {
        Layout.fillWidth: true; spacing: 8
        KText { text: "More from your device"; font.pixelSize: Theme.titleSize; heading: true; width: parent.width }
        KText { text: shell.controls.info.model; color: Theme.secondary; width: parent.width }
    }
    GridLayout {
        Layout.fillWidth: true
        columns: 2; columnSpacing: 16; rowSpacing: 16
        Repeater {
            model: [{title:"App Store", detail:"Browse and manage packages", page:"apps", icon:"apps"},
                    {title:"KOReader", detail:"Read and customise", page:"koreader", icon:"book"},
                    {title:"File manager", detail:"Browse files and folders", page:"files", icon:"storage"},
                    {title:"About k2", detail:"Version and information", page:"about", icon:"info"}]
            KButton {
                id: tile
                Layout.fillWidth: true; Layout.preferredHeight: 140
                padding: 20
                onClicked: shell.navigation.navigate(modelData.page)
                contentItem: Item {
                    KIcon { name: modelData.icon; ink: tile.foreground; width: 28; height: 28; anchors.top: parent.top; anchors.left: parent.left }
                    KIcon { name: "arrow"; ink: tile.foreground; width: 18; height: 18; anchors.top: parent.top; anchors.right: parent.right }
                    Column {
                        anchors.bottom: parent.bottom; width: parent.width; spacing: 8
                        KText { text: modelData.title; color: tile.foreground; font.pixelSize: Theme.sectionSize; heading: true }
                        KText { text: modelData.detail; font.pixelSize: Theme.smallSize; color: tile.down ? Theme.paper : Theme.secondary; width: parent.width }
                    }
                }
            }
        }
    }
    KButton {
        id: review
        Layout.fillWidth: true; implicitHeight: 80; padding: 16
        onClicked: { if (shell.packages.failed || shell.packages.busy) shell.navigation.navigate("activity"); else { shell.packages.search(""); shell.packages.setTab(shell.packages.updateCount ? "Updates" : "Installed"); shell.navigation.navigate("apps") } }
        contentItem: RowLayout {
            spacing: 16
            KIcon { name: shell.packages.busy ? "refresh" : shell.packages.failed ? "info" : shell.packages.updateCount ? "download" : "check"; ink: review.foreground; width: 24; height: 24 }
            Column {
                Layout.fillWidth: true; spacing: 6
                KText { text: shell.packages.busy || shell.packages.failed ? shell.packages.activityTitle : shell.packages.updateCount ? shell.packages.updateCount + (shell.packages.updateCount === 1 ? " update available" : " updates available") : "No updates available"; font.pixelSize: Theme.controlSize; heading: true; color: review.foreground; width: parent.width }
                KText { text: shell.packages.failed ? "Open activity for details" : shell.packages.installedCount + " packages installed"; color: review.down ? Theme.paper : Theme.secondary; font.pixelSize: Theme.smallSize }
            }
            KIcon { name: "arrow"; ink: review.foreground; width: 18; height: 18 }
        }
    }
    Item { Layout.fillHeight: true }
    RowLayout {
        Layout.fillWidth: true; spacing: 8
        KIcon { name: "storage"; width: 18; height: 18; ink: Theme.secondary }
        KText { text: shell.controls.info.free + " free"; font.pixelSize: Theme.smallSize; color: Theme.secondary; Layout.fillWidth: true }
        KText { text: "k2 " + shell.version; font.pixelSize: Theme.smallSize; color: Theme.secondary }
    }
}
