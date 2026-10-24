import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../../ui/components"

Flickable {
    id: featured
    property var viewModel
    readonly property var catalog: viewModel.featured
    readonly property var cardRows: groupCards(catalog.items)
    contentWidth: width
    contentHeight: content.height
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    flickableDirection: Flickable.VerticalFlick
    ScrollIndicator.vertical: ScrollIndicator {}

    function groupCards(items) {
        var result = []
        for (var index = 0; index < items.length; ++index) {
            var row = [items[index]]
            if (items[index].width === "half" && index + 1 < items.length && items[index + 1].width === "half")
                row.push(items[++index])
            result.push(row)
        }
        return result
    }

    Column {
        id: content
        width: featured.width
        spacing: 12
        Repeater {
            model: featured.cardRows
            RowLayout {
                id: cardRow
                property var entries: modelData
                width: content.width
                spacing: 12
                Repeater {
                    model: cardRow.entries
                    FeaturedCard {
                        Layout.fillWidth: true; Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        entry: modelData
                        onActivated: featured.viewModel.openFeatured(entry.id)
                    }
                }
                Item {
                    visible: cardRow.entries.length === 1 && cardRow.entries[0].width === "half"
                    Layout.fillWidth: true; Layout.preferredWidth: 1
                }
            }
        }
        Column {
            visible: featured.catalog.items.length === 0
            width: parent.width
            topPadding: 24; bottomPadding: 12
            spacing: 16
            KText {
                width: parent.width
                text: featured.catalog.loading ? "Loading featured apps…" : featured.catalog.error ? "Featured apps are unavailable" : "More apps to discover soon"
                heading: true; font.pixelSize: Theme.headingSize
                horizontalAlignment: Text.AlignHCenter
            }
            KText {
                visible: !featured.catalog.loading
                width: parent.width
                text: featured.catalog.error ? "Try again, or browse all packages below." : "Browse all packages to find apps and tools for your reader."
                color: Theme.secondary
                horizontalAlignment: Text.AlignHCenter
            }
            KButton {
                visible: !!featured.catalog.error && !featured.catalog.loading
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Try again"
                onClicked: featured.catalog.refresh()
            }
        }
        RowLayout {
            visible: featured.catalog.items.length > 0 && !!featured.catalog.error
            width: parent.width; spacing: 12
            KText {
                Layout.fillWidth: true
                text: "Couldn’t refresh featured apps."
                color: Theme.secondary; font.pixelSize: Theme.smallSize
            }
            KButton {
                text: "Try again"; enabled: !featured.catalog.loading
                onClicked: featured.catalog.refresh()
            }
        }
        KButton {
            width: parent.width
            implicitHeight: 64
            text: "Browse all packages"
            symbol: "apps"; alignLeft: true
            rightPadding: 40
            onClicked: featured.viewModel.setTab("All")
            KIcon {
                name: "arrow"; width: 18; height: 18
                anchors.right: parent.right; anchors.rightMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                ink: parent.foreground
            }
        }
    }
}
