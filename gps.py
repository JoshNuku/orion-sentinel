import serial
import time
import os
import sys

print("--- TESTING GPS MODULE ---")

# Check for debug mode
DEBUG = '--debug' in sys.argv or '--hex' in sys.argv
AUTO_BAUD = '--auto-baud' in sys.argv

# Try multiple common serial port names
POSSIBLE_PORTS = ['/dev/ttyS0', '/dev/ttyAMA0', '/dev/serial0']
COMMON_BAUD_RATES = [9600, 4800, 38400, 57600, 115200]

def try_baud_rate(port, baud):
    """Try opening port at given baud rate and check for valid NMEA data."""
    try:
        test_ser = serial.Serial(port, baud, timeout=2)
        print(f"   Testing {baud} baud...", end='')
        
        # Read for up to 2 seconds
        start = time.time()
        while time.time() - start < 2:
            if test_ser.in_waiting > 0:
                data = test_ser.read(min(100, test_ser.in_waiting))
                # Check if we see NMEA sentence start ($GP or $GN)
                if b'$G' in data:
                    test_ser.close()
                    print(" ✅ Found NMEA data!")
                    return True
                # Check if all bytes are in printable ASCII range (valid NMEA)
                printable = sum(1 for b in data if 10 <= b < 127)
                if printable > len(data) * 0.8:  # 80% printable = likely correct
                    test_ser.close()
                    print(" ✅ Looks good!")
                    return True
        
        test_ser.close()
        print(" ❌ No valid data")
        return False
    except:
        print(" ❌ Failed to open")
        return False

# Find the first available port
ser = None
selected_port = None
selected_baud = None

for port in POSSIBLE_PORTS:
    if os.path.exists(port):
        if AUTO_BAUD:
            print(f"🔍 Auto-detecting baud rate on {port}...")
            for baud in COMMON_BAUD_RATES:
                if try_baud_rate(port, baud):
                    selected_port = port
                    selected_baud = baud
                    break
            if selected_baud:
                break
        else:
            try:
                ser = serial.Serial(port, COMMON_BAUD_RATES[0], timeout=1)
                selected_port = port
                selected_baud = COMMON_BAUD_RATES[0]
                break
            except serial.SerialException:
                print(f"⚠️  Port {port} exists but couldn't open it.")
                continue

if selected_port and selected_baud:
    if ser is None:
        ser = serial.Serial(selected_port, selected_baud, timeout=1)
    print(f"✅ Serial Port {selected_port} opened (Baud: {selected_baud}).")
    if not AUTO_BAUD and not DEBUG:
        print(f"   💡 Tip: If you see garbage, try: python3 gps.py --auto-baud")

if ser is None:
    print("❌ Error: Could not open any serial port or detect valid GPS data.")
    print("\n📋 To enable serial on Raspberry Pi:")
    print("   1. Run: sudo raspi-config")
    print("   2. Navigate to: Interface Options → Serial Port")
    print("   3. Login shell over serial? → No")
    print("   4. Serial port hardware enabled? → Yes")
    print("   5. Reboot: sudo reboot")
    print("\n   Or run: sudo raspi-config nonint do_serial 2")
    print("   (This disables serial console but enables serial hardware)")
    print("\n💡 Try: python3 gps.py --auto-baud")
    exit(1)

try:
    print("Listening for NMEA data... (Press CTRL+C to stop)")
    if DEBUG:
        print("🔍 DEBUG MODE: Showing all raw bytes\n")
    else:
        print("Note: If you see weird symbols, check your baud rate or wiring.")
        print("      Run with --debug flag to see raw bytes\n")

    no_data_count = 0
    bytes_received = 0
    
    while True:
        if ser.in_waiting > 0:
            no_data_count = 0  # Reset counter when data arrives
            
            if DEBUG:
                # Raw byte mode - show hex and ASCII
                raw_bytes = ser.read(ser.in_waiting)
                bytes_received += len(raw_bytes)
                hex_str = ' '.join(f'{b:02x}' for b in raw_bytes)
                ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in raw_bytes)
                print(f"[{len(raw_bytes)} bytes] HEX: {hex_str[:60]}")
                print(f"            ASCII: {ascii_str[:60]}\n")
            else:
                # Normal mode - decode lines
                try:
                    line = ser.readline().decode('utf-8', errors='replace').strip()
                    bytes_received += len(line)
                    
                    # Filter for key GPS sentences (GPGGA tells you location fix)
                    if line.startswith('$'):
                        print(f"Received: {line}")
                    elif line:
                        # Show non-NMEA data for debugging
                        print(f"Non-NMEA: {line[:80]}")
                except UnicodeDecodeError as e:
                    print(f"❌ Decode error: {e}")
        else:
            no_data_count += 1
            # Show status every 5 seconds if no data
            if no_data_count == 50:  # 50 * 0.1s = 5 seconds
                print(f"⚠️  No data received for 5 seconds. Total bytes: {bytes_received}")
                print(f"   Troubleshooting:")
                print(f"   • GPS needs clear sky view (can take 30s-5min for first fix)")
                print(f"   • Check wiring: GPS TX → Pi RX (/dev/ttyS0), GPS RX → Pi TX")
                print(f"   • Check power: Most GPS modules use 3.3V (some 5V)")
                print(f"   • Try baud rates: 4800, 9600, 38400, 115200")
                print(f"   • Run with --debug to see raw bytes\n")
                no_data_count = 0  # Reset to show message every 5 seconds
        
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\n✅ Stopping...")
    if ser:
        ser.close()
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    if ser:
        ser.close()


#ngrok config add-authtoken 37zokXl0JHhpuiPXFdoRd5ZZyXC_7oEBHrJCssUB8p8FjvAHp
