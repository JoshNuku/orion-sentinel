#!/usr/bin/env python3
"""
Small harness to replay WAV files into AudioIntelligenceUnit for tuning.
Usage:
    python3 orion/test_audio.py path/to/file.wav

This script avoids heavy dependencies and uses the standard `wave` module
plus numpy for resampling.
"""
import sys
import wave
import numpy as np
from modules import config
from modules.ai_engine import AudioIntelligenceUnit


def read_wav(path):
    with wave.open(path, 'rb') as wf:
        sr = wf.getframerate()
        frames = wf.getnframes()
        sampwidth = wf.getsampwidth()
        data = wf.readframes(frames)

    # Convert bytes to numpy
    if sampwidth == 2:
        dtype = np.int16
    elif sampwidth == 4:
        dtype = np.int32
    else:
        # fallback to int16
        dtype = np.int16

    audio = np.frombuffer(data, dtype=dtype).astype(np.float32)

    # If stereo, take mean of channels
    # Determine number of channels from file
    try:
        with wave.open(path, 'rb') as wf:
            nch = wf.getnchannels()
    except Exception:
        nch = 1

    if nch > 1:
        audio = audio.reshape(-1, nch).mean(axis=1)

    # Normalize to roughly ADC-like range (0..65535) for compatibility with ADS1115-sourced arrays
    # Here we'll scale to zero-centered values
    audio = audio - np.mean(audio)
    # Scale to -1..1
    maxv = np.max(np.abs(audio)) if np.max(np.abs(audio)) > 0 else 1.0
    audio = audio / maxv

    return audio, sr


def resample_to(audio, src_sr, dst_sr):
    if src_sr == dst_sr:
        return audio
    duration = len(audio) / float(src_sr)
    target_len = int(duration * dst_sr)
    if target_len <= 0:
        return np.zeros(int(dst_sr * min(1.0, duration)), dtype=np.float32)
    t_old = np.linspace(0.0, duration, num=len(audio), endpoint=False)
    t_new = np.linspace(0.0, duration, num=target_len, endpoint=False)
    return np.interp(t_new, t_old, audio).astype(np.float32)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 orion/test_audio.py path/to/file.wav")
        sys.exit(1)

    path = sys.argv[1]
    audio, sr = read_wav(path)
    print(f"Loaded {path}: {len(audio)} samples @ {sr} Hz")

    target_sr = config.MIC_SAMPLE_RATE
    audio_rs = resample_to(audio, sr, target_sr)
    print(f"Resampled to {target_sr} Hz: {len(audio_rs)} samples")

    # The audio engine expects samples in ADC-like units. We'll scale
    # the normalized -1..1 floats to a pseudo-ADC range (e.g., 0..65535) so
    # behavior is similar to live ADC input.
    adc_like = (audio_rs * 10000.0).astype(np.float32)

    ai = AudioIntelligenceUnit()
    ai.load_model()

    # Split into buffer-duration chunks and run infer
    buf_dur = config.MIC_BUFFER_DURATION
    chunk_len = int(buf_dur * target_sr)
    for i in range(0, len(adc_like), chunk_len):
        chunk = adc_like[i:i+chunk_len]
        if len(chunk) < chunk_len:
            # pad
            chunk = np.pad(chunk, (0, chunk_len - len(chunk)))
        cls, conf = ai.infer(chunk)
        print(f"Chunk {i//chunk_len}: {cls} ({conf:.2%})")

    print("Done")
