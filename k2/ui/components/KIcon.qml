import QtQuick 2.15
Item {
    id: icon
    property string name: "apps"
    property color ink: Theme.ink
    implicitWidth: 24
    implicitHeight: 24
    readonly property var geometry: paths(name)
    readonly property real strokeWidth: panelWidth === 600 ? 2.25 : 1.65

    // Images participate in software-renderer clipping and damage tracking
    // without a live Shape render node or an offscreen scene layer.
    Image {
        anchors.fill: parent
        sourceSize: Qt.size(Math.ceil(icon.width * panelWidth / 600), Math.ceil(icon.height * panelWidth / 600))
        asynchronous: false
        // The SVG already supplies antialiased pixels at the panel resolution.
        smooth: panelWidth !== 600 || windowScale !== 1
        opacity: icon.ink.a
        readonly property string paint: Qt.rgba(icon.ink.r, icon.ink.g, icon.ink.b, 1).toString()
        source: "data:image/svg+xml;utf8," + encodeURIComponent(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            + '<path d="' + icon.geometry.stroke + '" fill="none" stroke="' + paint
            + '" stroke-width="' + icon.strokeWidth + '" stroke-linecap="round" stroke-linejoin="round"/>'
            + '<path d="' + icon.geometry.fill + '" fill="' + paint + '"/></svg>')
    }

    function paths(name) {
        var outlines = [], fills = [], current = ""
        function beginPath() { current = "" }
        function moveTo(x, y) { current += "M" + x + "," + y + " " }
        function lineTo(x, y) { current += "L" + x + "," + y + " " }
        function curveTo(x1, y1, x2, y2, x, y) {
            current += "C" + x1 + "," + y1 + " " + x2 + "," + y2 + " " + x + "," + y + " "
        }
        function closePath() { current += "Z " }
        function stroke() { outlines.push(current) }
        function line(points) {
            beginPath(); moveTo(points[0], points[1])
            for (var i = 2; i < points.length; i += 2) lineTo(points[i], points[i + 1])
            stroke()
        }
        function circle(x, y, r) {
            outlines.push("M" + (x + r) + "," + y + " a" + r + "," + r + " 0 1,0 " + (-2*r) + ",0 a" + r + "," + r + " 0 1,0 " + (2*r) + ",0")
        }
        function rectangle(x, y, w, h) {
            return "M" + x + "," + y + " h" + w + " v" + h + " h" + (-w) + " Z"
        }
        function strokeRect(x, y, w, h) { outlines.push(rectangle(x, y, w, h)) }
        function fillRect(x, y, w, h) { fills.push(rectangle(x, y, w, h)) }
        function arc(x, y, r, start, end, anticlockwise) {
            var span = end - start
            if (anticlockwise && span > 0) span -= 2 * Math.PI
            else if (!anticlockwise && span < 0) span += 2 * Math.PI
            var sx = x + r * Math.cos(start), sy = y + r * Math.sin(start)
            if (current) lineTo(sx, sy); else moveTo(sx, sy)
            current += "A" + r + "," + r + " 0 " + (Math.abs(span) > Math.PI ? 1 : 0) + "," + (anticlockwise ? 0 : 1) + " " + (x + r * Math.cos(end)) + "," + (y + r * Math.sin(end)) + " "
        }
        if (name === "home") {
            line([2,11,12,2,22,11]);line([5,9,5,22,10,22,10,15,14,15,14,22,19,22,19,9])
        } else if (name === "apps") {
            line([12,2.5,21,7.5,21,17,12,22,3,17,3,7.5,12,2.5])
            line([3,7.5,12,12.5,21,7.5]);line([12,12.5,12,22]);line([7.5,5,16.5,10])
        } else if (name === "book") {
            line([12,5,8,3,2,3,2,20,8,20,12,22,16,20,22,20,22,3,16,3,12,5,12,22])
        } else if (name === "plugin") {
            line([3,9,8,9,8,6]); beginPath(); arc(11,6,3,Math.PI,0); stroke()
            line([14,6,14,9,21,9,21,14,18,14]); beginPath(); arc(18,17,3,-Math.PI/2,Math.PI/2,true); stroke()
            line([18,20,21,20,21,22,3,22,3,9])
        } else if (name === "fullscreen") {
            line([3,9,3,3,9,3]);line([15,3,21,3,21,9])
            line([21,15,21,21,15,21]);line([9,21,3,21,3,15])
        } else if (name === "device") {
            strokeRect(5,2,14,20);line([9,18.5,15,18.5])
        } else if (name === "usb") {
            line([12,18,12,3]);line([9,6,12,3,15,6]);circle(12,20,2)
            line([12,15,6,12,6,8]);circle(6,6,1.5)
            line([12,12,18,9,18,6]);strokeRect(16.5,3,3,3)
        } else if (name === "folder") {
            line([2,6,9,6,11,8,22,8,22,20,2,20,2,6]);line([2,6,2,4,9,4,11,6])
        } else if (name === "folder-add") {
            line([2,6,9,6,11,8,22,8,22,20,2,20,2,6]);line([2,6,2,4,9,4,11,6])
            line([12,11,12,17]);line([9,14,15,14])
        } else if (name === "file") {
            line([5,2,14,2,20,8,20,22,5,22,5,2]);line([14,2,14,8,20,8])
            line([8,13,17,13]);line([8,17,15,17])
        } else if (name === "more") {
            circle(5,12,1);circle(12,12,1);circle(19,12,1)
        } else if (name === "plus") {
            line([12,4,12,20]);line([4,12,20,12])
        } else if (name === "copy") {
            strokeRect(8,8,13,13);line([16,8,16,3,3,3,3,16,8,16])
        } else if (name === "move") {
            line([3,12,21,12]);line([16,7,21,12,16,17])
        } else if (name === "edit") {
            line([4,16,16,4,20,8,8,20,3,21,4,16]);line([13,7,17,11])
        } else if (name === "grid") {
            strokeRect(3,3,7,7);strokeRect(14,3,7,7)
            strokeRect(3,14,7,7);strokeRect(14,14,7,7)
        } else if (name === "list") {
            for(var row=5;row<=19;row+=7) {
                strokeRect(3,row-1.5,3,3);line([10,row,21,row])
            }
        } else if (name === "info") {
            circle(12,12,9);line([12,11,12,17]);circle(12,7.4,0.45)
        } else if (name === "arrow") {
            line([9,5,16,12,9,19])
        } else if (name === "back") {
            line([14,5,7,12,14,19])
        } else if (name === "shift") {
            line([12,3,3,12,8,12,8,21,16,21,16,12,21,12,12,3])
        } else if (name === "backspace") {
            line([8,5,22,5,22,19,8,19,1,12,8,5]);line([12,9,18,15]);line([18,9,12,15])
        } else if (name === "search") {
            circle(10,10,6.5);line([15,15,21,21])
        } else if (name === "refresh") {
            beginPath(); arc(12,12,9,0,Math.PI*1.5)
            curveTo(14.5,3,16.9,4,18.7,5.8)
            lineTo(21,8); stroke()
            line([21,3,21,8,16,8])
        } else if (name === "download") {
            line([12,2,12,15]);line([7,10,12,15,17,10]);line([3,16,3,21,21,21,21,16])
        } else if (name === "exit") {
            line([10,3,3,3,3,21,10,21]);line([10,12,22,12]);line([17,7,22,12,17,17])
        } else if (name === "check") {
            line([4,12,9,17,20,6])
        } else if (name === "close") {
            line([6,6,18,18]);line([18,6,6,18])
        } else if (name === "battery") {
            strokeRect(2,6,17,12);fillRect(4.5,8.5,10.5,7);line([22,10,22,14])
        } else if (name === "terminal") {
            strokeRect(2,4,20,16);line([6,8,10,12,6,16]);line([13,16,18,16])
        } else if (name === "trash") {
            line([3,6,21,6]);line([9,6,9,3,15,3,15,6]);line([5,6,6,21,18,21,19,6]);line([10,10,10,17]);line([14,10,14,17])
        } else if (name === "storage") {
            line([5,3,19,3,22,14,22,21,2,21,2,14,5,3]);line([2,14,22,14]);circle(18,17.5,0.5)
        } else if (name === "settings") {
            circle(12,12,3)
            beginPath()
            for(var tooth=0;tooth<32;tooth++) {
                var angle = (tooth - 0.5) * Math.PI / 16
                var radius = tooth % 4 < 2 ? 10 : 8
                var x = 12 + Math.cos(angle) * radius, y = 12 + Math.sin(angle) * radius
                if(tooth === 0)moveTo(x,y); else lineTo(x,y)
            }
            closePath(); stroke()
        } else if (name === "wifi") {
            for (var r = 6; r <= 14; r += 4) {
                beginPath(); arc(12, 19, r, -Math.PI * 0.75, -Math.PI * 0.25); stroke()
            }
            circle(12,19,0.7)
        } else if (name === "moon") {
            outlines.push("M21,13 A9,9 0 1,1 11,3 A7,7 0 0,0 21,13 Z")
        } else if (name === "brightness") {
            circle(12,12,4)
            for(var ray=0;ray<8;ray++) {
                var a = ray * Math.PI / 4
                line([12+Math.cos(a)*7,12+Math.sin(a)*7,12+Math.cos(a)*10,12+Math.sin(a)*10])
            }
        }
        return {stroke: outlines.join(" "), fill: fills.join(" ")}
    }
}
