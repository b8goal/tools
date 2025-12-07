#!/usr/bin/env python3
"""
Generate modern and trendy alarm sounds for Time Timer
"""
import numpy as np
from scipy.io import wavfile
from scipy import signal
import os

def generate_digital_chime(duration=2, sample_rate=44100):
    """Modern digital chime sound"""
    t = np.linspace(0, duration, int(duration * sample_rate))
    
    # Ascending chime notes (C-E-G major chord)
    freqs = [523.25, 659.25, 783.99]  # C5, E5, G5
    sound = np.zeros_like(t)
    
    for i, freq in enumerate(freqs):
        start = i * 0.15
        note_t = t - start
        note = np.where(note_t >= 0, 
                       np.sin(2 * np.pi * freq * note_t) * np.exp(-note_t * 3),
                       0)
        sound += note * 0.3
    
    # Normalize
    sound = sound / np.max(np.abs(sound)) * 0.7
    return (sound * 32767).astype(np.int16)

def generate_soft_bell(duration=2, sample_rate=44100):
    """Soft bell sound"""
    t = np.linspace(0, duration, int(duration * sample_rate))
    
    # Bell harmonics
    fundamental = 800
    sound = (0.5 * np.sin(2 * np.pi * fundamental * t) +
             0.3 * np.sin(2 * np.pi * fundamental * 2 * t) +
             0.2 * np.sin(2 * np.pi * fundamental * 3 * t))
    
    # Gentle decay
    envelope = np.exp(-t * 1.5)
    sound = sound * envelope
    
    # Normalize
    sound = sound / np.max(np.abs(sound)) * 0.7
    return (sound * 32767).astype(np.int16)

def generate_ambient_rise(duration=2, sample_rate=44100):
    """Ambient rising sound"""
    t = np.linspace(0, duration, int(duration * sample_rate))
    
    # Rising frequency sweep
    freq_start = 200
    freq_end = 800
    freq = freq_start + (freq_end - freq_start) * (t / duration)
    
    phase = 2 * np.pi * np.cumsum(freq) / sample_rate
    sound = np.sin(phase)
    
    # Smooth envelope
    envelope = np.sin(np.pi * t / duration) ** 2
    sound = sound * envelope * 0.6
    
    # Normalize
    sound = sound / np.max(np.abs(sound)) * 0.7
    return (sound * 32767).astype(np.int16)

def generate_crystal(duration=2, sample_rate=44100):
    """Crystal/glass sound"""
    t = np.linspace(0, duration, int(duration * sample_rate))
    
    # High frequency harmonics
    freqs = [2000, 2500, 3000, 3500]
    sound = np.zeros_like(t)
    
    for i, freq in enumerate(freqs):
        harmonic = np.sin(2 * np.pi * freq * t) * (0.3 / (i + 1))
        sound += harmonic
    
    # Sharp attack, long decay
    envelope = np.exp(-t * 2)
    sound = sound * envelope
    
    # Normalize
    sound = sound / np.max(np.abs(sound)) * 0.7
    return (sound * 32767).astype(np.int16)

def generate_zen_bowl(duration=2, sample_rate=44100):
    """Zen singing bowl sound"""
    t = np.linspace(0, duration, int(duration * sample_rate))
    
    # Low fundamental with harmonics
    fundamental = 300
    sound = (0.6 * np.sin(2 * np.pi * fundamental * t) +
             0.3 * np.sin(2 * np.pi * fundamental * 2.1 * t) +
             0.2 * np.sin(2 * np.pi * fundamental * 3.2 * t))
    
    # Very slow decay
    envelope = np.exp(-t * 0.8)
    sound = sound * envelope
    
    # Normalize
    sound = sound / np.max(np.abs(sound)) * 0.7
    return (sound * 32767).astype(np.int16)

# Trendy alarm app sounds
def generate_gentle_wake(duration=2, sample_rate=44100):
    """Gentle wake-up sound (like iOS Radar)"""
    t = np.linspace(0, duration, int(duration * sample_rate))
    
    # Soft ascending tones
    freqs = [440, 554.37, 659.25]  # A4, C#5, E5
    sound = np.zeros_like(t)
    
    for i, freq in enumerate(freqs):
        start = i * 0.3
        note_t = t - start
        note = np.where(note_t >= 0,
                       np.sin(2 * np.pi * freq * note_t) * np.exp(-note_t * 1.5),
                       0)
        sound += note * 0.35
    
    # Normalize
    sound = sound / np.max(np.abs(sound)) * 0.7
    return (sound * 32767).astype(np.int16)

def generate_morning_birds(duration=2, sample_rate=44100):
    """Morning birds chirping"""
    t = np.linspace(0, duration, int(duration * sample_rate))
    sound = np.zeros_like(t)
    
    # Multiple chirps at different frequencies
    chirp_times = [0, 0.4, 0.8, 1.2]
    base_freqs = [2000, 2200, 1800, 2100]
    
    for chirp_time, base_freq in zip(chirp_times, base_freqs):
        chirp_t = t - chirp_time
        # Frequency modulation for chirp
        freq_mod = base_freq + 500 * np.sin(2 * np.pi * 10 * chirp_t)
        phase = 2 * np.pi * np.cumsum(freq_mod) / sample_rate
        
        chirp = np.where(
            (chirp_t >= 0) & (chirp_t < 0.15),
            np.sin(phase) * np.exp(-chirp_t * 15),
            0
        )
        sound += chirp * 0.3
    
    # Normalize
    sound = sound / np.max(np.abs(sound)) * 0.7
    return (sound * 32767).astype(np.int16)

def generate_harp_glissando(duration=2, sample_rate=44100):
    """Harp glissando (like iOS Harp)"""
    t = np.linspace(0, duration, int(duration * sample_rate))
    
    # C major scale ascending
    freqs = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
    sound = np.zeros_like(t)
    
    for i, freq in enumerate(freqs):
        start = i * 0.12
        note_t = t - start
        note = np.where(note_t >= 0,
                       np.sin(2 * np.pi * freq * note_t) * np.exp(-note_t * 4),
                       0)
        sound += note * 0.25
    
    # Normalize
    sound = sound / np.max(np.abs(sound)) * 0.7
    return (sound * 32767).astype(np.int16)

def generate_marimba(duration=2, sample_rate=44100):
    """Marimba sound (popular in alarm apps)"""
    t = np.linspace(0, duration, int(duration * sample_rate))
    
    # Marimba notes
    freqs = [523.25, 659.25, 783.99, 1046.50]  # C5, E5, G5, C6
    sound = np.zeros_like(t)
    
    for i, freq in enumerate(freqs):
        start = i * 0.2
        note_t = t - start
        # Marimba has strong odd harmonics
        note = np.where(note_t >= 0,
                       (np.sin(2 * np.pi * freq * note_t) +
                        0.3 * np.sin(2 * np.pi * freq * 3 * note_t)) * 
                       np.exp(-note_t * 5),
                       0)
        sound += note * 0.3
    
    # Normalize
    sound = sound / np.max(np.abs(sound)) * 0.7
    return (sound * 32767).astype(np.int16)

def generate_xylophone(duration=2, sample_rate=44100):
    """Xylophone sound"""
    t = np.linspace(0, duration, int(duration * sample_rate))
    
    # Bright xylophone notes
    freqs = [1046.50, 1174.66, 1318.51, 1567.98]  # C6, D6, E6, G6
    sound = np.zeros_like(t)
    
    for i, freq in enumerate(freqs):
        start = i * 0.18
        note_t = t - start
        note = np.where(note_t >= 0,
                       np.sin(2 * np.pi * freq * note_t) * np.exp(-note_t * 8),
                       0)
        sound += note * 0.3
    
    # Normalize
    sound = sound / np.max(np.abs(sound)) * 0.7
    return (sound * 32767).astype(np.int16)

# Create Resources directory
resources_dir = "/Users/hyeonseong/workspace/tools/TimeTimer/TimeTimer/Resources"
os.makedirs(resources_dir, exist_ok=True)

print("Generating modern sounds...")

# Modern sounds
digital_chime = generate_digital_chime()
wavfile.write(f"{resources_dir}/digital_chime.wav", 44100, digital_chime)
print("✓ Digital Chime")

soft_bell = generate_soft_bell()
wavfile.write(f"{resources_dir}/soft_bell.wav", 44100, soft_bell)
print("✓ Soft Bell")

ambient_rise = generate_ambient_rise()
wavfile.write(f"{resources_dir}/ambient_rise.wav", 44100, ambient_rise)
print("✓ Ambient Rise")

crystal = generate_crystal()
wavfile.write(f"{resources_dir}/crystal.wav", 44100, crystal)
print("✓ Crystal")

zen_bowl = generate_zen_bowl()
wavfile.write(f"{resources_dir}/zen_bowl.wav", 44100, zen_bowl)
print("✓ Zen Bowl")

print("\nGenerating trendy alarm sounds...")

# Trendy alarm sounds
gentle_wake = generate_gentle_wake()
wavfile.write(f"{resources_dir}/gentle_wake.wav", 44100, gentle_wake)
print("✓ Gentle Wake")

morning_birds = generate_morning_birds()
wavfile.write(f"{resources_dir}/morning_birds.wav", 44100, morning_birds)
print("✓ Morning Birds")

harp = generate_harp_glissando()
wavfile.write(f"{resources_dir}/harp.wav", 44100, harp)
print("✓ Harp")

marimba = generate_marimba()
wavfile.write(f"{resources_dir}/marimba.wav", 44100, marimba)
print("✓ Marimba")

xylophone = generate_xylophone()
wavfile.write(f"{resources_dir}/xylophone.wav", 44100, xylophone)
print("✓ Xylophone")

print("\n✅ All modern and trendy sounds generated successfully!")
