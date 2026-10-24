import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../../ui/components"

Flickable {
    id: page
    objectName: "fileSharingPage"
    property var shell
    property var viewModel
    property var state: viewModel.state
    readonly property string connectionType: viewModel.connectionType
    property bool connectionHelp: false
    readonly property string computerName: connectionType === "windows"
        ? ((state.windows || "").split("\\")[2] || state.name || "Kindle").replace(".local", "").toUpperCase()
        : state.name || "Kindle"
    onConnectionTypeChanged: { connectionHelp = false; contentY = 0 }
    contentHeight: content.height
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    ScrollIndicator.vertical: ScrollIndicator {}

    Column {
        id: content
        width: parent.width
        spacing: 24
        RowLayout {
            width: parent.width; spacing: 16
            ColumnLayout {
                Layout.fillWidth: true; spacing: 5
                KText {
                    Layout.fillWidth: true; heading: true; font.pixelSize: Theme.headingSize
                    text: viewModel.working ? page.state.running ? "Stopping sharing…" : "Starting sharing…"
                        : !viewModel.statusKnown ? (viewModel.busy ? "Checking sharing…" : "Sharing status unavailable")
                        : page.state.running ? "Sharing is on" : "Sharing is off"
                }
                KText {
                    Layout.fillWidth: true; visible: viewModel.statusKnown && !!page.state.running
                    text: "Available on " + (page.state.network || "your Wi-Fi network")
                    color: Theme.secondary
                }
            }
            KButton {
                objectName: "stopSharingButton"
                visible: !viewModel.statusKnown || !!page.state.running; text: "Stop sharing"
                enabled: viewModel.canStop
                onClicked: viewModel.stopSharing()
            }
        }
        Column {
            width: parent.width; spacing: 12
            visible: !!viewModel.error || !!page.state.error
            KText { width: parent.width; text: viewModel.error || page.state.error || "" }
            KButton { text: "Try again"; enabled: !viewModel.busy; onClicked: viewModel.refresh() }
        }
        Column {
            width: parent.width; spacing: 20; visible: viewModel.statusKnown && !page.state.running
            KText { width: parent.width; heading: true; font.pixelSize: Theme.sectionSize; text: "Move files without a cable" }
            KText { width: parent.width; text: "Add books or download files from a phone, Mac or Windows PC on the same Wi-Fi network." }
            KText { width: parent.width; visible: !page.state.canStart; text: page.state.detail || "Connect this Kindle to Wi-Fi first."; color: Theme.secondary }
            KButton {
                width: parent.width; primary: true
                text: viewModel.working ? "Starting sharing…" : "Turn on sharing"
                enabled: viewModel.canChange && !!page.state.canStart && !shell.packages.catalogWarning
                onClicked: viewModel.startSharing()
            }
            KText {
                width: parent.width; visible: !viewModel.canChange && !viewModel.working
                text: "Another device task is finishing. Please wait a moment."; color: Theme.secondary
            }
            KText { width: parent.width; visible: !!shell.packages.catalogWarning; text: shell.packages.catalogWarning || ""; color: Theme.secondary }
            KText { width: parent.width; text: "Use a Wi-Fi network you trust."; font.pixelSize: Theme.smallSize; color: Theme.secondary }
        }
        Column {
            width: parent.width; spacing: 12; visible: viewModel.statusKnown && !!page.state.running
            KText { text: "Connect from"; heading: true; font.pixelSize: Theme.sectionSize }
            RowLayout {
                width: parent.width; spacing: 8
                Repeater {
                    model: [{key:"phone",label:"Phone"}, {key:"mac",label:"Mac"}, {key:"windows",label:"Windows"}]
                    KButton {
                        objectName: "sharingTab-" + modelData.key
                        Layout.fillWidth: true; Layout.preferredWidth: 1
                        text: modelData.label; primary: page.connectionType === modelData.key
                        Accessible.checkable: true; Accessible.checked: primary
                        onClicked: viewModel.setConnectionType(modelData.key)
                    }
                }
            }
        }
        Column {
            width: parent.width; spacing: 12
            visible: viewModel.statusKnown && !!page.state.running && page.connectionType === "phone"
            KText { width: parent.width; text: "Scan with your phone"; heading: true; font.pixelSize: Theme.headingSize; horizontalAlignment: Text.AlignHCenter }
            KText {
                width: parent.width; horizontalAlignment: Text.AlignHCenter
                text: "Join the same Wi-Fi, then open your camera.\nScan this code to add or download files."
            }
            Canvas {
                id: qr
                width: Math.min(parent.width, 246); height: width
                anchors.horizontalCenter: parent.horizontalCenter
                property var matrix: page.state.qr || []
                onMatrixChanged: requestPaint()
                onWidthChanged: requestPaint()
                onPaint: {
                    var ctx = getContext("2d"); ctx.fillStyle = "white"; ctx.fillRect(0, 0, width, height)
                    if (!matrix.length) return
                    var cell = Math.floor(width / matrix.length), margin = Math.floor((width - cell * matrix.length) / 2)
                    ctx.fillStyle = "black"
                    for (var y = 0; y < matrix.length; ++y)
                        for (var x = 0; x < matrix.length; ++x)
                            if (matrix[y][x]) ctx.fillRect(margin+x*cell, margin+y*cell, cell, cell)
                }
            }
            KText {
                width: Math.min(parent.width, 420); anchors.horizontalCenter: parent.horizontalCenter
                text: "Keep this code private. Anyone with it can access your files while sharing is on."
                horizontalAlignment: Text.AlignHCenter; font.pixelSize: Theme.smallSize; color: Theme.secondary
            }
        }
        Column {
            width: parent.width; spacing: 18
            visible: viewModel.statusKnown && !!page.state.running && page.connectionType !== "phone"
            Repeater {
                model: [page.connectionType === "mac" ? "On your Mac, open Finder and choose Network." : "On your PC, open File Explorer and choose Network.",
                        "Open " + page.computerName + ".",
                        page.connectionType === "mac" ? "When asked, choose Registered User and enter:" : "When Windows asks you to sign in, enter:"]
                RowLayout {
                    width: parent.width; spacing: 12
                    KBadge { text: String(index + 1); Layout.alignment: Qt.AlignTop }
                    KText { Layout.fillWidth: true; text: modelData }
                }
            }
            KSurface {
                width: parent.width; height: credentials.height + 32
                color: Theme.wash; radius: Theme.radius
                GridLayout {
                    id: credentials
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 16
                    columns: 2; columnSpacing: 24; rowSpacing: 12
                    KText { text: "Username"; font.pixelSize: Theme.smallSize; color: Theme.secondary }
                    KText { Layout.fillWidth: true; text: page.state.username || "" }
                    KText { text: "Password"; font.pixelSize: Theme.smallSize; color: Theme.secondary }
                    KText { Layout.fillWidth: true; text: page.state.password || ""; font.pixelSize: Theme.sectionSize; font.letterSpacing: 1 }
                }
            }
            KText { width: parent.width; text: "Open Reader, then drag files into it to add them to your Kindle."; color: Theme.secondary }
            KButton {
                objectName: "sharingHelpButton"
                width: parent.width; flat: true; alignLeft: true
                text: page.connectionHelp ? "Hide connection help" : "Can’t find your Kindle?"
                Accessible.checkable: true; Accessible.checked: page.connectionHelp
                onClicked: page.connectionHelp = !page.connectionHelp
            }
            Column {
                width: parent.width; spacing: 12; visible: page.connectionHelp
                KText { width: parent.width; text: "Check that your computer is on " + (page.state.network || "the same Wi-Fi network") + "." }
                KText {
                    width: parent.width
                    text: page.connectionType === "mac" ? "In Finder, choose Go, then Connect to Server. Enter:"
                        : "In File Explorer, enter this in the address bar:"
                }
                KText { width: parent.width; text: page.connectionType === "mac" ? page.state.mac || "" : page.state.windows || ""; wrapMode: Text.WrapAnywhere }
                KText { width: parent.width; text: "If that does not connect, use this address instead:"; font.pixelSize: Theme.smallSize; color: Theme.secondary }
                KText { width: parent.width; text: page.connectionType === "mac" ? "smb://" + (page.state.address || "") + "/Reader" : page.state.direct || ""; wrapMode: Text.WrapAnywhere }
            }
        }
    }
}
