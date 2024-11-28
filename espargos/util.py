#!/usr/bin/env python3

import numpy as np
from . import constants
from . import csi


def csi_interp_iterative(csi: np.ndarray, weights: np.ndarray = None, iterations = 10):
	"""
	Interpolates CSI data (frequency-domain or time-domain) using an iterative algorithm.
	Tries to sum up the CSI data phase-coherently with the least error.
	More details about the algorithm (which is quite straightforward) can be found in section
	"IV. Linear Interpolation Baseline" in the paper "GAN-based Massive MIMO Channel Model Trained on Measured Data".

	:param csi: The CSI data to interpolate. Complex-valued NumPy array. Can be an array with arbitrary dimensions, but the first dimension must be the number of CSI datapoints.
	:param weights: The weights to use for each CSI datapoint. If None, all datapoints are weighted equally.
	:param iterations: The number of iterations to perform. Default is 10.

	:return: The interpolated CSI data. Complex-valued NumPy array with the same shape as the input CSI data.
	"""
	if weights is None:
		weights = np.ones(len(csi), dtype = csi.dtype) / len(csi)

	phi = np.zeros_like(weights, dtype = csi.dtype)
	w = None
	
	for i in range(iterations):
		w = np.einsum("n,n,n...->...", weights, np.exp(-1.0j * phi), csi)
		phi = np.angle(np.einsum("a,na->n", np.conj(w.flatten()), csi.reshape(len(csi), -1)))
		#err = np.sum([weights[n] * np.linalg.norm(csi[n] - np.exp(1.0j * phi[n]) * w)**2 for n in range(len(csi))])

	return w

def csi_interp_iterative_by_array(csi: np.ndarray, weights: np.ndarray = None, iterations = 10):
	"""
	Interpolates CSI data (frequency-domain or time-domain) using an iterative algorithm.
	Same as :func:`csi_interp_iterative`, but assumes that second dimension of :code:`csi` is the antenna array dimension and performs the interpolation for each antenna array separately.
	"""
	csi_interp = np.zeros((csi.shape[1], *csi.shape[2:]), dtype = csi.dtype)

	for b in range(csi.shape[1]):
		csi_interp[b] = csi_interp_iterative(csi[:,b], weights=weights, iterations=iterations)

	return csi_interp

def csi_interp_eigenvec(csi: np.ndarray, weights: np.ndarray = None):
	"""
	Interpolates CSI data (frequency-domain or time-domain) by finding the principal eigenvector of the covariance matrix.

	:param csi: The CSI data to interpolate. Complex-valued NumPy array. Can be an array with arbitrary dimensions, but the first dimension must be the number of CSI datapoints.
	:param weights: The weights to use for each CSI datapoint. If None, all datapoints are weighted equally.
	"""
	if weights is None:
		weights = np.ones(len(csi)) / len(csi)

	csi_shape = csi.shape[1:]
	csi = np.reshape(csi, (csi.shape[0], -1))
	R = np.einsum("n,na,nb->ab", weights, csi, np.conj(csi))

	# eig is faster than eigh for small matrices like the one here
	w, v = np.linalg.eig(R)
	principal = np.argmax(w)

	return np.reshape(v[:, principal], csi_shape)

def get_frequencies_ht40(primary_channel: int, secondary_channel: int):
	"""
	Returns the frequencies of the subcarriers in an HT40 2.4GHz WiFi channel.
	:param primary_channel: The primary channel number.
	:param secondary_channel: The secondary channel number.
	:return: The frequencies of the subcarriers, in Hz, NumPy array.
	"""
	center_primary = constants.WIFI_CHANNEL1_FREQUENCY + constants.WIFI_CHANNEL_SPACING * (primary_channel - 1)
	center_secondary = constants.WIFI_CHANNEL1_FREQUENCY + constants.WIFI_CHANNEL_SPACING * (secondary_channel - 1)
	center_ht40 = (center_primary + center_secondary) / 2
	ht40_subcarrier_count = (csi.csi_buf_t.htltf_lower.size + csi.HT40_GAP_SUBCARRIERS * 2 + csi.csi_buf_t.htltf_higher.size) // 2
	assert(ht40_subcarrier_count % 2 == 1)
	return center_ht40 + np.arange(-ht40_subcarrier_count // 2, ht40_subcarrier_count // 2) * constants.WIFI_SUBCARRIER_SPACING

def get_calib_trace_wavelength(frequencies: np.ndarray):
	"""
	Returns the wavelength of the subcarriers on the calibration traces on the ESPARGOS sensor board.

	:param frequencies: The frequencies of the subcarriers, in Hz, NumPy array.
	:return: The wavelengths of the subcarriers, in meters, NumPy array.
	"""
	return constants.CALIB_TRACE_GROUP_VELOCITY / frequencies

def get_cable_wavelength(frequencies: np.ndarray, velocity_factors: np.ndarray):
	"""
	Returns the wavelength of the provided subcarrier frequencies on a cable with the given velocity factors.

	:param frequencies: The frequencies of the subcarriers, in Hz, NumPy array.
	:param velocity_factors: The velocity factors of the cable, NumPy array.
	:return: The wavelengths of the subcarriers, in meters, NumPy array.
	"""
	return constants.SPEED_OF_LIGHT / frequencies[np.newaxis, :] * velocity_factors[:, np.newaxis]

def interpolate_ht40_gap(csi_ht40: np.ndarray):
	"""
	Apply linear interpolation to determine realistic values for the subcarrier channel coefficients in the gap between the bonded channels in an HT40 channel.

	:param csi_ht40: The CSI data for an HT40 channel. Complex-valued NumPy array with arbitrary shape, but the last dimension must be the subcarriers.
	:return: The CSI data with the values in the gap filled in.
	"""
	index_left = csi.csi_buf_t.htltf_lower.size // 2 - 1
	index_right = csi.csi_buf_t.htltf_lower.size // 2 + csi.HT40_GAP_SUBCARRIERS
	missing_indices = np.arange(index_left + 1, index_right)
	left = csi_ht40[..., index_left]
	right = csi_ht40[..., index_right]
	interp = (missing_indices - index_left) / (index_right - index_left)
	csi_ht40[..., missing_indices] = interp * right[..., np.newaxis] + (1 - interp) * left[..., np.newaxis]

def shift_to_firstpeak(csi_datapoints: np.ndarray, max_delay_taps = 3, search_resolution = 40, peak_threshold = 0.4):
	"""
	Shifts the CSI data so that the first peak of the channel impulse response is at time 0.
	Uses a simple but rather computation-efficient algorithm to find the first peak of the channel impulse response (as opposed to superresolution-based approach).

	:param csi_datapoints: The CSI data to shift, frequency-domain. Complex-valued NumPy array with shape (datapoints, arrays, rows, columns, subcarriers).
	:param max_delay_taps: The maximum number of time taps to shift the CSI data by.
	:param search_resolution: The number of search points (granularity) to use for the time shift.
	:param peak_threshold: The threshold for the peak detection, as a fraction of the maximum peak power.

	:return: The frequency-domain CSI data with the first peak of the channel impulse response at time 0.
	"""
	# Time-shift all collected CSI so that first "peak" is at time 0
	# CSI datapoints has shape (datapoints, arrays, rows, columns, subcarriers)
	shifts = np.linspace(-max_delay_taps, 0, search_resolution)
	subcarrier_range = np.arange(-csi_datapoints.shape[-1] // 2, csi_datapoints.shape[-1] // 2) + 1
	shift_vectors = np.exp(1.0j * np.outer(shifts, 2 * np.pi * subcarrier_range / csi_datapoints.shape[-1]))
	powers_by_delay = np.abs(np.einsum("lbrms,ds->lbrmd", csi_datapoints, shift_vectors))
	max_peaks = np.max(powers_by_delay, axis = -1)
	first_peak = np.argmax(powers_by_delay > peak_threshold * max_peaks[:,:,:,:,np.newaxis], axis = -1)
	shift_to_firstpeak = shift_vectors[first_peak]

	return shift_to_firstpeak * csi_datapoints

def fdomain_to_tdomain_pdp_mvdr(csi_fdomain: np.ndarray, chunksize = 36, tap_min = -7, tap_max = 7, resolution = 200):
	"""
	Convert frequency-domain CSI data to a time-domain power delay profile (PDP) using the MVDR beamformer.

	:param: csi_fdomain: The frequency-domain CSI data. Complex-valued NumPy array with shape (datapoints, arrays, rows, columns, subcarriers).
	:return: The delays (in taps) and the PDPs of shape (datapoints, arrays, rows, columns, delays), as NumPy arrays.
	"""
	# Compute the covariance matrix R
	chunksize = csi_fdomain.shape[-1] if chunksize is None else chunksize
	chunkcount = csi_fdomain.shape[-1] // chunksize
	padding = (csi_fdomain.shape[-1] - chunkcount * chunksize) // 2

	csi_chunked = np.reshape(csi_fdomain[..., padding:padding + chunkcount * chunksize], csi_fdomain.shape[:-1] + (chunkcount, chunksize), order = "C")
	R = 1 / csi_chunked.shape[0] * np.einsum("dbrmci,dbrmcj->brmij", csi_chunked, np.conj(csi_chunked))

	delays_taps = np.linspace(tap_min, tap_max, resolution)
	# TODO: get rid of magic constant 128
	steering_vectors = np.exp(-1.0j * 2 * np.pi * np.outer(np.arange(R.shape[-1]), delays_taps / 128))

	R = (R + np.flip(np.conj(R), axis = (3, 4))) / 2
	R = R + 0.1 * np.eye(R.shape[-1])[np.newaxis,np.newaxis,np.newaxis,:,:]

	# Computation using matrix inverse
	#R_inv = np.linalg.inv(R)
	#P_mvdr = 1 / np.real(np.einsum("it,brmij,jt->brmt", np.conj(steering_vectors), R_inv, steering_vectors))

	# Computation using matrix solve
	R_inv_steering_vectors = np.linalg.solve(R, steering_vectors)
	P_mvdr = 1 / np.real(np.einsum("it,brmit->brmt", np.conj(steering_vectors), R_inv_steering_vectors))

	return delays_taps, P_mvdr

def fdomain_to_tdomain_pdp_music(csi_fdomain: np.ndarray, source_count: int = None, chunksize = 36, tap_min = -7, tap_max = 7, resolution = 200):
	"""
	Convert frequency-domain CSI data to a time-domain power delay profile (PDP) using MUSIC super-resolution.

	:param: csi_fdomain: The frequency-domain CSI data. Complex-valued NumPy array with shape (datapoints, arrays, rows, columns, subcarriers).
	:return: The delays (in taps) and the PDPs of shape (datapoints, arrays, rows, columns, delays), as NumPy arrays.
	"""
	# Compute the covariance matrix R
	chunksize = csi_fdomain.shape[-1] if chunksize is None else chunksize
	chunkcount = csi_fdomain.shape[-1] // chunksize
	padding = (csi_fdomain.shape[-1] - chunkcount * chunksize) // 2

	csi_chunked = np.reshape(csi_fdomain[..., padding:padding + chunkcount * chunksize], csi_fdomain.shape[:-1] + (chunkcount, chunksize), order = "C")
	R = 1 / csi_chunked.shape[0] * np.einsum("dbrmci,dbrmcj->brmij", csi_chunked, np.conj(csi_chunked))

	delays_taps = np.linspace(tap_min, tap_max, resolution)
	# TODO: get rid of magic constant 128
	steering_vectors = np.exp(-1.0j * 2 * np.pi * np.outer(np.arange(R.shape[-1]), delays_taps / 128))

	# Use forward–backward correlation matrix (FBCM)
	R = (R + np.flip(np.conj(R), axis = (3, 4))) / 2

	eigval, eigvec = np.linalg.eigh(R)
	eigval = eigval[:,:,:,::-1]
	eigvec = eigvec[:,:,:,:,::-1]

	P_music = np.zeros(R.shape[:3] + (resolution,))
	for array in range(R.shape[0]):
		for row in range(R.shape[1]):
			for col in range(R.shape[2]):
				antenna_source_count = source_count
				if antenna_source_count is None:
					# Rissanen MDL for FBCM, as described in
					# Xinrong Li and Kaveh Pahlavan: "Super-resolution TOA estimation with diversity for indoor geolocation" in IEEE Transactions on Wireless Communications
					ev = np.real(eigval)[array,row,col,:]

					# M = number of chunks for autocorrelation matrix computation, L = maximum number of sources
					M = chunkcount
					L = 10
					mdl = np.zeros(L)

					for k in range(L):
						mdl[k] = -M * (L - k) * (np.sum(np.log(ev[k:L] + 1e-6) / (L - k)) - np.log(np.sum(ev[k:L] + 1e-6) / (L - k)))
						mdl[k] = mdl[k] + (1/4) * k * (2 * L - k + 1) * np.log(M)

					antenna_source_count = np.argmin(mdl)

				Qn = eigvec[array,row,col,:,antenna_source_count:]
				P_music[array,row,col] = 1 / np.linalg.norm(np.einsum("cn,cr->nr", np.conj(Qn), steering_vectors), axis = 0)

	return delays_taps, P_music

def estimate_toas_rootmusic(csi_fdomain: np.ndarray, max_source_count = 2, chunksize = 36, per_board_average = False):
	"""
	Estimate the time of arrivals (ToAs) of the LoS paths using the root-MUSIC algorithm.

	:param csi_fdomain: The frequency-domain CSI data. Complex-valued NumPy array with shape (datapoints, arrays, rows, columns, subcarriers).
	:param max_source_count: The maximum number of sources to estimate. The number of sources is determined using the Rissanen MDL criterion, but this parameter can be used to limit the number of sources.
	:param chunksize: The size of the chunks to use for the covariance matrix computation.
	:param per_board_average: If True, compute the average ToA over all antennas per board. If False, return the ToAs for each antenna separately.
	:return: The estimated ToAs of the LoS paths, in seconds, NumPy array of shape :code:`(boardcount, constants.ROWS_PER_BOARD, constants.ANTENNAS_PER_ROW)`.
	"""
	# Compute the covariance matrix R
	chunksize = csi_fdomain.shape[-1] if chunksize is None else chunksize
	chunkcount = csi_fdomain.shape[-1] // chunksize
	padding = (csi_fdomain.shape[-1] - chunkcount * chunksize) // 2

	csi_chunked = np.reshape(csi_fdomain[..., padding:padding + chunkcount * chunksize], csi_fdomain.shape[:-1] + (chunkcount, chunksize), order = "C")

	if per_board_average:
		# Compute R per-board, but add dummy dimensions for row and column
		R = 1 / (csi_chunked.shape[0] * csi_chunked.shape[2] * csi_chunked.shape[3]) * np.einsum("dbrmci,dbrmcj->bij", csi_chunked, np.conj(csi_chunked))
		R = R[:,np.newaxis,np.newaxis,:,:]
	else:
		R = 1 / csi_chunked.shape[0] * np.einsum("dbrmci,dbrmcj->brmij", csi_chunked, np.conj(csi_chunked))

	# Use forward–backward correlation matrix (FBCM)
	R = (R + np.flip(np.conj(R), axis = (3, 4))) / 2

	if chunksize > 50:
		eigval, eigvec = np.linalg.eig(R)
	else:
		eigval, eigvec = np.linalg.eigh(R)

	toas_by_antenna = np.zeros(R.shape[:3])
	for array in range(R.shape[0]):
		for row in range(R.shape[1]):
			for col in range(R.shape[2]):
				# Rissanen MDL for FBCM, as described in
				# Xinrong Li and Kaveh Pahlavan: "Super-resolution TOA estimation with diversity for indoor geolocation" in IEEE Transactions on Wireless Communications
				ev = np.sort(np.real(eigval[array,row,col,:]))[::-1]

				# M = number of chunks for autocorrelation matrix computation, L = maximum number of sources
				M = chunkcount * csi_fdomain.shape[0]
				L = 10
				mdl = np.zeros(L)

				for k in range(L):
					mdl[k] = -M * (L - k) * (np.sum(np.log(ev[k:L] + 1e-6) / (L - k)) - np.log(np.sum(ev[k:L] + 1e-6) / (L - k)))
					mdl[k] = mdl[k] + (1/4) * k * (2 * L - k + 1) * np.log(M)

				antenna_source_count = min(np.argmin(mdl), max_source_count)

				# Now that we determined the number of sources via Rissanen MDL criterion,
				# we can use the root-MUSIC algorithm to estimate the ToAs
				order = np.argsort(np.real(eigval[array,row,col]))[::-1]
				Qn = np.asmatrix(eigvec[array,row,col,:,:][:,order][:,antenna_source_count:])
				C = np.matmul(Qn, Qn.H)

				coeffs = np.asarray([np.trace(C, offset = diag) for diag in range(1, len(C))])

				# Remove some of the smaller noise coefficients, trade accuracy for speed
				coeffs = np.hstack((coeffs[::-1], np.trace(C), coeffs.conj()))

				roots = np.roots(coeffs)
				roots = roots[abs(roots) < 1]
				powers = 1 / (1 - np.abs(roots))
				largest_roots = np.argsort(powers)[::-1]

				source_delays = -np.angle(roots[largest_roots[:antenna_source_count]]) / (2 * np.pi) / constants.WIFI_SUBCARRIER_SPACING
			
				# Out of the strongest 2 paths (or only strongest, if only one source exists), pick the earliest one
				if len(source_delays) > 0:
					toas_by_antenna[array,row,col] = np.min(source_delays[:min(antenna_source_count, 2)])

	# If per-board averaging is enabled, remove dummy dimensions
	if per_board_average:
		toas_by_antenna = toas_by_antenna[:,0,0]

	return toas_by_antenna