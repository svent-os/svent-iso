import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    color: "#202531"
    ButtonGroup {
        id: choices
        exclusive: true
    }
    ScrollView {
        anchors.fill: parent
        anchors.margins: 20
        contentWidth: availableWidth
        clip: true
        ColumnLayout {
            width: parent.width
            spacing: 18
            Text {
                Layout.fillWidth: true
                text: "Choose a bootloader"
                color: "#e5e8ee"
                font.pixelSize: 23
                font.bold: true
                wrapMode: Text.WordWrap
            }
            Text {
                Layout.fillWidth: true
                text: "GRUB is recommended for a new installation."
                color: "#bdc5d1"
                font.pixelSize: 14
                wrapMode: Text.WordWrap
            }
            Repeater {
                model: [
                    {choice: "grub", title: "GRUB Bootloader", description: "Install GRUB with the SventOS red text menu. Start SventOS directly from your disk."},
                    {choice: "none", title: "No Bootloader", description: "Keep an existing bootloader and configure it yourself. The installation will not start on its own without a working bootloader."}
                ]
                delegate: Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: card.implicitHeight + 36
                    radius: 6
                    color: "#181d25"
                    border.color: config.packageChoice === modelData.choice ? "#e6506e" : "#566173"
                    border.width: 1
                    RowLayout {
                        id: card
                        anchors.fill: parent
                        anchors.margins: 18
                        spacing: 20
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            Text {
                                Layout.fillWidth: true
                                text: modelData.title
                                color: "#ffffff"
                                font.pixelSize: 17
                                font.bold: true
                                wrapMode: Text.WordWrap
                            }
                            Text {
                                Layout.fillWidth: true
                                text: modelData.description
                                color: "#c5ccd7"
                                font.pixelSize: 14
                                wrapMode: Text.WordWrap
                            }
                        }
                        RadioButton {
                            id: option
                            objectName: modelData.choice + "Choice"
                            ButtonGroup.group: choices
                            checked: config.packageChoice === modelData.choice
                            onClicked: config.packageChoice = modelData.choice
                            Accessible.name: modelData.title
                            indicator: Rectangle {
                                implicitWidth: 44
                                implicitHeight: 24
                                y: (option.height - height) / 2
                                radius: 12
                                color: option.checked ? "#b82d50" : "#69788e"
                                border.width: option.activeFocus ? 2 : 0
                                border.color: "#ffffff"
                                Rectangle {
                                    width: 18
                                    height: 18
                                    radius: 9
                                    y: 3
                                    x: option.checked ? 23 : 3
                                    color: "#ffffff"
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
