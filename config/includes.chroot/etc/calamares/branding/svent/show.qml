import QtQuick 2.0
import calamares.slideshow 1.0

Presentation {
    Slide {
        Rectangle {
            anchors.fill: parent
            color: "#202531"
        }
        Image {
            anchors.fill: parent
            anchors.margins: 8
            source: "file:///etc/calamares/branding/svent/installation-image.png"
            fillMode: Image.PreserveAspectFit
            smooth: true
        }
    }
}
