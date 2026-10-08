import QtQuick 2.0;
import calamares.slideshow 1.0;

Presentation {
    id: presentation
    Timer { interval: 6000; running: true; repeat: true; onTriggered: presentation.goToNextSlide() }
    Slide {
        Text {
            anchors.centerIn: parent
            horizontalAlignment: Text.AlignHCenter
            text: "SventOS\nYour Debian-based pentest toolkit"
            color: "#e6edf3"
            font.pixelSize: 24
        }
    }
    Slide {
        Text {
            anchors.centerIn: parent
            horizontalAlignment: Text.AlignHCenter
            text: "Pick your desktop and tool categories.\nBurp Suite ships with the Web set."
            color: "#e6edf3"
            font.pixelSize: 22
        }
    }
}
