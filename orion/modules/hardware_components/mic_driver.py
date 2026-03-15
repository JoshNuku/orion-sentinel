"""Microphone driver interfaces and example stubs

Implement a driver with the minimal API used by `MicrophoneMonitor`:

- initialize(): prepare hardware
- read(): return numeric ADC-like sample (int/float)
- close(): cleanup resources

You can attach a driver instance with `MicrophoneMonitor.set_driver(driver)`.
"""
from typing import Optional

class MicDriverBase:
    """Abstract base for microphone drivers."""

    def initialize(self) -> None:
        """Prepare hardware resources. Raise on failure."""
        raise NotImplementedError()

    def read(self) -> float:
        """Return a single ADC-like sample (numeric)."""
        raise NotImplementedError()

    def close(self) -> None:
        """Release hardware resources."""
        raise NotImplementedError()


class ADS1115MicDriver(MicDriverBase):
    """Example wrapper for ADS1115 + AnalogIn.

    This is a light adapter showing how to fit the `AnalogIn` API into the
    MicDriverBase interface. Importing adafruit libraries here is optional;
    you can keep the real imports only in your runtime environment.
    """

    def __init__(self, ads1115_obj=None, analog_in_obj=None, channel=None):
        # You can pass pre-created ADS/AnalogIn objects or a channel id to
        # construct them here.
        self._ads = ads1115_obj
        self._analog = analog_in_obj
        self._channel = channel

    def initialize(self) -> None:
        # If you didn't pass objects, initialize bus/ads/analog here.
        # e.g.:
        # import board, busio, adafruit_ads1x15.ads1115 as ADS
        # from adafruit_ads1x15.analog_in import AnalogIn
        # i2c = busio.I2C(board.SCL, board.SDA)
        # self._ads = ADS.ADS1115(i2c)
        # self._analog = AnalogIn(self._ads, self._channel)
        if self._analog is None:
            raise RuntimeError("ADS1115 AnalogIn object not provided")

    def read(self) -> float:
        # Return the current analog reading
        return float(self._analog.value)

    def close(self) -> None:
        # No explicit close required for adafruit objects, but keep method
        # to satisfy the interface.
        self._analog = None
        self._ads = None


class ADS1115Driver(ADS1115MicDriver):
    """Concrete ADS1115 driver which initializes the I2C bus and AnalogIn

    Use this when you want the driver to manage bus initialization itself.
    """

    def __init__(self, channel=1):
        super().__init__(ads1115_obj=None, analog_in_obj=None, channel=channel)
        self._channel = channel

    def initialize(self) -> None:
        try:
            import board
            import busio
            import adafruit_ads1x15.ads1115 as ADS
            from adafruit_ads1x15.analog_in import AnalogIn

            i2c = busio.I2C(board.SCL, board.SDA)
            self._ads = ADS.ADS1115(i2c)
            self._analog = AnalogIn(self._ads, self._channel)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize ADS1115 driver: {e}")

    def close(self) -> None:
        self._analog = None
        self._ads = None
