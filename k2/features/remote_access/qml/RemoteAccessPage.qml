import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../../../ui/components"

ColumnLayout {
    id: page
    property var shell
    property var viewModel
    spacing: 20
    KTabBar {
        Layout.fillWidth: true
        visible: viewModel.featureOptions.length > 1
        enabled: !viewModel.featureWorking && !viewModel.featureBusy
        model: viewModel.featureOptions
        currentId: viewModel.feature.id || ""
        objectNamePrefix: "remoteTab-"
        onActivated: viewModel.selectRemoteFeature(identifier)
    }
    Component { id: screenControls; ScreenSharingControls { shell: page.shell; viewModel: page.viewModel } }
    Component { id: sshControls; SshControls { shell: page.shell; viewModel: page.viewModel } }
    Loader {
        Layout.fillWidth: true
        Layout.fillHeight: true
        sourceComponent: viewModel.screenSharing ? screenControls : sshControls
    }
}
