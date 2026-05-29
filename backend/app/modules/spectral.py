import numpy as np
import cv2

def detect_spectral_anomalies(image_matrix: np.ndarray) -> float:
    gray = cv2.cvtColor(image_matrix, cv2.COLOR_BGR2GRAY)
    f_transform = np.fft.fft2(gray)
    f_shift = np.fft.fftshift(f_transform)
    magnitude_spectrum = np.log(np.abs(f_shift) + 1)
    
    h, w = magnitude_spectrum.shape
    center_y, center_x = h // 2, w // 2
    
    y, x = np.indices((h, w))
    r = np.sqrt((x - center_x)**2 + (y - center_y)**2).astype(int)
    
    tbin = np.bincount(r.ravel(), magnitude_spectrum.ravel())
    nr = np.bincount(r.ravel())
    radial_profile = tbin / np.maximum(nr, 1)
    
    tail_energy = np.sum(radial_profile[int(len(radial_profile)*0.75):])
    total_energy = np.sum(radial_profile)
    
    return float(tail_energy / (total_energy + 1e-7))