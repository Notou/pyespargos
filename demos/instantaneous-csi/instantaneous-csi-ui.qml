import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtCharts

ApplicationWindow {
	id: window
	visible: true
	minimumWidth: 800
	minimumHeight: 500

	color: "#333333"
	title: "Instantaneous CSI"

	// Tab20 color cycle reordered: https://github.com/matplotlib/matplotlib/blob/main/lib/matplotlib/_cm.py#L1293
	property var colorCycle: ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf", "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5", "#c49c94", "#f7b6d2", "#c7c7c7", "#dbdb8d", "#9edae5"]

	ColumnLayout {
		height: parent.height
		width: parent.width

		Text {
			Layout.alignment: Qt.AlignCenter
			font.pixelSize: Math.max(24, window.width / 70)
			text: "Instantaneous CSI: " + (backend.timeDomain ? "Time Domain" : (backend.superResolution ? "Superresolution Time Domain" : "Frequency Domain"))
			color: "#ffffff"
			Layout.margins: 10
		}

		ChartView {
			id: csiAmplitude
			Layout.alignment: Qt.AlignTop
			legend.visible: false
			legend.labelColor: "#e0e0e0"
			Layout.fillWidth: true
			Layout.fillHeight: true
			antialiasing: true
			backgroundColor: "#202020"
			dropShadowEnabled: true

			axes: [
				ValueAxis {
					id: csiAmplitudeSubcarrierAxis

					min: (backend.timeDomain || backend.superResolution) ? -7 : backend.subcarrierRange[0]
					max: (backend.timeDomain || backend.superResolution) ? 7 : backend.subcarrierRange.slice(-1)[0]
					titleText: (backend.timeDomain || backend.superResolution) ? "<font color=\"#e0e0e0\">Delay [tap]</font>" : "<font color=\"#e0e0e0\">Subcarrier Index</font>"
					titleFont.bold: false
					gridLineColor: "#c0c0c0"
					tickInterval: (backend.timeDomain || backend.superResolution) ? 5 : 30
					tickType: ValueAxis.TicksDynamic
					labelsColor: "#e0e0e0"
				},
				ValueAxis {
					id: csiAmplitudeAxis

					min: 0
					max: 1
					titleText: (backend.timeDomain || backend.superResolution) ? "<font color=\"#e0e0e0\">Power [linear]</font>" : "<font color=\"#e0e0e0\">Power [dB]</font>"
					titleFont.bold: false
					gridLineColor: "#c0c0c0"
					tickInterval: backend.timeDomain ? 2000 : (backend.superResolution ? 0.5 : 5)
					tickType: ValueAxis.TicksDynamic
					labelsColor: "#e0e0e0"
				}
			]

			Component.onCompleted : {
				for (let ant = 0; ant < backend.sensorCount; ++ant) {
					let series = csiAmplitude.createSeries(ChartView.SeriesTypeLine, "tx-" + ant, csiAmplitudeSubcarrierAxis, csiAmplitudeAxis)
					series.pointsVisible = false
					series.color = colorCycle[ant % colorCycle.length]
					series.useOpenGL = true

					for (const s of backend.subcarrierRange) {
						series.append(s, 0)
					}
				}
			}
		}

		ChartView {
			id: csiPhase
			Layout.alignment: Qt.AlignTop
			legend.visible: false
			legend.labelColor: "#e0e0e0"
			Layout.fillWidth: true
			Layout.fillHeight: true
			antialiasing: true
			backgroundColor: "#202020"
			dropShadowEnabled: true
			visible: !backend.superResolution

			axes: [
				ValueAxis {
					id: csiPhaseSubcarrierAxis

					min: (backend.timeDomain || backend.superResolution) ? -7 : backend.subcarrierRange[0]
					max: (backend.timeDomain || backend.superResolution) ? 7 : backend.subcarrierRange.slice(-1)[0]
					titleText: (backend.timeDomain || backend.superResolution) ? "<font color=\"#e0e0e0\">Delay [tap]</font>" : "<font color=\"#e0e0e0\">Subcarrier Index</font>"
					titleFont.bold: false
					gridLineColor: "#c0c0c0"
					tickInterval: (backend.timeDomain || backend.superResolution) ? 5 : 30
					tickType: ValueAxis.TicksDynamic
					labelsColor: "#e0e0e0"
				},
				ValueAxis {
					id: csiPhaseAxis

					min: -3.14
					max: 3.14
					titleText: "<font color=\"#e0e0e0\">Phase [rad]</font>"
					titleFont.bold: false
					gridLineColor: "#c0c0c0"
					tickInterval: 2
					tickType: ValueAxis.TicksDynamic
					labelsColor: "#e0e0e0"
				}
			]

			Component.onCompleted : {
				for (let ant = 0; ant < backend.sensorCount; ++ant) {
					let series = csiPhase.createSeries(ChartView.SeriesTypeLine, "tx-" + ant, csiPhaseSubcarrierAxis, csiPhaseAxis)
					series.pointsVisible = false
					series.color = colorCycle[ant % colorCycle.length]
					series.useOpenGL = true

					for (const s of backend.subcarrierRange) {
						series.append(s, 0)
					}
				}
			}
		}
	}

	Timer {
		interval: (backend.superResolution ? 1 / 30 : 1 / 60) * 1000
		running: true
		repeat: true
		onTriggered: {
			let amplitudeSeries = [];
			let phaseSeries = [];
			for (let i = 0; i < backend.sensorCount; ++i) {
				amplitudeSeries.push(csiAmplitude.series(i));
				phaseSeries.push(csiPhase.series(i));
			}

			backend.updateCSI(amplitudeSeries, phaseSeries, csiAmplitudeAxis)
		}
	}
}