"""Generate placeholder icons for the application.

Run this script directly to generate icons:
    python -m moria_manager.assets.icon_generator
"""

from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Pillow is required to generate icons: pip install pillow")
    raise


def create_gear_icon(size: int = 32) -> Image.Image:
    """Create a simple gear icon."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    center = size // 2
    outer_radius = size // 2 - 2
    inner_radius = size // 4
    teeth = 8

    # Draw gear teeth as a circle with notches
    draw.ellipse(
        [center - outer_radius, center - outer_radius,
         center + outer_radius, center + outer_radius],
        fill=(100, 100, 100, 255)
    )

    # Draw center hole
    draw.ellipse(
        [center - inner_radius, center - inner_radius,
         center + inner_radius, center + inner_radius],
        fill=(0, 0, 0, 0)
    )

    return img


def create_backup_icon(size: int = 32) -> Image.Image:
    """Create a simple backup/save icon (floppy disk style)."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 8
    # Main body
    draw.rectangle(
        [margin, margin, size - margin, size - margin],
        fill=(70, 130, 180, 255),
        outline=(50, 100, 150, 255),
        width=1
    )

    # Label area (white rectangle at top)
    label_height = size // 3
    draw.rectangle(
        [margin + 4, margin + 2, size - margin - 4, margin + label_height],
        fill=(240, 240, 240, 255)
    )

    return img


def create_restore_icon(size: int = 32) -> Image.Image:
    """Create a simple restore icon (circular arrow)."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    center = size // 2
    radius = size // 2 - 4

    # Draw arc
    draw.arc(
        [center - radius, center - radius, center + radius, center + radius],
        start=45, end=315,
        fill=(70, 180, 70, 255),
        width=3
    )

    # Draw arrow head
    arrow_size = size // 6
    draw.polygon(
        [(center + radius - arrow_size, center - radius // 2),
         (center + radius + arrow_size // 2, center - radius // 2 - arrow_size),
         (center + radius + arrow_size // 2, center - radius // 2 + arrow_size)],
        fill=(70, 180, 70, 255)
    )

    return img


def create_app_icon(size: int = 256) -> Image.Image:
    """Create a simple application icon."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle
    margin = size // 16
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(45, 90, 140, 255)
    )

    # Draw a stylized "M" for Moria
    center = size // 2
    m_width = size // 2
    m_height = size // 3
    line_width = size // 12

    # Left vertical
    draw.rectangle(
        [center - m_width // 2, center - m_height // 2,
         center - m_width // 2 + line_width, center + m_height // 2],
        fill=(255, 255, 255, 255)
    )
    # Right vertical
    draw.rectangle(
        [center + m_width // 2 - line_width, center - m_height // 2,
         center + m_width // 2, center + m_height // 2],
        fill=(255, 255, 255, 255)
    )
    # Middle peak
    draw.polygon(
        [(center - m_width // 2, center - m_height // 2),
         (center, center),
         (center + m_width // 2, center - m_height // 2),
         (center + m_width // 2 - line_width, center - m_height // 2),
         (center, center - line_width),
         (center - m_width // 2 + line_width, center - m_height // 2)],
        fill=(255, 255, 255, 255)
    )

    return img


def generate_all_icons(output_dir: Path | None = None):
    """Generate all icons and save them to the icons directory."""
    if output_dir is None:
        output_dir = Path(__file__).parent / "icons"

    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate gear icon
    gear = create_gear_icon(32)
    gear.save(output_dir / "gear.png")
    print(f"Created: {output_dir / 'gear.png'}")

    # Generate backup icon
    backup = create_backup_icon(32)
    backup.save(output_dir / "backup.png")
    print(f"Created: {output_dir / 'backup.png'}")

    # Generate restore icon
    restore = create_restore_icon(32)
    restore.save(output_dir / "restore.png")
    print(f"Created: {output_dir / 'restore.png'}")

    # Generate app icon (multiple sizes for ICO)
    app_256 = create_app_icon(256)
    app_256.save(output_dir / "app_icon.png")
    print(f"Created: {output_dir / 'app_icon.png'}")

    # Create ICO file with multiple sizes
    app_48 = create_app_icon(48)
    app_32 = create_app_icon(32)
    app_16 = create_app_icon(16)
    app_256.save(
        output_dir / "app_icon.ico",
        format='ICO',
        sizes=[(16, 16), (32, 32), (48, 48), (256, 256)]
    )
    print(f"Created: {output_dir / 'app_icon.ico'}")


if __name__ == "__main__":
    generate_all_icons()
