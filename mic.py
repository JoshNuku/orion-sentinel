import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import argparse
import wave
import struct

# Parse command line arguments
parser = argparse.ArgumentParser(description='Record audio from ADS1115 ADC microphone')
parser.add_argument('--output', type=str, help='Output WAV file path (e.g., recording.wav)')
parser.add_argument('--duration', type=float, default=5.0, help='Recording duration in seconds (default: 5.0)')
parser.add_argument('--rate', type=int, default=8000, help='Sample rate in Hz (default: 8000)')
parser.add_argument('--channel', type=int, choices=[0,1,2,3], help='Override default channel (0-3 for A0-A3)')
args = parser.parse_args()

print("--- TESTING MICROPHONE (ADS1115) ---")

try:
    # 1. Create the I2C bus
    i2c = busio.I2C(board.SCL, board.SDA)
    
    # 2. Create the ADC object
    ads = ADS.ADS1115(i2c)
    
    # 3. Create the channel for the Microphone
    # Microphone is wired to A1 (channel index 1)
    mic_channel = None
    
    # If user specified a channel, use it directly
    if args.channel is not None:
        try:
            mic_channel = AnalogIn(ads, args.channel)
            print(f"✅ Using user-specified channel index {args.channel} (A{args.channel}).")
        except Exception as e:
            print(f"❌ Failed to open channel {args.channel}: {e}")
            raise
    else:
        # First try named constants on the ADS module (older examples sometimes use ADS.P1 etc.)
        for pin_name in ("P1", "A1", "P0", "P2", "P3", "A0", "A2", "A3"):
            pin = getattr(ADS, pin_name, None)
            if pin is None:
                continue
            try:
                mic_channel = AnalogIn(ads, pin)
                print(f"✅ Using ADS named constant {pin_name}.")
                break
            except Exception:
                mic_channel = None

        # If no named constants, try using integer channel indices (prioritize 1=A1 first)
        if mic_channel is None:
            for idx in (1, 0, 2, 3):
                try:
                    mic_channel = AnalogIn(ads, idx)
                    print(f"✅ Using ADS channel index {idx} (A{idx}).")
                    break
                except Exception:
                    mic_channel = None

    if mic_channel is None:
        # If we couldn't open any channel, provide a helpful error.
        available = [n for n in ("P0", "P1", "P2", "P3", "A0", "A1", "A2", "A3") if hasattr(ADS, n)]
        if available:
            raise RuntimeError(f"Found ADS constants {available} but failed to open a channel. Check wiring or permissions.")
        else:
            raise AttributeError(
                "Could not find ADS named pin constants on the imported ADS module. "
                "Newer versions of the library expect integer channel indices (0..3). "
                "The script attempted both approaches and failed to open a channel. "
                "Try:\n  - Ensuring your I2C wiring is correct and the device is powered,\n  - Installing/upgrading the library: `python -m pip install --upgrade adafruit-circuitpython-ads1x15 adafruit-blinka`, or\n  - Running the script on the hardware-enabled device with I2C support.")

    print("✅ ADS1115 Detected.")
    
    if args.output:
        # Recording mode
        print(f"🎙️  Recording to {args.output}")
        print(f"   Duration: {args.duration}s, Sample rate: {args.rate} Hz")
        print("   Recording started...")
        
        samples = []
        sample_interval = 1.0 / args.rate
        num_samples = int(args.duration * args.rate)
        start_time = time.time()
        
        for i in range(num_samples):
            target_time = start_time + (i * sample_interval)
            
            # Read the raw value
            raw_value = mic_channel.value
            samples.append(raw_value)
            
            # Progress indicator every 10%
            if (i + 1) % (num_samples // 10) == 0:
                progress = ((i + 1) / num_samples) * 100
                print(f"   {progress:.0f}% complete...")
            
            # Sleep until next sample time
            sleep_time = target_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        print(f"✅ Recording complete! Captured {len(samples)} samples")
        
        # Save to WAV file
        print(f"💾 Saving to {args.output}...")
        with wave.open(args.output, 'w') as wav_file:
            # Configure WAV: 1 channel, 2 bytes per sample (16-bit), sample rate
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(args.rate)
            
            # Convert samples to 16-bit signed integers (centered around 0)
            # Normalize from ADC range (0-32767) to audio range (-32768 to 32767)
            for sample in samples:
                # Center the signal around 0 by subtracting the midpoint
                centered = sample - 16384
                # Pack as signed 16-bit little-endian
                wav_file.writeframes(struct.pack('<h', centered))
        
        print(f"✅ Saved {args.output}")
    else:
        # Live monitoring mode
        print("Reading Microphone levels... (Press CTRL+C to stop)")
        print("Try clapping or blowing on the mic!")

        while True:
            # Read the raw value (0 to 26000+) and voltage
            raw_value = mic_channel.value
            voltage = mic_channel.voltage
            
            # Create a simple visual bar graph in the terminal
            bar_length = int(raw_value / 500) 
            bar = "|" * bar_length
            
            print(f"Value: {raw_value:5d}  Voltage: {voltage:.2f}V  {bar}")
            
            # Small delay to make it readable
            time.sleep(0.1)

except ValueError:
    print("❌ Error: I2C device not found. Check wiring of the Blue Shield.")
except Exception as e:
    print(f"❌ Error: {e}")