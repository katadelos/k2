pragma Singleton
import QtQuick 2.15
QtObject {
    property FontLoader displayFontLoader: FontLoader {
        source: Qt.resolvedUrl("../assets/fonts/KTRMNLDINMittelschrift-Regular.otf")
    }
    property FontLoader bodyFontLoader: FontLoader {
        source: Qt.resolvedUrl("../assets/fonts/NeueHaasDisplayRoman.ttf")
    }
    readonly property bool darkMode: appRuntime.appearance.paletteDarkMode
    readonly property color ink: darkMode ? "#ffffff" : "#000000"
    // Thin gray text needs more contrast on the native 600 px panels.
    readonly property color secondary: darkMode ? (panelWidth === 600 ? "#cccccc" : "#aaaaaa") : (panelWidth === 600 ? "#333333" : "#555555")
    readonly property color line: darkMode ? "#666666" : "#aaaaaa"
    readonly property color faint: darkMode ? "#333333" : "#e5e5e5"
    readonly property color paper: darkMode ? "#000000" : "#ffffff"
    readonly property color wash: darkMode ? "#151515" : "#f4f4f4"
    readonly property color primaryPressed: darkMode ? "#b7b7b7" : "#484848"
    readonly property string displayFont: displayFontLoader.name
    readonly property string bodyFont: bodyFontLoader.name
    readonly property int radius: 6
    readonly property int margin: 24
    readonly property int gap: 16
    readonly property int touchSize: 44
    // One extra pixel keeps small stems legible on an unscaled 600 px panel.
    readonly property int textSizeAdjustment: panelWidth === 600 ? 1 : 0
    readonly property int titleSize: 28
    readonly property int sectionSize: 20 + textSizeAdjustment
    readonly property int smallSize: 14 + textSizeAdjustment
    readonly property real scale: 1
    readonly property int divider: 1
    readonly property int bodySize: 17 + textSizeAdjustment
    readonly property int controlSize: 17 + textSizeAdjustment
    readonly property int headingSize: 22 + textSizeAdjustment
}
