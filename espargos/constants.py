#!/usr/bin/env python3

ANTENNAS_PER_ROW = 4
"Number of antennas per row / per SPI controller on the board"

ROWS_PER_BOARD = 2
"Number of rows / SPI controllers on the board"

SPEED_OF_LIGHT = 299792458
"Speed of light in a vacuum"

ANTENNAS_PER_BOARD = ANTENNAS_PER_ROW * ROWS_PER_BOARD
"Number of antennas on one board"

ANTENNA_SEPARATION = 0.06
"Distance between the centers of two antennas [m]"

CALIB_TRACE_LENGTH = [
	[0.0708462, 0.0229349, 0.0786856, 0.1423600],
	[0.0838888, 0.0295291, 0.0671322, 0.1308537]
]
"Calibration signal trace lengths on ESPARGOS PCB"

#CALIB_TRACE_EMPIRICAL_ERROR = [
#	[0.0005, 0.0057, 0.0000, 0.0058],
#	[0.0093, 0.0117, 0.0073, 0.0097]
#]

CALIB_TRACE_DIELECTRIC_CONSTANT = 4.3
"Dielectric constant of the sensor PCB material"

CALIB_TRACE_WIDTH = 0.2
"Width of the calibration signal trace, in m"

CALIB_TRACE_HEIGHT = 0.119
"Height of the calibration signal trace (distance between GND plane and microstrip), in m"

CALIB_TRACE_EFFECTIVE_DIELECTRIC_CONSTANT: float = (CALIB_TRACE_DIELECTRIC_CONSTANT + 1) / 2 + (CALIB_TRACE_DIELECTRIC_CONSTANT - 1) / 2 * (1 + 12 * (CALIB_TRACE_HEIGHT/CALIB_TRACE_WIDTH))**(-1/2)
"Effective dielectric constant of the calibration trace"

CALIB_TRACE_GROUP_VELOCITY: float = SPEED_OF_LIGHT / CALIB_TRACE_EFFECTIVE_DIELECTRIC_CONSTANT**0.5
"Group velocity of signal on the calibration trace"

WIFI_CHANNEL1_FREQUENCY = 2.412e9
"Frequency of channel 1 in 2.4 GHz WiFi"

WIFI_CHANNEL_SPACING = 5e6
"Frequency spacing of WiFi channels"

WIFI_SUBCARRIER_SPACING = 312.5e3
"Subcarrier spacing of WiFi (in Hz)"