import QtQuick 2.15
import QtQuick.Controls 2.15
AbstractButton {
    id: control
    implicitWidth: 52; implicitHeight: 44
    checkable: false
    opacity: enabled ? 1 : 0.4
    Accessible.role: Accessible.CheckBox
    Accessible.checkable: true
    Accessible.checked: checked
    background: Item {
        KSurface {
            anchors.centerIn: parent; width: 48; height: 26; radius: 13
            color: control.checked ? Theme.ink : Theme.wash
            borderColor: control.visualFocus ? Theme.ink : Theme.line
            borderWidth: control.visualFocus ? 2 : 1
            KSurface {
                x: control.checked ? 25 : 3; y: 3; width: 20; height: 20; radius: 10
                color: control.checked ? Theme.paper : Theme.secondary
            }
        }
    }
}
