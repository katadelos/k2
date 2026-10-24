import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../../ui/components"

Flickable {
    id: page
    objectName: "screenSharingPage"
    property var shell
    property var viewModel
    readonly property var state: viewModel ? viewModel.featureState : ({})
    readonly property bool running: !!state.running
    contentHeight: content.height
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    ScrollIndicator.vertical: ScrollIndicator {}
    Column {
        id: content
        width: parent.width
        spacing: 20
        RowLayout {
            width: parent.width
            spacing: 16
            Column {
                Layout.fillWidth: true
                spacing: 8
                KText {
                    width: parent.width; heading: true; font.pixelSize: Theme.headingSize
                    text: viewModel && viewModel.featureWorking ? "Changing screen sharing…" : page.running ? "Screen sharing is on" : "Screen sharing is off"
                }
                KText {
                    width: parent.width; color: Theme.secondary
                    text: page.running ? "View and control this Kindle from your computer." : "Use a VNC viewer to see the screen, tap and type."
                }
            }
            KButton {
                objectName: "stopScreenSharingButton"
                visible: page.running
                text: "Stop sharing"
                enabled: viewModel && viewModel.canChange
                onClicked: viewModel.changeFeature("stop")
            }
        }
        KText {
            width: parent.width
            visible: !!(viewModel && viewModel.featureError) || !!page.state.error
            text: (viewModel ? viewModel.featureError : "") || page.state.error || ""
        }
        Column {
            width: parent.width
            spacing: 16
            visible: !page.running
            KText {
                width: parent.width; color: Theme.secondary
                text: "Share over Wi-Fi and USB networking. Both connections work when available."
            }
            KText {
                width: parent.width; color: Theme.secondary
                visible: !page.state.canStart
                text: "Join Wi-Fi or enable USB networking in the SSH tab first."
            }
            KButton {
                objectName: "startScreenSharingButton"
                width: parent.width; primary: true; text: "Start screen sharing"
                enabled: viewModel && viewModel.canChange && !shell.packages.catalogWarning && !!page.state.canStart
                onClicked: viewModel.changeFeature("start")
            }
        }
        Column {
            width: parent.width; spacing: 16; visible: page.running
            KText { width: parent.width; text: "Connect with a VNC viewer"; heading: true; font.pixelSize: Theme.sectionSize }
            KText { width: parent.width; text: "Enter this address and password in your computer’s VNC app. On a Mac, open Screen Sharing."; color: Theme.secondary }
            Rectangle {
                width: parent.width; height: credentials.height + 32; color: Theme.wash
                Column {
                    id: credentials; x: 16; y: 16; width: parent.width - 32; spacing: 16
                    Repeater {
                        model: [{title: "Wi-Fi", address: page.state.wifiAddress || ""},
                                {title: "USB", address: page.state.usbAddress || ""}]
                        Column {
                            width: credentials.width; spacing: 6
                            visible: !!modelData.address
                            KText { text: modelData.title; font.pixelSize: Theme.smallSize; color: Theme.secondary }
                            KText { width: parent.width; text: modelData.address + ":" + (page.state.port || 5900); wrapMode: Text.WrapAnywhere; heading: true; font.pixelSize: Theme.sectionSize }
                        }
                    }
                    KText { width: parent.width; visible: !page.state.wifiAddress && !page.state.usbAddress; text: "Waiting for Wi-Fi or USB networking…"; color: Theme.secondary }
                    Column {
                        width: parent.width; spacing: 6
                        KText { text: "Password"; font.pixelSize: Theme.smallSize; color: Theme.secondary }
                        KText { text: page.state.password || ""; heading: true; font.pixelSize: Theme.sectionSize; font.letterSpacing: 1 }
                    }
                }
            }
            KText { width: parent.width; text: "A new password is created each time you start sharing. The Kindle stays awake until you stop."; color: Theme.secondary; font.pixelSize: Theme.smallSize }
        }
        KText { width: parent.width; text: "Use a trusted network. VNC screen and input traffic are not encrypted."; color: Theme.secondary; font.pixelSize: Theme.smallSize }
        KText { width: parent.width; visible: !!page.state.detail; text: page.state.detail || ""; color: Theme.secondary }
        KText { width: parent.width; visible: !!(shell && shell.packages.catalogWarning); text: shell ? shell.packages.catalogWarning : ""; color: Theme.secondary }
        KButton { width: parent.width; flat: true; text: "Screen sharing package"; onClicked: shell.packages.selectPackage(viewModel.feature.package) }
    }
}
