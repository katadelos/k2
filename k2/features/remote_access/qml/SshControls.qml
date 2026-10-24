import QtQuick 2.15
import "../../../ui/components"
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Flickable {
    property var shell
    property var viewModel
    id: page
    property var state: viewModel.featureState
    readonly property bool wantsUsb: viewModel.featureTransport !== "wifi"
    readonly property bool wantsWifi: viewModel.featureTransport !== "usb"
    readonly property string transportError: [wantsUsb ? state.usbError || "" : "", wantsWifi ? state.wifiError || "" : ""].filter(function(value) { return value.length > 0 }).join("\n")
    readonly property bool canStart: !!state[({usb:"canStartUsb",wifi:"canStartWifi",both:"canStartBoth"})[viewModel.featureTransport]]
    contentHeight: content.height
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    ScrollIndicator.vertical: ScrollIndicator {}
    Column {
        id: content
        width: parent.width
        spacing: 24
        RowLayout {
            width: parent.width
            spacing: 16
            KIcon { name: "terminal"; Layout.preferredWidth: 28; Layout.preferredHeight: 28 }
            Column {
                Layout.fillWidth: true
                spacing: 6
                KText {
                    width: parent.width; heading: true; font.pixelSize: Theme.headingSize
                    text: viewModel.featureWorking ? "Changing developer tools…" : !page.state.schema ? viewModel.featureError ? "Status unavailable" : "Reading developer tools…" : page.state.ssh ? "SSH is running" : "SSH is stopped"
                }
                KText { width: parent.width; text: "Supernet · public-key authentication"; font.pixelSize: Theme.smallSize; color: Theme.secondary }
            }
            KButton {
                symbol: "refresh"; flat: true; Accessible.name: "Refresh connection status"
                enabled: viewModel.canRead && !viewModel.featureWorking
                onClicked: viewModel.refreshFeature()
            }
        }
        Column {
            width: parent.width; spacing: 10
            KText { text: "Connect over"; heading: true; font.pixelSize: Theme.sectionSize; width: parent.width }
            RowLayout {
                width: parent.width; spacing: 12
                Repeater {
                    model: [{value:"usb",title:"USB"},{value:"wifi",title:"Wi-Fi"},{value:"both",title:"Both"}]
                    KButton {
                        Layout.fillWidth: true; text: modelData.title
                        primary: viewModel.featureTransport === modelData.value
                        enabled: !viewModel.featureWorking && !page.state.ssh && (modelData.value === "wifi" || !page.state.adb)
                        Accessible.checkable: true; Accessible.checked: primary
                        onClicked: viewModel.setFeatureTransport(modelData.value)
                    }
                }
            }
            KText { visible: !!page.state.adbAvailable; text: "USB SSH and ADB use different USB modes. Stop one before enabling the other. Wi-Fi SSH can stay on."; font.pixelSize: Theme.smallSize; color: Theme.secondary; width: parent.width }
            KText { visible: !!page.state.ssh; text: "Stop SSH before changing the connection type."; font.pixelSize: Theme.smallSize; color: Theme.secondary; width: parent.width }
        }
        KText {
            width: parent.width
            visible: !!viewModel.featureError || !!page.state.error
            text: viewModel.featureError || page.state.error || ""
            color: Theme.ink
        }
        KText { width: parent.width; visible: !!page.transportError; text: page.transportError; color: Theme.secondary }
        Column {
            width: parent.width
            visible: !!page.state.schema && !page.state.keysReady
            spacing: 12
            KText { text: "Add your SSH public key"; heading: true; font.pixelSize: Theme.sectionSize; width: parent.width }
            KText { text: "Copy your computer’s SSH public key into this file, then refresh the status. Keep the private key on your computer."; width: parent.width; color: Theme.secondary }
            Rectangle {
                width: parent.width; height: keyPath.height + 28; color: Theme.wash
                KText { id: keyPath; x: 14; y: 14; width: parent.width - 28; text: page.state.keyPath || ""; font.pixelSize: Theme.smallSize; wrapMode: Text.WrapAnywhere }
            }
        }
        RowLayout {
            width: parent.width; spacing: 12
            KButton {
                Layout.fillWidth: true
                visible: !page.state.ssh
                primary: true
                text: "Start SSH"
                enabled: viewModel.canChange && !shell.packages.catalogWarning &&
                         page.canStart
                onClicked: viewModel.changeFeature("start")
            }
            KButton {
                Layout.fillWidth: true
                visible: !!page.state.ssh || !!page.state.canStop
                text: page.state.ssh ? "Stop SSH" : "Clean up connection"
                enabled: viewModel.canChange && !!page.state.canStop
                onClicked: viewModel.changeFeature("stop")
            }
        }
        Column {
            width: parent.width
            spacing: 16
            visible: !!page.state.adbAvailable || !!page.state.keepAwakeAvailable
            RowLayout {
                width: parent.width
                visible: !!page.state.adbAvailable
                Column {
                    Layout.fillWidth: true
                    spacing: 6
                    KText { width: parent.width; text: "ADB"; heading: true; font.pixelSize: Theme.sectionSize }
                    KText { width: parent.width; text: (page.state.ssh && page.state.usbEnabled ? "Stop USB SSH and select an ADB USB mode before enabling ADB." : page.state.adbError) || (page.state.adb ? "USB debugging is running." : "USB debugging is stopped."); color: Theme.secondary }
                }
                KSwitch {
                    objectName: "developerAdb"
                    Accessible.name: "ADB"
                    checked: !!page.state.adb
                    enabled: viewModel.canChange && !shell.packages.catalogWarning && (page.state.adb || (!page.state.adbError && !(page.state.ssh && page.state.usbEnabled)))
                    onClicked: viewModel.changeFeature(page.state.adb ? "adb-stop" : "adb-start")
                }
            }
            RowLayout {
                width: parent.width
                visible: !!page.state.keepAwakeAvailable
                Column {
                    Layout.fillWidth: true
                    spacing: 6
                    KText { width: parent.width; text: "Keep awake"; heading: true; font.pixelSize: Theme.sectionSize }
                    KText { width: parent.width; text: "Prevent sleep while debugging. Resets after reboot."; color: Theme.secondary }
                }
                KSwitch {
                    objectName: "developerKeepAwake"
                    Accessible.name: "Keep awake"
                    checked: !!page.state.keepAwake
                    enabled: viewModel.canChange && !shell.packages.catalogWarning
                    onClicked: viewModel.changeFeature(page.state.keepAwake ? "awake-off" : "awake-on")
                }
            }
        }
        Column {
            width: parent.width
            visible: !!page.state.schema
            InfoRow { label: "USB mode"; value: ({adb: "ADB", network: "USB networking", other: "Other"})[page.state.usbMode] || "Unavailable" }
            InfoRow { label: "Hostname"; value: page.state.hostname || "Unavailable" }
            InfoRow { visible: page.wantsUsb; label: "USB network"; value: page.state.network ? "On" : "Off"; badge: true; badgeEmphasized: !!page.state.network }
            InfoRow { visible: page.wantsUsb; label: "USB address"; value: (page.state.address || "") + "/" + (page.state.prefix || 24) }
            InfoRow { visible: page.wantsWifi; label: "Wi-Fi address"; value: page.state.wifiAddress || "Not connected" }
            InfoRow { label: "SSH port"; value: String(page.state.port || 22); last: true }
        }
        Column {
            width: parent.width
            visible: !!page.state.keysReady && page.wantsUsb
            spacing: 12
            KText { text: "Connect over USB"; heading: true; font.pixelSize: Theme.sectionSize; width: parent.width }
            KText { text: "Connect a USB cable and set the computer’s USB network address to " + (page.state.hostAddress || "") + ". " + (page.state.ssh ? "Connect with SSH:" : "Start SSH, then connect:"); width: parent.width; color: Theme.secondary }
            Rectangle {
                width: parent.width; height: command.height + 28; color: Theme.wash
                KText { id: command; x: 14; y: 14; width: parent.width - 28; text: "ssh " + (page.state.port && page.state.port !== 22 ? "-p " + page.state.port + " " : "") + "root@" + (page.state.address || "192.168.15.244"); wrapMode: Text.WrapAnywhere }
            }
        }
        Column {
            width: parent.width
            visible: !!page.state.keysReady && page.wantsWifi
            spacing: 12
            KText { text: "Connect over Wi-Fi"; heading: true; font.pixelSize: Theme.sectionSize; width: parent.width }
            KText { text: page.state.wifiAvailable ? "Connect your computer to the same Wi-Fi network. " + (page.state.ssh ? "Connect with SSH:" : "Start SSH, then connect:") : "Join a Wi-Fi network in the reader’s stock settings, then refresh the status here."; width: parent.width; color: Theme.secondary }
            Rectangle {
                visible: !!page.state.wifiAddress
                width: parent.width; height: wifiCommand.height + 28; color: Theme.wash
                KText { id: wifiCommand; x: 14; y: 14; width: parent.width - 28; text: "ssh " + (page.state.port && page.state.port !== 22 ? "-p " + page.state.port + " " : "") + "root@" + (page.state.wifiAddress || ""); wrapMode: Text.WrapAnywhere }
            }
        }
        KText { width: parent.width; visible: !!page.state.detail; text: page.state.detail || ""; font.pixelSize: Theme.smallSize; color: Theme.secondary }
        KText { width: parent.width; visible: !!shell.packages.catalogWarning; text: shell.packages.catalogWarning; font.pixelSize: Theme.smallSize; color: Theme.secondary }
        Column {
            width: parent.width; spacing: 16
            visible: !!page.state.kppAvailable
            KText { width: parent.width; text: "Kindle interface"; heading: true; font.pixelSize: Theme.sectionSize }
            KText { width: parent.width; visible: !!page.state.kppError; text: page.state.kppError || "" }
            KText { width: parent.width; visible: !!page.state.kppMessage; text: page.state.kppMessage || "" }
            KButton {
                width: parent.width; text: "Restart interface"
                enabled: viewModel.canChange && !viewModel.featureBusy && !page.state.kppBusy
                onClicked: viewModel.changeFeature("kpp-restart")
            }
            KButton {
                width: parent.width; text: "Disable optional extensions"
                enabled: viewModel.canChange && !viewModel.featureBusy && !page.state.kppBusy
                onClicked: viewModel.changeFeature("kpp-safe-mode")
            }
            KText { width: parent.width; text: "Extension errors"; heading: true; font.pixelSize: Theme.sectionSize }
            KText { width: parent.width; text: (page.state.kppErrors || []).join("\n\n") || "No recent extension errors."; font.pixelSize: Theme.smallSize; wrapMode: Text.WrapAnywhere }
            KButton {
                width: parent.width; text: "Export diagnostics"
                enabled: viewModel.canChange && !viewModel.featureBusy && !page.state.kppBusy
                onClicked: viewModel.changeFeature("kpp-export")
            }
        }
        KButton { width: parent.width; text: "Supernet package details"; symbol: "apps"; onClicked: shell.packages.selectPackage(viewModel.feature.package) }
    }
}
