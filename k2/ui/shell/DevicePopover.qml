import QtQuick 2.15
import "../components"
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
Item {
    property var shell
    visible: shell.controls.controlsOpen && !shell.packages.loading
    onVisibleChanged: if (visible) appRuntime.appearance.refresh()
    MouseArea { anchors.fill: parent; onClicked: shell.controls.closeControls() }
    KSurface {
        anchors.right: parent.right; anchors.rightMargin: 24; y: 60
        width: 320; height: Math.min(contents.height + 36, parent.height - y - 24)
        color: Theme.paper; borderColor: Theme.ink; borderWidth: 2; radius: Theme.radius
        MouseArea { anchors.fill: parent }
        Flickable {
            anchors.fill: parent; anchors.margins: 18
            contentHeight: contents.height; clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollIndicator.vertical: ScrollIndicator {}
            Column {
                id: contents
                width: parent.width; spacing: 8
                Column {
                    width: parent.width
                    Item {
                        width: parent.width; height: 44
                        KIcon { name: "wifi"; x: 12; y: 11; width: 22; height: 22 }
                        TextMetrics { id: wifiCapital; font: wifiLabel.font; text: "H" }
                        KText {
                            id: wifiLabel
                            x: 42; y: Math.round((44 - wifiCapital.tightBoundingRect.height) / 2 - baselineOffset - wifiCapital.tightBoundingRect.y)
                            text: "Wi-Fi"; font.pixelSize: Theme.controlSize; heading: true
                        }
                        KSwitch {
                            anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
                            checked: !!shell.controls.wifi.enabled
                            enabled: !!shell.controls.wifi.available && !shell.controls.wifiChanging && shell.controls.canChangeWifi
                            onClicked: shell.controls.setWifi(!shell.controls.wifi.enabled)
                            Accessible.name: "Wi-Fi"
                        }
                    }
                    KText { x: 42; text: !shell.controls.wifi.available && shell.controls.controlsBusy ? "Checking Wi-Fi…" : shell.controls.wifi.connected && shell.controls.wifi.ssid ? "Connected to " + shell.controls.wifi.ssid : shell.controls.wifi.status; width: parent.width - 54; font.pixelSize: Theme.smallSize; color: Theme.secondary }
                }
                Column {
                    visible: shell.controls.brightness.available; width: parent.width
                    Item {
                        width: parent.width; height: 44
                        KIcon { name: "brightness"; x: 12; y: 11; width: 22; height: 22 }
                        TextMetrics { id: lightCapital; font: lightLabel.font; text: "H" }
                        KText {
                            id: lightLabel
                            x: 42; y: Math.round((44 - lightCapital.tightBoundingRect.height) / 2 - baselineOffset - lightCapital.tightBoundingRect.y)
                            text: "Brightness"; font.pixelSize: Theme.controlSize; heading: true
                        }
                        KText { anchors.right: parent.right; anchors.rightMargin: 12; anchors.baseline: lightLabel.baseline; text: Math.round(light.value / light.to * 100) + "%"; font.pixelSize: 15; color: Theme.secondary }
                    }
                    Slider {
                        id: light
                        x: 12; width: parent.width - 24; implicitHeight: 40
                        from: 0; to: shell.controls.brightness.maximum; stepSize: 1
                        Component.onCompleted: value = shell.controls.brightness.value
                        // The thumb owns its position during a drag. Device replies
                        // and Wi-Fi polling must not reapply an older value.
                        Connections {
                            target: shell.controls
                            function onChanged() {
                                if (!light.pressed && !shell.controls.brightnessChanging)
                                    light.value = shell.controls.brightness.value
                            }
                        }
                        Timer {
                            id: brightnessSend
                            interval: 150
                            onTriggered: shell.controls.setBrightness(Math.round(light.value))
                        }
                        onMoved: {
                            if (!pressed) shell.controls.setBrightness(Math.round(value))
                            else if (!brightnessSend.running) brightnessSend.start()
                        }
                        onPressedChanged: if (!pressed) {
                            brightnessSend.stop()
                            shell.controls.setBrightness(Math.round(value))
                        }
                        background: Rectangle {
                            x: light.leftPadding; y: light.topPadding + light.availableHeight / 2 - height / 2
                            width: light.availableWidth; height: 4; color: Theme.faint
                            Rectangle { width: light.visualPosition * parent.width; height: parent.height; color: Theme.ink }
                        }
                        handle: KSurface {
                            x: light.leftPadding + light.visualPosition * (light.availableWidth - width)
                            y: light.topPadding + light.availableHeight / 2 - height / 2
                            width: 22; height: 22; radius: 11; color: Theme.ink
                        }
                    }
                    Item { width: 1; height: 8 }
                }
                Item {
                    width: parent.width; height: 44
                    KIcon { name: "moon"; x: 12; y: 11; width: 22; height: 22 }
                    TextMetrics { id: darkCapital; font: darkLabel.font; text: "H" }
                    KText {
                        id: darkLabel
                        x: 42; y: Math.round((44 - darkCapital.tightBoundingRect.height) / 2 - baselineOffset - darkCapital.tightBoundingRect.y)
                        text: "Dark mode"; font.pixelSize: Theme.controlSize; heading: true
                    }
                    KSwitch {
                        anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
                        checked: appRuntime.appearance.darkMode
                        enabled: !appRuntime.appearance.busy
                        onClicked: appRuntime.appearance.setDarkMode(!appRuntime.appearance.darkMode)
                        Accessible.name: "Dark mode"
                    }
                }
                Item {
                    visible: deviceFamily === "kindle"
                    width: parent.width; height: 44
                    KIcon { name: "fullscreen"; x: 12; y: 11; width: 22; height: 22 }
                    TextMetrics { id: fullScreenCapital; font: fullScreenLabel.font; text: "H" }
                    KText {
                        id: fullScreenLabel
                        x: 42; y: Math.round((44 - fullScreenCapital.tightBoundingRect.height) / 2 - baselineOffset - fullScreenCapital.tightBoundingRect.y)
                        text: "Full screen"; font.pixelSize: Theme.controlSize; heading: true
                    }
                    KSwitch {
                        anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
                        checked: appRuntime.appearance.fullScreen
                        onClicked: appRuntime.appearance.setFullScreen(!appRuntime.appearance.fullScreen)
                        Accessible.name: "Full screen"
                    }
                }
                KText { visible: !!appRuntime.appearance.error; x: 12; text: appRuntime.appearance.error; width: parent.width - 24; font.pixelSize: 14 }
                KText { visible: !!shell.controls.controlError; x: 12; text: shell.controls.controlError; width: parent.width - 24; font.pixelSize: 14 }
                Rectangle { visible: shell.reader.popoverReaderAvailable || shell.packages.popoverFeatures.length > 0; x: 12; width: parent.width - 24; height: 1; color: Theme.line }
                KButton {
                    visible: shell.reader.popoverReaderAvailable
                    text: "KOReader"; symbol: "book"; flat: true; alignLeft: true; width: parent.width
                    enabled: shell.reader.canOpen
                    onClicked: shell.reader.openReaderShortcut()
                }
                Repeater {
                    model: shell.packages.popoverFeatures
                    KButton {
                        text: modelData.title; symbol: modelData.popover.icon
                        flat: true; alignLeft: true; width: contents.width
                        onClicked: shell.packages.selectFeature(modelData.id)
                    }
                }
                Rectangle { x: 12; width: parent.width - 24; height: 1; color: Theme.line }
                KButton { text: "Device details"; symbol: "device"; flat: true; alignLeft: true; width: parent.width; onClicked: shell.navigation.navigate("device") }
                KButton { text: "Exit k2"; symbol: "exit"; flat: true; alignLeft: true; width: parent.width; enabled: shell.operations.canExit; onClicked: shell.quit() }
                KText { visible: shell.packages.busy || shell.remote.featureWorking || shell.reader.readerWorking; x: 12; text: (shell.reader.readerWorking ? shell.reader.readerActivity : shell.remote.featureWorking ? "Updating remote access settings…" : shell.packages.activityTitle) + "\nYou can exit when this finishes."; width: parent.width - 24; color: Theme.secondary; font.pixelSize: 13 }
            }
        }
    }
}
