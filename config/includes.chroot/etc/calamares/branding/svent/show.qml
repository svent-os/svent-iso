import QtQuick 2.0
import calamares.slideshow 1.0

Presentation {
    id: presentation
    Timer { interval: 8000; running: true; repeat: true; onTriggered: presentation.goToNextSlide() }
    Slide {
        Rectangle { anchors.fill: parent; color: "#202531" }
        Column {
            anchors.centerIn: parent
            spacing: 20
            Image { source: "file:///usr/share/svent/logo/logo.png"; width: 80; height: 80; fillMode: Image.PreserveAspectFit; anchors.horizontalCenter: parent.horizontalCenter }
            Text { text: "Your system. Your workspace."; color: "#ffffff"; font.pixelSize: 26; anchors.horizontalCenter: parent.horizontalCenter }
            Text { text: "SventOS brings a complete, personalized XFCE desktop."; color: "#b9c1d0"; font.pixelSize: 16; anchors.horizontalCenter: parent.horizontalCenter }
        }
    }
    Slide {
        Rectangle { anchors.fill: parent; color: "#202531" }
        Column {
            anchors.centerIn: parent
            spacing: 20
            Text { text: "Ready for everyday work"; color: "#ffffff"; font.pixelSize: 26; anchors.horizontalCenter: parent.horizontalCenter }
            Text { text: "LibreOffice, Firefox, VLC and GIMP.\nA complete workspace in your language."; color: "#b9c1d0"; font.pixelSize: 18; horizontalAlignment: Text.AlignHCenter; anchors.horizontalCenter: parent.horizontalCenter }
            Text { text: "The desktop installs directly from this ISO, even offline."; color: "#ee5476"; font.pixelSize: 16; anchors.horizontalCenter: parent.horizontalCenter }
        }
    }
}
