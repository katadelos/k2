import QtQuick 2.15
import "../../../ui/components"
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
ColumnLayout {
    property var shell
    property var viewModel
    id: activity
    property bool detailsOpen: viewModel.failed
    spacing: 24
    PageHeading {
        Layout.fillWidth: true
        title: viewModel.activityTitle
        description: !viewModel.busy && !viewModel.failed && !viewModel.operation.action ? "No recent activity." : ""
        symbol: viewModel.busy ? "refresh" : viewModel.failed ? "info" : "check"
    }
    KText {
        visible: viewModel.failed; Layout.fillWidth: true
        text: viewModel.message; font.pixelSize: Theme.smallSize; maximumLineCount: 4; elide: Text.ElideRight
    }
    KText { visible: !!viewModel.stateWarning; text: viewModel.stateWarning; Layout.fillWidth: true; font.pixelSize: Theme.smallSize }
    KText { visible: !!viewModel.restartError; text: viewModel.restartError; Layout.fillWidth: true; font.pixelSize: Theme.smallSize }
    KText { visible: !viewModel.busy && !!viewModel.result.reloadKppRequired; text: "Exit k2 and open KPP Mods from your library to apply the changes."; Layout.fillWidth: true; font.pixelSize: Theme.smallSize }
    KText { visible: !viewModel.busy && !!viewModel.result.restartUncertain; text: "Couldn’t verify which runtime packages changed. Reload the package list to check whether a restart is needed."; Layout.fillWidth: true; font.pixelSize: Theme.smallSize }
    KSurface {
        visible: viewModel.busy; Layout.fillWidth: true; implicitHeight: 56; color: Theme.wash; radius: Theme.radius
        KText { anchors.fill: parent; anchors.margins: 16; text: viewModel.loadingStatus; font.pixelSize: Theme.smallSize; elide: Text.ElideRight; maximumLineCount: 1 }
    }
    KSurface {
        visible: !viewModel.busy && !!viewModel.catalogWarning
        Layout.fillWidth: true; implicitHeight: catalogMessage.height + 32; color: Theme.wash; radius: Theme.radius
        KText { id: catalogMessage; x: 16; y: 16; width: parent.width - 32; text: "Couldn’t reload the package list.\n" + viewModel.catalogWarning; font.pixelSize: Theme.smallSize; maximumLineCount: 4; elide: Text.ElideRight }
    }
    KText { visible: !viewModel.busy && ((!!viewModel.result.restartRequired && !viewModel.result.restartAutomatic) || !!viewModel.result.restartReaderRequired); text: viewModel.result.restartReaderRequired ? "Restart your reader to apply the packages that changed." : "Exit and reopen k2 to apply the packages that changed."; font.pixelSize: Theme.smallSize; Layout.fillWidth: true }
    KSurface {
        visible: !viewModel.busy && !viewModel.failed && !!viewModel.activityApplication.name && viewModel.operation.action !== "update"
        Layout.fillWidth: true; implicitHeight: nextStep.height + 32; color: Theme.wash; radius: Theme.radius
        Column {
            id: nextStep; x: 16; y: 16; width: parent.width - 32; spacing: 12
            KText { visible: !!viewModel.activityApplication.instructions || viewModel.activityFeatures.length > 0; text: viewModel.activityFeatures.length ? "Device controls are ready to use." : viewModel.activityApplication.instructions || ""; width: parent.width; font.pixelSize: Theme.smallSize; maximumLineCount: 4; elide: Text.ElideRight }
            Repeater {
                model: viewModel.activityFeatures
                KButton { width: parent.width; text: modelData.title; symbol: "terminal"; primary: true; onClicked: viewModel.selectFeature(modelData.id) }
            }
            KButton { visible: !!viewModel.activityApplication.canOpen; text: "Open " + (viewModel.activityApplication.name || ""); enabled: viewModel.canLaunch; primary: true; width: parent.width; onClicked: viewModel.openActivityApplication() }
            KButton { text: "Package details"; onClicked: viewModel.showInstalledPackage() }
        }
    }
    RowLayout {
        Layout.fillWidth: true; spacing: 12
        KButton { visible: viewModel.failed && !viewModel.busy && viewModel.result.state !== "interrupted"; text: "Try again"; symbol: "refresh"; primary: true; onClicked: viewModel.retry() }
        KButton { visible: !!viewModel.catalogWarning && !viewModel.busy; text: "Reload package list"; onClicked: viewModel.reloadPackages() }
        KButton { text: viewModel.busy ? "Browse App Store" : "Back to App Store"; onClicked: shell.navigation.navigate("apps") }
        Item { Layout.fillWidth: true }
    }
    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.faint }
    KButton {
        Layout.fillWidth: true; flat: true; alignLeft: true
        text: activity.detailsOpen ? "Hide details" : "Show details"
        symbol: "terminal"; onClicked: activity.detailsOpen = !activity.detailsOpen
    }
    KSurface {
        visible: activity.detailsOpen
        Layout.fillHeight: true; Layout.fillWidth: true; Layout.minimumHeight: 0
        color: Theme.wash; radius: Theme.radius
        Flickable {
            id: activityScroll
            anchors.fill: parent
            contentWidth: width; contentHeight: activityLog.height + 32
            clip: true; boundsBehavior: Flickable.StopAtBounds
            flickableDirection: Flickable.VerticalFlick
            ScrollIndicator.vertical: ScrollIndicator {}
            function followOutput() {
                if (visible) contentY = Math.max(0, contentHeight - height)
            }
            onVisibleChanged: if (visible) Qt.callLater(followOutput)
            onHeightChanged: if (viewModel.busy) Qt.callLater(followOutput)
            onContentHeightChanged: Qt.callLater(followOutput)
            KText {
                id: activityLog
                x: 16; y: 16; width: Math.max(0, activityScroll.width - 32)
                text: viewModel.log; font.pixelSize: Theme.smallSize
                wrapMode: Text.WrapAnywhere
                onTextChanged: Qt.callLater(activityScroll.followOutput)
            }
        }
    }
    Item { visible: !activity.detailsOpen; Layout.fillHeight: true }
}
