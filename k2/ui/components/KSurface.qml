import QtQuick 2.15

// Qt's software Rectangle renderer caches rounded corners before item scaling.
// Draw the complete outline at panel resolution to keep corners and edges joined.
Item {
    id: surface
    property color color: "transparent"
    property real radius: 0
    property color borderColor: "transparent"
    property real borderWidth: 1
    onColorChanged: drawing.requestPaint()
    onRadiusChanged: drawing.requestPaint()
    onBorderColorChanged: drawing.requestPaint()
    onBorderWidthChanged: drawing.requestPaint()
    Canvas {
        id: drawing
        property real density: Math.max(1, panelWidth / 600)
        width: surface.width * density; height: surface.height * density
        scale: 1 / density; transformOrigin: Item.TopLeft
        // A surface can finish sizing while its dialog is hidden.
        onVisibleChanged: if (visible) requestPaint()
        onAvailableChanged: if (available) requestPaint()
        onDensityChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var c = getContext("2d")
            c.reset(); c.scale(density, density)
            var outlineWidth = surface.borderColor.a > 0 ? surface.borderWidth : 0
            var inset = outlineWidth / 2
            var left = inset, top = inset
            var right = surface.width - inset, bottom = surface.height - inset
            var r = Math.max(0, Math.min(surface.radius - inset, (right-left)/2, (bottom-top)/2))
            var arc = r * 0.55228475
            c.beginPath()
            c.moveTo(left+r, top); c.lineTo(right-r, top)
            c.bezierCurveTo(right-r+arc, top, right, top+r-arc, right, top+r)
            c.lineTo(right, bottom-r); c.bezierCurveTo(right, bottom-r+arc, right-r+arc, bottom, right-r, bottom)
            c.lineTo(left+r, bottom); c.bezierCurveTo(left+r-arc, bottom, left, bottom-r+arc, left, bottom-r)
            c.lineTo(left, top+r); c.bezierCurveTo(left, top+r-arc, left+r-arc, top, left+r, top)
            c.closePath()
            c.fillStyle = surface.color; c.fill()
            if (outlineWidth > 0) {
                c.lineWidth = outlineWidth
                c.strokeStyle = surface.borderColor; c.stroke()
            }
        }
    }
}
