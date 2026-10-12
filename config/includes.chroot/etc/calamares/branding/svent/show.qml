import QtQuick 2.0
import calamares.slideshow 1.0

Presentation {
    Rectangle {
        anchors.fill: parent
        color: "#202531"
    }
    Slide {
        anchors.fill: parent
        Image {
            anchors.fill: parent
            anchors.margins: 8
            source: "file:///etc/calamares/branding/svent/installation-image.png"
            fillMode: Image.PreserveAspectFit
            smooth: true
        }
    }
}
