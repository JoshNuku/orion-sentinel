"""Hardware component drivers package

Provide small, well-documented driver interface classes for microphone and GPS
hardware. The sentinel core can attach a driver instance via
`MicrophoneMonitor.set_driver(driver)` or by replacing the `GPSTracker` with
an implementation that matches the same public API.

This package contains base classes and lightweight example stubs to guide
integration with ADS1115, USB mics, or serial GPS modules.
"""

from .mic_driver import MicDriverBase, ADS1115MicDriver, ADS1115Driver
from .gps_driver import GPSDriverBase, SerialGPSDriver

__all__ = [
    'MicDriverBase', 'ADS1115MicDriver', 'ADS1115Driver',
    'GPSDriverBase', 'SerialGPSDriver'
]
