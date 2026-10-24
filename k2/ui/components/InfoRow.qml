import QtQuick 2.15
Item {
    property string label
    property string value
    property bool stacked: false
    property bool last: false
    property bool badge: false
    property bool badgeEmphasized: false
    width: parent.width
    implicitHeight: Math.max(caption.y + caption.height, badge ? statusBadge.y + statusBadge.height : detail.y + detail.height) + 16
    height: implicitHeight
    KText {
        id: caption
        x: 0; y: stacked ? 16 : badge ? 16 + (statusBadge.height - height) / 2 : 16 + detail.baselineOffset - baselineOffset
        width: stacked ? parent.width : 144
        text: label; font.pixelSize: Theme.smallSize; color: Theme.secondary
    }
    KText {
        id: detail
        x: stacked ? 0 : 168; y: stacked ? caption.y + caption.height + 8 : 16
        width: parent.width - x
        visible: !badge
        text: value; font.pixelSize: Theme.bodySize
    }
    KBadge {
        id: statusBadge
        visible: badge; x: detail.x; y: detail.y
        text: value; emphasized: badgeEmphasized
    }
    Rectangle { visible: !last; anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.faint }
}
