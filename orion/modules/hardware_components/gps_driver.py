"""GPS driver interfaces and example stubs

Provide a minimal GPS driver interface. The existing `GPSTracker` in
`orion/modules/hardware.py` follows a simple `get_location()` shape; a real
driver can be implemented to replace that class or to be wrapped by it.
"""
from typing import Dict

class GPSDriverBase:
    """Abstract GPS driver interface."""

    def initialize(self) -> None:
        """Prepare GPS hardware (e.g., open serial port)."""
        raise NotImplementedError()

    def get_location(self) -> Dict[str, float]:
        """Return {'lat': float, 'lng': float} or raise on failure."""
        raise NotImplementedError()

    def close(self) -> None:
        """Cleanup resources."""
        raise NotImplementedError()


class SerialGPSDriver(GPSDriverBase):
    """Example serial NMEA GPS driver stub.

    Replace with a real serial-parsing implementation (e.g., pynmea2) when
    you connect the GPS hardware.
    """

    def __init__(self, port: str = '/dev/ttyS0', baud: int = 9600):
        self.port = port
        self.baud = baud
        self._serial = None

    def initialize(self) -> None:
        try:
            import serial
            # Open serial port to GPS module. Many u-blox modules expose ttyAMA0 or /dev/ttyS0
            self._serial = serial.Serial(self.port, self.baud, timeout=1)
        except Exception as e:
            # Keep _serial as None, callers should handle absence
            self._serial = None
            raise RuntimeError(f"Failed to open GPS serial port {self.port}: {e}")

    def get_location(self) -> Dict[str, float]:
        # Read NMEA lines and parse using pynmea2 if available. This method will
        # attempt to find a valid position-bearing sentence (GGA/RMC) and return
        # the latest coordinates. If parsing libs are missing or no fix is
        # available, raise RuntimeError.
        if self._serial is None:
            raise RuntimeError("GPS serial port not initialized")

        try:
            import pynmea2
        except Exception:
            raise RuntimeError("pynmea2 required for parsing NMEA sentences")

        # Try reading a few lines for a valid fix
        attempts = 0
        max_attempts = 20
        while attempts < max_attempts:
            try:
                line = self._serial.readline().decode('ascii', errors='ignore').strip()
            except Exception:
                line = ''

            attempts += 1
            if not line:
                continue
            try:
                msg = pynmea2.parse(line)
            except Exception:
                continue

            # GGA contains fix and lat/lon
            if hasattr(msg, 'latitude') and hasattr(msg, 'longitude'):
                lat = getattr(msg, 'latitude', 0.0)
                lon = getattr(msg, 'longitude', 0.0)
                if lat != 0.0 and lon != 0.0:
                    return {'lat': float(lat), 'lng': float(lon)}

            # RMC may also provide valid lat/lon when status is 'A' (active)
            if msg.__class__.__name__ == 'RMC':
                try:
                    if getattr(msg, 'status', 'V') == 'A':
                        lat = getattr(msg, 'latitude', 0.0)
                        lon = getattr(msg, 'longitude', 0.0)
                        if lat != 0.0 and lon != 0.0:
                            return {'lat': float(lat), 'lng': float(lon)}
                except Exception:
                    pass

        raise RuntimeError('No valid GPS fix found')

    def close(self) -> None:
        try:
            if self._serial:
                self._serial.close()
        finally:
            self._serial = None
