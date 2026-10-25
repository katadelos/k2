import QtQuick 2.15
import QtQuick.Window 2.15
import "../components"
Window {
    id: window
    readonly property var appShell: shell
    readonly property bool splashVisible: !minimumSplashElapsed || !appShell || appShell.packages.loading || contentLoader.status !== Loader.Ready
    readonly property bool applicationLoadFailed: contentLoader.status === Loader.Error || (contentLoader.item !== null && contentLoader.item.applicationLoadFailed)
    onApplicationLoadFailedChanged: if (applicationLoadFailed && deferredStartup) appRuntime.fail_application_load()
    property bool minimumSplashElapsed: false
    property bool componentReady: false
    readonly property bool displayDark: appRuntime.appearance.paletteDarkMode
    readonly property bool displayFullscreen: appRuntime.appearance.fullScreen
    onDisplayDarkChanged: if (componentReady) appRuntime.requestDisplayCleanup(true)
    onDisplayFullscreenChanged: if (componentReady) appRuntime.requestDisplayCleanup(true)
    onSplashVisibleChanged: if (componentReady && !splashVisible) appRuntime.requestDisplayCleanup(true)
    width: panelWidth * windowScale; height: panelHeight * windowScale
    visible: true; color: Theme.paper
    title: deviceMode && deviceFamily === "kindle" ? "L:A_N:application_ID:org.k2_PC:" + (appRuntime.appearance.fullScreen ? "N" : "T") : appShell ? "k2 — " + appShell.controls.info.model + " simulator" : "k2"
    flags: deviceMode && deviceFamily === "kobo" ? Qt.Window | Qt.FramelessWindowHint : Qt.Window
    visibility: deviceMode && deviceFamily === "kobo" ? Window.FullScreen : Window.Windowed
    onClosing: {
        close.accepted = false
        if (appShell) appShell.quit()
        else Qt.quit()
    }
    function loadApplication() {
        if (appShell) contentLoader.setSource("ApplicationContent.qml", {shell: appShell})
    }
    onAppShellChanged: if (componentReady) loadApplication()
    Component.onCompleted: { componentReady = true; loadApplication() }
    Timer {
        interval: 2000
        running: firstFramePresented && !window.minimumSplashElapsed
        onTriggered: window.minimumSplashElapsed = true
    }
    Loader {
        id: contentLoader
        anchors.fill: parent
        asynchronous: deferredStartup
        visible: !window.splashVisible
        enabled: visible
    }
    Rectangle {
        visible: window.splashVisible
        color: Theme.paper
        width: 600; height: window.height / (window.width / 600)
        scale: window.width / 600; transformOrigin: Item.TopLeft
        layer.enabled: offscreenPreview
        layer.smooth: true
        layer.textureSize: Qt.size(panelWidth, Math.round(height * panelWidth / width))
        SplashPage {
            anchors.fill: parent
            statusText: !window.appShell ? "Starting k2…" : window.appShell.packages.loading ? window.appShell.packages.loadingStatus + "…" : "Ready"
            progress: !window.appShell ? 0 : window.appShell.packages.loading ? window.appShell.packages.loadingProgress : 1
        }
    }
}
