import QtQuick 2.15
import "../components"
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
Item {
    id: content
    property var shell
    readonly property var appShell: shell
    readonly property bool applicationLoadFailed: pageLoader.status === Loader.Error
    onVisibleChanged: if (visible && buttonNavigation) initialFocus.restart()
    Timer {
        id: initialFocus
        interval: 0
        onTriggered: appRuntime.keys.focusFirst(pageLoader.item)
    }
    Connections {
        target: appRuntime.keys
        function onRequested(action) {
            if (action === "back") {
                if (shell.confirmations.active || shell.controls.controlsOpen) shell.back()
                else if (!pageLoader.item || !pageLoader.item.dismissKeyboard || !pageLoader.item.dismissKeyboard()) shell.back()
                initialFocus.restart()
            } else if (action === "home") {
                if (shell.confirmations.active) shell.confirmations.cancel()
                shell.controls.closeControls()
                shell.navigation.navigate("home")
            } else if (action === "menu") {
                if (!shell.confirmations.active) shell.controls.toggleControls()
            } else if (action === "keyboard") {
                if (pageLoader.item && pageLoader.item.toggleKeyboard) pageLoader.item.toggleKeyboard()
            } else if (action === "previous" || action === "next") {
                var direction = action === "next" ? 1 : -1
                if (pageLoader.item && pageLoader.item.turnPage) pageLoader.item.turnPage(direction)
                else appRuntime.keys.scrollPage(direction)
            }
        }
    }
    Shortcut {
        sequence: "Escape"
        enabled: content.enabled && !shell.packages.loading
        onActivated: {
            if (shell.confirmations.active || shell.controls.controlsOpen) shell.back()
            else if (!pageLoader.item || !pageLoader.item.dismissKeyboard || !pageLoader.item.dismissKeyboard()) shell.back()
        }
    }
    Rectangle {
        id: surface
        color: Theme.paper; width: 600; height: content.height / (content.width / 600)
        scale: content.width / 600; transformOrigin: Item.TopLeft
        // Composite headless captures to avoid seams between scaled items.
        // Native software windows must render directly; Cocoa layers go blank.
        layer.enabled: offscreenPreview
        layer.smooth: true
        layer.textureSize: Qt.size(panelWidth, Math.round(height * panelWidth / width))
        ColumnLayout {
            visible: !shell.packages.loading
            enabled: !shell.controls.controlsOpen && !shell.confirmations.active
            anchors.fill: parent; anchors.margins: 24; anchors.topMargin: 6; spacing: 16
            AppHeader {
                shell: content.appShell
                Layout.fillWidth: true
                title: shell.navigation.title
                actions: pageLoader.item && pageLoader.item.headerActions ? pageLoader.item.headerActions : null
            }
            KButton {
                readonly property var activity: shell.operations.activity
                visible: !!activity.route && shell.navigation.page !== activity.route && shell.navigation.page.indexOf(activity.route + "-") !== 0 && shell.navigation.page !== "home" && (activity.hiddenPages || []).indexOf(shell.navigation.page) < 0
                Layout.fillWidth: true; text: activity.title || ""; symbol: "refresh"; alignLeft: true
                onClicked: shell.navigation.navigate(activity.route)
            }
            Loader {
                id: pageLoader
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 0
                enabled: !routeLoad.running
                onLoaded: {
                    if (content.visible && !shell.packages.loading) appRuntime.displayPageChanged()
                    if (buttonNavigation) initialFocus.restart()
                }
                function loadRoute() {
                    setSource(shell.navigation.source, {shell: content.appShell, viewModel: shell.navigation.model})
                }
                Component.onCompleted: loadRoute()
                Timer {
                    id: routeLoad
                    interval: 0
                    // Let the outgoing page finish its input and model callbacks
                    // before destroying its controls and delegates.
                    onTriggered: pageLoader.loadRoute()
                }
                Connections {
                    target: shell.navigation
                    function onRouteChanged() { routeLoad.restart() }
                }
            }
            KText {
                visible: buttonNavigation && !(pageLoader.item && pageLoader.item.keyboardOpen)
                Layout.fillWidth: true
                text: "D-pad: move · Centre: select · Back · Menu: controls"
                font.pixelSize: 12
                color: Theme.secondary
                horizontalAlignment: Text.AlignHCenter
            }
        }
        DevicePopover { anchors.fill: parent; shell: content.appShell }
        TapHandler {
            onTapped: {
                if (pageLoader.item && pageLoader.item.dismissKeyboardAt) {
                    var position = pageLoader.item.mapFromItem(surface, point.position.x, point.position.y)
                    pageLoader.item.dismissKeyboardAt(position.x, position.y)
                }
            }
        }
        Item {
            Component.onCompleted: appRuntime.keys.registerScope(this, 40)
            visible: shell.confirmations.active
            onVisibleChanged: if (visible) cancelAction.forceActiveFocus()
            anchors.fill: parent
            MouseArea { anchors.fill: parent }
            KSurface {
                anchors.centerIn: parent; width: parent.width - 64; height: dialog.height + 56
                color: Theme.paper; borderColor: Theme.ink; borderWidth: 2; radius: Theme.radius
                ColumnLayout {
                    id: dialog; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 28; spacing: 24
                    KText { text: shell.confirmations.pending.title || ""; font.pixelSize: 26; heading: true; Layout.fillWidth: true }
                    KText { text: shell.confirmations.pending.body || ""; font.pixelSize: 17; color: Theme.secondary; Layout.fillWidth: true }
                    Flickable {
                        visible: !!shell.confirmations.pending.changes && shell.confirmations.pending.changes.length > 0
                        Layout.fillWidth: true; Layout.preferredHeight: Math.min(changes.height, surface.height * 0.22)
                        contentHeight: changes.height; clip: true; boundsBehavior: Flickable.StopAtBounds
                        ScrollIndicator.vertical: ScrollIndicator {}
                        Column {
                            id: changes; width: parent.width; spacing: 12
                            Repeater {
                                model: shell.confirmations.pending.changes || []
                                Column {
                                    width: changes.width; spacing: 4
                                    KText { text: ({install:"Install",upgrade:"Update",update:"Update",remove:"Remove",configure:"Finish setup"})[modelData.action] + " " + modelData.name; heading: true; font.pixelSize: Theme.controlSize; width: parent.width }
                                    KText { text: modelData.fromVersion && modelData.toVersion ? modelData.fromVersion + " → " + modelData.toVersion : modelData.toVersion || modelData.fromVersion; font.pixelSize: Theme.smallSize; color: Theme.secondary; width: parent.width }
                                }
                            }
                        }
                    }
                    KText { visible: !!shell.confirmations.pending.error; text: shell.confirmations.pending.error || ""; font.pixelSize: Theme.smallSize; Layout.fillWidth: true; maximumLineCount: 5; elide: Text.ElideRight }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 12
                        KButton { id: cancelAction; text: "Cancel"; Layout.fillWidth: true; onClicked: shell.confirmations.cancel() }
                        KButton { text: shell.confirmations.pending.label || "Continue"; primary: true; enabled: shell.confirmations.canConfirm; Layout.fillWidth: true; onClicked: shell.confirmations.confirm() }
                    }
                }
            }
        }
        Rectangle {
            visible: buttonNavigation && appRuntime.keys.focusRect.width > 0
            x: appRuntime.keys.focusRect.x / surface.scale
            y: appRuntime.keys.focusRect.y / surface.scale
            width: appRuntime.keys.focusRect.width / surface.scale
            height: appRuntime.keys.focusRect.height / surface.scale
            color: "transparent"
            border.color: Theme.ink
            border.width: 3
            radius: 3
        }
    }
}
