import QtQuick 2.15
import "../components"

Column {
    property var shell
    property var viewModel
    spacing: 24
    PageHeading {
        width: parent.width
        title: "KPP Mods"
        description: "Kindle interface extensions"
        symbol: "plugin"
    }
    KText {
        width: parent.width
        text: buttonNavigation ? "KPP Mods is not supported on Kindle 4." : "Extension controls are not available in k2 yet."
        color: Theme.secondary
    }
    KMenuRow {
        visible: !buttonNavigation
        width: parent.width
        text: "Package details"
        detail: "Install or update KPP Mods"
        symbol: "apps"
        onClicked: shell.packages.selectPackage("kppmods")
    }
}
