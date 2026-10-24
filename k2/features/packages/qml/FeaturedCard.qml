import QtQuick 2.15
import "../../../ui/components"

KSurface {
    id: card
    property var entry
    signal activated()
    readonly property bool fullWidth: entry.width === "full"
    readonly property bool hasImage: !!entry.image && logo.status !== Image.Error
    readonly property int inset: 20
    readonly property int imageSize: fullWidth ? Math.min(144, width * 0.29) : Math.min(120, width - inset * 2)
    readonly property int contentGap: 16
    implicitHeight: fullWidth
        ? Math.max(copy.implicitHeight, hasImage ? imageSize : 0) + inset * 2
        : copy.implicitHeight + (hasImage ? imageSize + contentGap : 0) + inset * 2
    radius: Theme.radius
    color: Theme.paper
    borderColor: Theme.ink

    Image {
        id: logo
        visible: card.hasImage
        source: card.entry.image || ""
        asynchronous: true
        fillMode: Image.PreserveAspectFit
        width: card.imageSize; height: width
        x: card.fullWidth ? card.width - card.inset - width : (card.width - width) / 2
        y: card.fullWidth ? (card.height - height) / 2 : card.inset
        Accessible.ignored: true
    }
    Column {
        id: copy
        x: card.inset
        y: card.fullWidth ? (card.height - height) / 2 : card.inset + (card.hasImage ? card.imageSize + card.contentGap : 0)
        width: card.width - card.inset * 2 - (card.fullWidth && card.hasImage ? card.imageSize + card.contentGap : 0)
        spacing: 12
        KText {
            text: card.entry.title
            width: parent.width; heading: true
            font.pixelSize: card.fullWidth ? 30 : 25
        }
        KText {
            visible: !!text; text: card.entry.headline || ""
            width: parent.width; heading: true
            font.pixelSize: card.fullWidth ? 23 : 20
        }
        KText {
            visible: !!text; text: card.entry.description || ""
            width: parent.width; color: Theme.secondary
            font.pixelSize: Theme.bodySize
        }
        KButton {
            id: action
            text: card.entry.action.label
            primary: card.fullWidth
            implicitWidth: actionLabel.implicitWidth + leftPadding + rightPadding
            implicitHeight: Math.max(Theme.touchSize, actionLabel.implicitHeight + topPadding + bottomPadding)
            width: Math.min(parent.width, implicitWidth)
            onClicked: card.activated()
            Accessible.name: text + ", " + card.entry.title
            contentItem: KText {
                id: actionLabel
                text: action.text; font: action.font; color: action.foreground
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
