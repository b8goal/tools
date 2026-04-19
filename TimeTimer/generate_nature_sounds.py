#!/usr/bin/env python3
"""
Generate nature sound audio files for Time Timer
Uses simple sine waves and noise to simulate nature sounds
"""
import numpy as np
from scipy.io import wavfile
import os

def generate_rain_sound(duration=2, sample_rate=44100):
    """Generate rain sound using white noise"""
    # White noise for rain
    noise = np.random.normal(0, 0.3, int(duration * sample_rate))
    
    # Apply low-pass filter effect
    from scipy import signal
    b, a = signal.butter(4, 0.3)
    filtered = signal.filtfilt(b, a, noise)
    
    # Fade in/out
    fade_samples = int(0.1 * sample_rate)
    fade_in = np.linspace(0, 1, fade_samples)
    fade_out = np.linspace(1, 0, fade_samples)
    
    filtered[:fade_samples] *= fade_in
    filtered[-fade_samples:] *= fade_out
    
    # Normalize
    filtered = filtered / np.max(np.abs(filtered)) * 0.7
    
    return (filtered * 32767).astype(np.int16)

def generate_wave_sound(duration=2, sample_rate=44100):
    """Generate ocean wave sound"""
    t = np.linspace(0, duration, int(duration * sample_rate))
    
    # Low frequency sine for wave motion
    wave = 0.3 * np.sin(2 * np.pi * 0.5 * t)
    
    # Add noise for foam
    noise = np.random.normal(0, 0.15, len(t))
    
    # Combine
    sound = wave + noise
    
    # Envelope
    envelope = np.exp(-t * 0.5) * np.sin(2 * np.pi * 0.3 * t)
    sound = sound * (1 + envelope)
    
    # Fade
    fade_samples = int(0.1 * sample_rate)
    fade_in = np.linspace(0, 1, fade_samples)
    fade_out = np.linspace(1, 0, fade_samples)
    
    sound[:fade_samples] *= fade_in
    sound[-fade_samples:] *= fade_out
    
    # Normalize
    sound = sound / np.max(np.abs(sound)) * 0.7
    
    return (sound * 32767).astype(np.int16)

def generate_train_sound(duration=2, sample_rate=44100):
    """Generate train sound"""
    t = np.linspace(0, duration, int(duration * sample_rate))
    
    # Low rumble
    rumble = 0.4 * np.sin(2 * np.pi * 80 * t)
    rumble += 0.2 * np.sin(2 * np.pi * 120 * t)
    
    # Rhythmic clacking
    clack_freq = 4  # Hz
    clack = 0.3 * np.sin(2 * np.pi * 400 * t) * (np.sin(2 * np.pi * clack_freq * t) > 0.7)
    
    # Combine
    sound = rumble + clack
    
    # Fade
    fade_samples = int(0.1 * sample_rate)
    fade_in = np.linspace(0, 1, fade_samples)
    fade_out = np.linspace(1, 0, fade_samples)
    
    sound[:fade_samples] *= fade_in
    sound[-fade_samples:] *= fade_out
    
    # Normalize
    sound = sound / np.max(np.abs(sound)) * 0.7
    
    return (sound * 32767).astype(np.int16)

def generate_grass_sound(duration=2, sample_rate=44100):
    """Generate grass/wind sound"""
    # Pink noise for natural wind
    noise = np.random.normal(0, 0.25, int(duration * sample_rate))
    
    # Apply band-pass filter
    from scipy import signal
    b, a = signal.butter(3, [0.1, 0.4], btype='band')
    filtered = signal.filtfilt(b, a, noise)
    
    # Add gentle modulation
    t = np.linspace(0, duration, len(filtered))
    modulation = 1 + 0.3 * np.sin(2 * np.pi * 2 * t)
    filtered = filtered * modulation
    
    # Fade
    fade_samples = int(0.1 * sample_rate)
    fade_in = np.linspace(0, 1, fade_samples)
    fade_out = np.linspace(1, 0, fade_samples)
    
    filtered[:fade_samples] *= fade_in
    filtered[-fade_samples:] *= fade_out
    
    # Normalize
    filtered = filtered / np.max(np.abs(filtered)) * 0.7
    
    return (filtered * 32767).astype(np.int16)

# Create Resources directory
resources_dir = "/Users/hyeonseong/workspace/tools/TimeTimer/TimeTimer/Resources"
os.makedirs(resources_dir, exist_ok=True)

# Generate sounds
print("Generating nature sounds...")

rain = generate_rain_sound()
wavfile.write(f"{resources_dir}/rain.wav", 44100, rain)
print("✓ Rain sound generated")

wave = generate_wave_sound()
wavfile.write(f"{resources_dir}/wave.wav", 44100, wave)
print("✓ Wave sound generated")

train = generate_train_sound()
wavfile.write(f"{resources_dir}/train.wav", 44100, train)
print("✓ Train sound generated")

grass = generate_grass_sound()
wavfile.write(f"{resources_dir}/grass.wav", 44100, grass)
print("✓ Grass/wind sound generated")

print("\nAll nature sounds generated successfully!")
