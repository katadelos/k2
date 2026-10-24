import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../../ui/components"

Item {
    id: page
    property var shell
    property var viewModel
    property bool booksOnly: false
    property string editor: ""
    property bool keyboardOpen: false
    readonly property bool choosingFolder: !!viewModel.transfer.action
    readonly property bool gridView: viewModel.gridView
    readonly property var rows: viewModel.entries.filter(function(row) {
        return choosingFolder || !booksOnly || row.directory || row.kind === "Book"
    })
    readonly property Component headerActions: Component {
        Row {
            spacing: 8
            KButton {
                width: 44; height: 44; symbol: "folder-add"; flat: true
                visible: !page.editor
                enabled: viewModel.canChange && !actions.visible && !options.visible
                Accessible.name: "New folder"
                onClicked: page.editName("mkdir")
            }
        }
    }

    function closeMenu() {
        actions.visible = false
        if (!editor && !shell.confirmations.active) viewModel.clearSelection()
    }

    function showActions(path, item) {
        if (choosingFolder || viewModel.busy) return
        viewModel.select(path)
        var point = item.mapToItem(page, item.width, item.height)
        actions.menuX = Math.max(0, Math.min(page.width - actions.menuWidth, point.x - actions.menuWidth))
        actions.anchorY = point.y
        actions.visible = true
    }

    function dismissKeyboard() {
        if (actions.visible) { closeMenu(); return true }
        if (options.visible) { options.visible = false; return true }
        if (keyboardOpen) {
            keyboardOpen = false
            nameField.focus = false
            return true
        }
        if (editor) { editor = ""; viewModel.clearSelection(); return true }
        if (choosingFolder) { viewModel.cancelTransfer(); return true }
        if (viewModel.currentPath) { viewModel.up(); return true }
        return false
    }

    function editName(action) {
        editor = action
        nameField.text = action === "rename" ? viewModel.selected.name : ""
        nameField.forceActiveFocus()
        if (action === "rename") {
            var dot = viewModel.selected.directory ? -1 : nameField.text.lastIndexOf(".")
            nameField.select(0, dot > 0 ? dot : nameField.text.length)
        }
    }

    function dismissKeyboardAt(x, y) {
        if (!keyboardOpen) return
        var keyboardPoint = keyboard.mapFromItem(page, x, y)
        var fieldPoint = nameBox.mapFromItem(page, x, y)
        if (!(keyboardPoint.x >= 0 && keyboardPoint.x < keyboard.width
                && keyboardPoint.y >= 0 && keyboardPoint.y < keyboard.height)
                && !(fieldPoint.x >= 0 && fieldPoint.x < nameBox.width
                && fieldPoint.y >= 0 && fieldPoint.y < nameBox.height)) {
            keyboardOpen = false
            nameField.focus = false
        }
    }

    function submitName() {
        if (!nameField.text || !viewModel.canChange) return
        keyboardOpen = false
        nameField.focus = false
        if (editor === "rename") viewModel.renameSelected(nameField.text)
        else viewModel.newFolder(nameField.text)
        editor = ""
    }

    ColumnLayout {
        anchors.fill: parent; spacing: 12
        enabled: !actions.visible && !options.visible
        RowLayout {
            visible: !page.editor
            Layout.fillWidth: true; spacing: 8
            Flickable {
                id: breadcrumbs
                Layout.fillWidth: true; Layout.preferredHeight: Theme.touchSize
                contentWidth: pathRow.width; clip: true; boundsBehavior: Flickable.StopAtBounds
                onContentWidthChanged: contentX = Math.max(0, contentWidth - width)
                Row {
                    id: pathRow; height: parent.height
                    Repeater {
                        model: viewModel.breadcrumbs
                        Row {
                            height: pathRow.height
                            KIcon { visible: index > 0; name: "arrow"; width: visible ? 16 : 0; height: 16; anchors.verticalCenter: parent.verticalCenter; ink: Theme.secondary }
                            KButton {
                                text: modelData.name; flat: true; enabled: !viewModel.busy
                                width: Math.min(implicitWidth, breadcrumbs.width * 0.75)
                                onClicked: viewModel.openFolder(modelData.path)
                            }
                        }
                    }
                }
            }
            KButton {
                symbol: page.gridView ? "list" : "grid"; flat: true
                Accessible.name: page.gridView ? "List view" : "Grid view"
                onClicked: viewModel.setGridView(!page.gridView)
            }
            KButton {
                id: optionsButton; symbol: "more"; flat: true
                Accessible.name: "Folder options"
                onClicked: {
                    options.menuY = mapToItem(page, 0, height).y + 4
                    options.visible = true
                }
            }
        }

        KText {
            visible: !!viewModel.error || !!viewModel.message || viewModel.busy
            Layout.fillWidth: true; font.pixelSize: Theme.smallSize
            text: viewModel.busy ? viewModel.activity : viewModel.error || viewModel.message
            color: viewModel.error ? Theme.ink : Theme.secondary
        }

        ColumnLayout {
            visible: !!page.editor
            Layout.fillWidth: true; spacing: 12
            RowLayout {
                Layout.fillWidth: true
                KText { text: page.editor === "rename" ? "Rename" : "New folder"; heading: true; font.pixelSize: Theme.headingSize; Layout.fillWidth: true }
                KButton {
                    symbol: "close"; flat: true; Accessible.name: "Cancel name change"
                    onClicked: { page.keyboardOpen = false; nameField.focus = false; page.editor = ""; viewModel.clearSelection() }
                }
            }
            KSurface {
                id: nameBox
                Layout.fillWidth: true; implicitHeight: 52
                borderColor: nameField.activeFocus ? Theme.ink : Theme.line; radius: Theme.radius
                TextField {
                    id: nameField; anchors.fill: parent; padding: 12
                    placeholderText: "Folder name"; background: Item {}
                    font.family: Theme.bodyFont; font.pixelSize: Theme.bodySize; color: Theme.ink
                    selectByMouse: true
                    inputMethodHints: Qt.ImhNoAutoUppercase | Qt.ImhNoPredictiveText
                    onActiveFocusChanged: if (activeFocus) page.keyboardOpen = true
                    onAccepted: page.submitName()
                    Accessible.name: page.editor === "rename" ? "New file name" : "Folder name"
                }
            }
            KText {
                visible: page.editor === "rename" && !viewModel.selected.directory
                text: "Keep the file extension so your reader recognises the format."
                Layout.fillWidth: true; font.pixelSize: Theme.smallSize; color: Theme.secondary
            }
            KButton {
                Layout.fillWidth: true; primary: true
                text: page.editor === "rename" ? "Save name" : "Create folder"
                enabled: !!nameField.text && viewModel.canChange
                onClicked: page.submitName()
            }
        }

        GridView {
            id: fileList
            visible: !page.editor
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 0
            model: page.rows
            cellWidth: page.gridView ? width / 2 : width
            cellHeight: page.gridView ? 154 : 86
            clip: true; boundsBehavior: Flickable.StopAtBounds
            ScrollIndicator.vertical: ScrollIndicator {}
            delegate: Item {
                id: row
                width: fileList.cellWidth; height: fileList.cellHeight
                readonly property bool selected: actions.visible && viewModel.selected.path === modelData.path
                KButton {
                    id: entry
                    property bool held: false
                    anchors.fill: parent
                    anchors.rightMargin: page.gridView ? (index % 2 === 0 ? 8 : 0) : 0
                    anchors.leftMargin: page.gridView && index % 2 !== 0 ? 8 : 0
                    anchors.bottomMargin: page.gridView ? 16 : 0
                    padding: 0; enabled: !viewModel.busy
                    onPressed: held = false
                    onPressAndHold: { held = true; page.showActions(modelData.path, entry) }
                    onClicked: {
                        if (held) return
                        if (modelData.directory && !modelData.protected) viewModel.openFolder(modelData.path)
                        else page.showActions(modelData.path, entry)
                    }
                    Accessible.name: modelData.name + ", " + modelData.detail
                    background: KSurface {
                        color: entry.down ? Theme.ink : modelData.directory && page.gridView ? Theme.wash : Theme.paper
                        radius: page.gridView ? 10 : 0
                        borderColor: row.selected ? Theme.ink : page.gridView ? Theme.faint : "transparent"
                        borderWidth: row.selected ? 2 : 1
                    }
                    contentItem: Item {
                        KIcon {
                            name: modelData.icon; x: page.gridView ? 18 : 6
                            y: page.gridView ? 16 : (parent.height - height) / 2
                            width: page.gridView ? 30 : 28; height: width
                            ink: entry.down ? Theme.paper : Theme.ink
                        }
                        Column {
                            x: page.gridView ? 18 : 54
                            y: page.gridView ? 59 : (parent.height - height) / 2
                            width: parent.width - x - (page.gridView ? 16 : 48); spacing: 6
                            KText {
                                width: parent.width; text: modelData.name; heading: true
                                font.pixelSize: Theme.bodySize
                                maximumLineCount: page.gridView ? 2 : 1; elide: Text.ElideMiddle
                                color: entry.down ? Theme.paper : Theme.ink
                            }
                            KText {
                                width: parent.width
                                text: modelData.directory ? modelData.kind : (modelData.extension || modelData.kind) + (modelData.size ? " · " + modelData.size : "")
                                font.pixelSize: Theme.smallSize; maximumLineCount: 1; elide: Text.ElideRight
                                color: entry.down ? Theme.paper : Theme.secondary
                            }
                        }
                    }
                }
                KButton {
                    visible: !page.choosingFolder
                    anchors.right: entry.right; anchors.rightMargin: page.gridView ? 6 : 0
                    y: page.gridView ? 6 : (parent.height - height) / 2
                    width: 44; height: 44; symbol: "more"; flat: true
                    enabled: !viewModel.busy
                    background: KSurface { color: parent.down ? Theme.ink : "transparent"; radius: Theme.radius }
                    Accessible.name: "Options for " + modelData.name
                    onClicked: page.showActions(modelData.path, entry)
                }
                Rectangle { visible: !page.gridView; anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.faint }
            }
            footer: Column {
                visible: page.rows.length === 0 && !viewModel.busy
                width: fileList.width; spacing: 12
                Item { width: 1; height: 20 }
                KIcon { name: page.booksOnly ? "book" : "folder"; width: 36; height: 36; ink: Theme.secondary; anchors.horizontalCenter: parent.horizontalCenter }
                KText { width: parent.width; heading: true; horizontalAlignment: Text.AlignHCenter; text: page.choosingFolder ? "No subfolders" : page.booksOnly ? "No books here" : "An empty folder" }
                KText {
                    width: parent.width; color: Theme.secondary; horizontalAlignment: Text.AlignHCenter
                    text: page.choosingFolder ? "Choose this folder, or go up to another location." : page.booksOnly ? "Turn off Show books only in the three-dot menu to see all files." : "Add your files here, or create a folder to organise them."
                }
            }
        }

        KSurface {
            visible: page.choosingFolder && !page.editor
            Layout.fillWidth: true; implicitHeight: transferContents.implicitHeight + 28
            color: Theme.wash; radius: 10
            ColumnLayout {
                id: transferContents; anchors.fill: parent; anchors.margins: 14; spacing: 12
                KText {
                    Layout.fillWidth: true; heading: true; maximumLineCount: 2; elide: Text.ElideMiddle
                    text: (viewModel.transfer.action === "copy" ? "Copy “" : "Move “") + (viewModel.transfer.record ? viewModel.transfer.record.name : "") + "” here?"
                }
                RowLayout {
                    Layout.fillWidth: true; spacing: 12
                    KButton { text: "Cancel"; Layout.fillWidth: true; enabled: !viewModel.busy; onClicked: viewModel.cancelTransfer() }
                    KButton {
                        text: viewModel.transfer.action === "copy" ? "Copy here" : "Move here"
                        primary: true; Layout.fillWidth: true
                        enabled: viewModel.canChange && viewModel.currentPath !== viewModel.transfer.origin
                        onClicked: viewModel.completeTransfer()
                    }
                }
            }
        }

        Item { visible: !!page.editor; Layout.fillHeight: true; Layout.minimumHeight: 0 }
        OnScreenKeyboard {
            id: keyboard; visible: page.keyboardOpen
            Layout.fillWidth: true; Layout.preferredHeight: 258
            Layout.leftMargin: -24; Layout.rightMargin: -24; Layout.bottomMargin: -24
            submitLabel: "Done"; target: nameField
            onSubmitRequested: page.submitName()
        }
    }

    Item {
        id: options; visible: false; anchors.fill: parent; z: 2
        property real menuY: 0
        MouseArea { anchors.fill: parent; onClicked: options.visible = false }
        KSurface {
            anchors.right: parent.right; y: Math.min(options.menuY, parent.height - height)
            width: 264; height: optionsContents.height + 16
            color: Theme.paper; borderColor: Theme.ink; radius: 10
            MouseArea { anchors.fill: parent }
            Column {
                id: optionsContents; x: 8; y: 8; width: parent.width - 16; spacing: 4
                KButton {
                    visible: !page.choosingFolder
                    text: "Show books only"; symbol: page.booksOnly ? "check" : "book"
                    width: parent.width; flat: true; alignLeft: true; enabled: !viewModel.busy
                    Accessible.checkable: true; Accessible.checked: page.booksOnly
                    onClicked: { page.booksOnly = !page.booksOnly; options.visible = false }
                }
                KButton {
                    text: viewModel.showHidden ? "Hide hidden files" : "Show hidden files"; symbol: viewModel.showHidden ? "check" : "folder"
                    width: parent.width; flat: true; alignLeft: true; enabled: !viewModel.busy
                    onClicked: { viewModel.setShowHidden(!viewModel.showHidden); options.visible = false }
                }
                KButton {
                    text: "Refresh folder"; symbol: "refresh"; width: parent.width; flat: true; alignLeft: true; enabled: !viewModel.busy
                    onClicked: { viewModel.refresh(); options.visible = false }
                }
            }
        }
    }

    Item {
        id: actions; visible: false; anchors.fill: parent; z: 3
        property real menuX: 0
        property real anchorY: 0
        readonly property real menuWidth: Math.min(page.width, 310)
        MouseArea { anchors.fill: parent; onClicked: page.closeMenu() }
        KSurface {
            x: actions.menuX; y: Math.max(0, Math.min(actions.anchorY + 4, page.height - height))
            width: actions.menuWidth; height: Math.min(actionContents.height + 32, page.height)
            color: Theme.paper; borderColor: Theme.ink; radius: 10
            MouseArea { anchors.fill: parent }
            Flickable {
                anchors.fill: parent; anchors.margins: 16
                contentHeight: actionContents.height; clip: true; boundsBehavior: Flickable.StopAtBounds
                ScrollIndicator.vertical: ScrollIndicator {}
                Column {
                    id: actionContents; width: parent.width; spacing: 6
                    KText { text: viewModel.selected.name || ""; width: parent.width; heading: true; font.pixelSize: Theme.headingSize; maximumLineCount: 2; elide: Text.ElideMiddle }
                    KText {
                        text: (viewModel.selected.detail || "") + (viewModel.selected.modified ? " · " + viewModel.selected.modified : "")
                        width: parent.width; font.pixelSize: Theme.smallSize; color: Theme.secondary
                    }
                    Item { width: 1; height: 6 }
                    Rectangle { width: parent.width; height: 1; color: Theme.faint }
                    KButton {
                        visible: !!viewModel.selected.directory && !viewModel.selected.protected
                        text: "Open folder"; symbol: "folder"; flat: true; alignLeft: true; width: parent.width
                        onClicked: { viewModel.openFolder(viewModel.selected.path); page.closeMenu() }
                    }
                    KButton {
                        visible: !!viewModel.selected.mutable; text: "Move"; symbol: "move"; flat: true; alignLeft: true; width: parent.width; enabled: viewModel.canChange
                        onClicked: { viewModel.beginTransfer("move"); page.closeMenu() }
                    }
                    KButton {
                        visible: !!viewModel.selected.mutable; text: "Copy"; symbol: "copy"; flat: true; alignLeft: true; width: parent.width; enabled: viewModel.canChange
                        onClicked: { viewModel.beginTransfer("copy"); page.closeMenu() }
                    }
                    KButton {
                        visible: !!viewModel.selected.mutable; text: "Rename"; symbol: "edit"; flat: true; alignLeft: true; width: parent.width; enabled: viewModel.canChange
                        onClicked: { page.editName("rename"); page.closeMenu() }
                    }
                    KButton {
                        visible: !!viewModel.selected.mutable; text: "Delete"; symbol: "trash"; flat: true; alignLeft: true; width: parent.width; enabled: viewModel.canChange
                        onClicked: { viewModel.requestDelete(); page.closeMenu() }
                    }
                    KText { visible: !!viewModel.selected.link; text: "Only the link is changed; its target is kept."; width: parent.width; color: Theme.secondary; font.pixelSize: Theme.smallSize }
                }
            }
        }
    }
}
