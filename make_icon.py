#!/usr/bin/env python3
"""Generate a simple app icon as .icns using PIL or fallback to sips."""
import subprocess
import tempfile
import os
import struct

def create_icon_png(path, size=512):
    """Create a simple icon PNG using Python (no dependencies)."""
    # We'll create a minimal icon script and use macOS sips to convert
    # First create a simple SVG and convert it
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#1a1a2e"/>
      <stop offset="100%" style="stop-color:#16213e"/>
    </linearGradient>
    <linearGradient id="bolt" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#00d4ff"/>
      <stop offset="100%" style="stop-color:#00d26a"/>
    </linearGradient>
  </defs>
  <!-- Rounded rect bg -->
  <rect x="10" y="10" width="{size-20}" height="{size-20}" rx="90" ry="90" fill="url(#bg)" stroke="#2a2a4a" stroke-width="4"/>
  <!-- Lightning bolt -->
  <polygon points="270,100 200,270 260,270 230,420 330,230 270,230 300,100" fill="url(#bolt)" opacity="0.95"/>
  <!-- Glow effect -->
  <polygon points="270,100 200,270 260,270 230,420 330,230 270,230 300,100" fill="url(#bolt)" opacity="0.3" filter="url(#blur)"/>
</svg>'''

    svg_path = os.path.join(os.path.dirname(path), "icon.svg")
    with open(svg_path, "w") as f:
        f.write(svg)

    # Use qlmanage or sips to convert SVG to PNG  
    # Actually, let's use a simpler approach - create iconset
    return svg_path


def create_icns(output_dir):
    """Create .icns file using iconutil."""
    iconset_dir = os.path.join(output_dir, "AppIcon.iconset")
    os.makedirs(iconset_dir, exist_ok=True)

    # Create SVG first
    svg_path = create_icon_png(os.path.join(output_dir, "icon.png"))

    # Use rsvg-convert or qlmanage to make PNGs at various sizes
    sizes = [16, 32, 64, 128, 256, 512]

    for s in sizes:
        png_name = f"icon_{s}x{s}.png"
        png_path = os.path.join(iconset_dir, png_name)

        # Try using qlmanage (built-in macOS)
        try:
            subprocess.run(
                ["qlmanage", "-t", "-s", str(s), "-o", iconset_dir, svg_path],
                capture_output=True, timeout=10
            )
            # qlmanage outputs as filename.svg.png
            ql_output = os.path.join(iconset_dir, "icon.svg.png")
            if os.path.exists(ql_output):
                os.rename(ql_output, png_path)
        except Exception:
            pass

    # Now create the iconset with proper names
    icon_files = {}
    for s in sizes:
        src = os.path.join(iconset_dir, f"icon_{s}x{s}.png")
        if os.path.exists(src):
            # Standard resolution
            dst = os.path.join(iconset_dir, f"icon_{s}x{s}.png")
            icon_files[s] = dst

    # Try iconutil
    icns_path = os.path.join(output_dir, "AppIcon.icns")
    try:
        subprocess.run(
            ["iconutil", "-c", "icns", iconset_dir, "-o", icns_path],
            capture_output=True, timeout=10
        )
        if os.path.exists(icns_path):
            return icns_path
    except Exception:
        pass

    return None


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    result = create_icns(script_dir)
    if result:
        print(f"Created: {result}")
    else:
        print("Could not create .icns (icon will use default)")
