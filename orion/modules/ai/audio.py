"""Audio intelligence unit - lightweight, rule-based FFT detectors."""
import numpy as np
import threading
import logging
from .. import config

logger = logging.getLogger(__name__)


class AudioIntelligenceUnit:
    def __init__(self):
        self.lock = threading.Lock()
        self.classes = ["Silence", "Excavator", "Chainsaw", "Speech"]
        self.sr = getattr(config, 'MIC_SAMPLE_RATE', 16000)
        self.window = getattr(config, 'AUDIO_FFT_WINDOW', 1024)
        self.bands = getattr(config, 'AUDIO_BANDS_HZ', {})
        self.thresholds = getattr(config, 'AUDIO_DETECTION', {})

    def load_model(self, model_path=None, class_names=None):
        if class_names:
            self.classes = class_names
        logger.info("🧠 AudioIntelligenceUnit ready (rule-based)")
        return True

    def unload_model(self):
        logger.info("💤 AudioIntelligenceUnit unloaded")

    def _compute_spectrum(self, samples):
        if len(samples) < self.window:
            pad = self.window - len(samples)
            samples = np.pad(samples, (0, pad))
        win = np.hanning(self.window)
        frame = samples[: self.window] * win
        spec = np.fft.rfft(frame)
        mag = np.abs(spec)
        freqs = np.fft.rfftfreq(self.window, 1.0 / self.sr)
        return freqs, mag

    def _band_energy(self, freqs, mag, low_hz, high_hz):
        idx = np.where((freqs >= low_hz) & (freqs < high_hz))[0]
        if idx.size == 0:
            return 0.0
        return float(np.sum(mag[idx] ** 2))

    def _spectral_flatness(self, mag):
        mag = np.where(mag <= 1e-12, 1e-12, mag)
        geo_mean = np.exp(np.mean(np.log(mag)))
        arith_mean = np.mean(mag)
        return float(geo_mean / (arith_mean + 1e-12))

    def infer(self, audio_samples):
        try:
            if audio_samples is None or len(audio_samples) == 0:
                return "Silence", 0.0

            with self.lock:
                samples = np.asarray(audio_samples, dtype=np.float32)
                samples = samples - np.mean(samples)
                freqs, mag = self._compute_spectrum(samples)
                total_energy = float(np.sum(mag ** 2)) + 1e-12

                low_hz, low_hi = self.bands.get('low', (20, 300))
                mid_hz, mid_hi = self.bands.get('mid', (300, 2000))
                high_hz, high_hi = self.bands.get('high', (2000, 6000))

                low_energy = self._band_energy(freqs, mag, low_hz, low_hi)
                mid_energy = self._band_energy(freqs, mag, mid_hz, mid_hi)
                high_energy = self._band_energy(freqs, mag, high_hz, high_hi)

                low_ratio = low_energy / total_energy
                mid_high_ratio = (mid_energy + high_energy) / total_energy
                flatness = self._spectral_flatness(mag)

                exc_thresh = self.thresholds.get('excavator', {})
                if low_ratio >= exc_thresh.get('low_energy_ratio', 0.55):
                    conf = min(1.0, (low_ratio - exc_thresh.get('low_energy_ratio', 0.55)) / 0.45 + 0.5)
                    return "Excavator", max(conf, exc_thresh.get('min_confidence', 0.5))

                ch_thresh = self.thresholds.get('chainsaw', {})
                if (mid_high_ratio >= ch_thresh.get('mid_high_energy_ratio', 0.45)) and (flatness <= ch_thresh.get('spectral_flatness', 0.1)):
                    conf = min(1.0, mid_high_ratio + (0.1 - flatness))
                    return "Chainsaw", max(conf, ch_thresh.get('min_confidence', 0.5))

                centroid = float(np.sum(freqs * mag) / (np.sum(mag) + 1e-12))
                sp_thresh = self.thresholds.get('speech', {})
                zcr = float(((np.diff(np.sign(samples)) != 0).sum()) / float(len(samples)))
                if centroid <= sp_thresh.get('centroid_max', 3000) and zcr <= sp_thresh.get('zcr_max', 0.15) and mid_energy / total_energy > 0.1:
                    conf = min(1.0, 1.0 - (centroid / (sp_thresh.get('centroid_max', 3000) * 1.5)))
                    return "Speech", max(conf, sp_thresh.get('min_confidence', 0.5))

                return "Silence", 0.0

        except Exception as e:
            logger.error(f"❌ Audio inference error: {e}")
            return None, 0.0

    def is_loaded(self):
        return True
