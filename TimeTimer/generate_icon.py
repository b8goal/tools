#!/usr/bin/env python3
"""
Generate vibrant, modern app icon for Time Timer
"""
from PIL import Image, ImageDraw, ImageFilter
import math

def create_vibrant_timer_icon(size):
    """Create a vibrant, modern timer icon with 3D effect"""
    # Create image with transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    center = size // 2
    
    # Background gradient circle (dark to vibrant)
    for r in range(int(size * 0.48), 0, -1):
        # Radial gradient from dark purple to bright blue
        ratio = r / (size * 0.48)
        
        # Vibrant gradient colors
        if ratio > 0.7:
            # Outer: Deep purple
            color_r = int(80 + (120 - 80) * (1 - ratio) / 0.3)
            color_g = int(40 + (80 - 40) * (1 - ratio) / 0.3)
            color_b = int(140 + (200 - 140) * (1 - ratio) / 0.3)
        else:
            # Inner: Bright cyan/blue
            color_r = int(120 + (60 - 120) * ratio / 0.7)
            color_g = int(80 + (180 - 80) * ratio / 0.7)
            color_b = int(200 + (255 - 200) * ratio / 0.7)
        
        color = (color_r, color_g, color_b, 255)
        draw.ellipse([center - r, center - r, center + r, center + r], fill=color)
    
    # Create timer arc with vibrant gradient
    arc_width = int(size * 0.12)
    outer_radius = int(size * 0.44)
    inner_radius = outer_radius - arc_width
    
    # Draw vibrant arc (270 degrees)
    arc_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    arc_draw = ImageDraw.Draw(arc_img)
    
    for angle in range(270):
        # Vibrant gradient from cyan to magenta
        ratio = angle / 270
        
        # Cyan -> Blue -> Purple -> Magenta
        if ratio < 0.33:
            # Cyan to Blue
            t = ratio / 0.33
            r = int(0 + (100 - 0) * t)
            g = int(255 + (150 - 255) * t)
            b = int(255)
        elif ratio < 0.66:
            # Blue to Purple
            t = (ratio - 0.33) / 0.33
            r = int(100 + (180 - 100) * t)
            g = int(150 + (80 - 150) * t)
            b = int(255)
        else:
            # Purple to Magenta
            t = (ratio - 0.66) / 0.34
            r = int(180 + (255 - 180) * t)
            g = int(80 + (50 - 80) * t)
            b = int(255 + (200 - 255) * t)
        
        color = (r, g, b, 255)
        
        # Calculate arc position
        rad = math.radians(angle - 135)  # Start from top
        
        # Draw thick line for arc
        for radius in range(inner_radius, outer_radius, 2):
            x = center + int(radius * math.cos(rad))
            y = center + int(radius * math.sin(rad))
            
            # Draw multiple points for smooth arc
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    if 0 <= x + dx < size and 0 <= y + dy < size:
                        arc_draw.point((x + dx, y + dy), fill=color)
    
    # Apply slight blur for smooth gradient
    arc_img = arc_img.filter(ImageFilter.GaussianBlur(radius=1))
    
    # Composite arc onto main image
    img = Image.alpha_composite(img, arc_img)
    
    # Add bright highlight on arc (3D effect)
    highlight_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    highlight_draw = ImageDraw.Draw(highlight_img)
    
    for angle in range(60):  # Highlight on top-left
        rad = math.radians(angle - 135)
        
        # White highlight
        alpha = int(100 * (1 - angle / 60))
        color = (255, 255, 255, alpha)
        
        for radius in range(outer_radius - arc_width // 2, outer_radius):
            x = center + int(radius * math.cos(rad))
            y = center + int(radius * math.sin(rad))
            
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    if 0 <= x + dx < size and 0 <= y + dy < size:
                        highlight_draw.point((x + dx, y + dy), fill=color)
    
    img = Image.alpha_composite(img, highlight_img)
    
    # Center dot with glow
    dot_radius = int(size * 0.08)
    
    # Glow effect
    for r in range(dot_radius + 10, dot_radius - 1, -1):
        alpha = int(150 * (1 - (r - dot_radius) / 10)) if r > dot_radius else 255
        glow_color = (255, 100, 255, alpha)
        draw.ellipse([center - r, center - r, center + r, center + r], fill=glow_color)
    
    # Bright center dot
    draw.ellipse([center - dot_radius, center - dot_radius,
                  center + dot_radius, center + dot_radius],
                 fill=(255, 255, 255, 255))
    
    # Add subtle shadow for depth
    shadow = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_offset = int(size * 0.02)
    shadow_draw.ellipse([shadow_offset, shadow_offset, 
                         size - shadow_offset, size - shadow_offset],
                        fill=(0, 0, 0, 30))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=size // 40))
    
    # Composite shadow behind
    final = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    final = Image.alpha_composite(final, shadow)
    final = Image.alpha_composite(final, img)
    
    return final

# Generate icons for all required sizes
sizes = [16, 32, 64, 128, 256, 512, 1024]

for size in sizes:
    icon = create_vibrant_timer_icon(size)
    filename = f"/Users/hyeonseong/workspace/tools/TimeTimer/TimeTimer/Assets.xcassets/AppIcon.appiconset/icon_{size}.png"
    icon.save(filename, 'PNG')
    print(f"✓ Generated vibrant {size}x{size} icon")

print("\n🎨 All vibrant icons generated successfully!")
