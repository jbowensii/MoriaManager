"""Generate procedural placeholder icons for the application.

These are used as fallbacks when PNG icon assets are not available.
Each function draws a simple vector icon using Pillow's ImageDraw.

Run this script directly to regenerate all icons:
    python -m moria_manager.assets.icon_generator
"""

from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Pillow is required to generate icons: pip install pillow")
    raise


# --- Individual Icon Generators ---

def create_gear_icon(size: int = 32) -> Image.Image:
    """Create a gear/cog icon with 8 teeth for the Settings button."""
    import math

    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    center = size // 2
    outer_radius = size // 2 - 2
    inner_radius = outer_radius * 0.65
    hole_radius = size // 6
    num_teeth = 8
    # Build gear shape as polygon points
    points = []
    for i in range(num_teeth * 2):
        angle = (i * math.pi / num_teeth) - math.pi / 2
        # Alternate between outer and inner radius
        if i % 2 == 0:
            # Outer point (tooth tip)
            r = outer_radius
        else:
            # Inner point (between teeth)
            r = inner_radius
        x = center + r * math.cos(angle)
        y = center + r * math.sin(angle)
        points.append((x, y))

    # Draw the gear body
    draw.polygon(points, fill=(150, 150, 150, 255))

    # Draw center hub (darker circle)
    hub_radius = inner_radius * 0.7
    draw.ellipse(
        [center - hub_radius, center - hub_radius,
         center + hub_radius, center + hub_radius],
        fill=(120, 120, 120, 255)
    )

    # Draw center hole
    draw.ellipse(
        [center - hole_radius, center - hole_radius,
         center + hole_radius, center + hole_radius],
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
    """Create the application icon â€” blue circle with a stylized 'M' for Moria."""
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


def create_materials_icon(size: int = 32) -> Image.Image:
    """Create a materials calculator icon (black and white sack/bag)."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 8

    # Sack body (rounded bottom rectangle shape)
    sack_top = margin + size // 6
    sack_bottom = size - margin
    sack_left = margin + 2
    sack_right = size - margin - 2
    sack_width = sack_right - sack_left

    # Draw main sack body - light gray fill with dark outline
    body_color = (200, 200, 200, 255)  # Light gray
    outline_color = (60, 60, 60, 255)  # Dark gray

    # Draw sack body as rounded rectangle
    draw.rounded_rectangle(
        [sack_left, sack_top, sack_right, sack_bottom],
        radius=size // 6,
        fill=body_color,
        outline=outline_color,
        width=2
    )

    # Draw tied top/neck of sack
    neck_width = sack_width // 2
    neck_left = sack_left + sack_width // 4
    neck_top = margin

    # Neck/tied part (narrower rectangle)
    draw.rectangle(
        [neck_left + 2, neck_top, neck_left + neck_width - 2, sack_top + 2],
        fill=body_color,
        outline=outline_color,
        width=1
    )

    # Draw tie/knot (horizontal line with bulge)
    tie_y = sack_top - 1
    draw.line(
        [(neck_left, tie_y), (neck_left + neck_width, tie_y)],
        fill=outline_color,
        width=2
    )

    # Draw small decorative lines on sack (texture)
    line_color = (120, 120, 120, 255)
    center_x = (sack_left + sack_right) // 2
    center_y = (sack_top + sack_bottom) // 2

    # Three horizontal lines for texture
    line_length = sack_width // 3
    for offset in [-size // 8, 0, size // 8]:
        y = center_y + offset
        draw.line(
            [(center_x - line_length // 2, y), (center_x + line_length // 2, y)],
            fill=line_color,
            width=1
        )

    return img


def create_help_icon(size: int = 32) -> Image.Image:
    """Create a greyscale book icon for the Help button."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 8
    book_left = margin
    book_right = size - margin
    book_top = margin + 2
    book_bottom = size - margin

    # Book cover (dark grey)
    cover_color = (100, 100, 100, 255)
    outline_color = (60, 60, 60, 255)

    # Draw book cover/spine
    draw.rounded_rectangle(
        [book_left, book_top, book_right, book_bottom],
        radius=2,
        fill=cover_color,
        outline=outline_color,
        width=1
    )

    # Draw spine on left side
    spine_width = size // 8
    draw.rectangle(
        [book_left, book_top, book_left + spine_width, book_bottom],
        fill=(80, 80, 80, 255),
        outline=outline_color,
        width=1
    )

    # Draw pages (lighter grey area)
    pages_color = (180, 180, 180, 255)
    pages_left = book_left + spine_width + 2
    pages_right = book_right - 3
    pages_top = book_top + 3
    pages_bottom = book_bottom - 3

    draw.rectangle(
        [pages_left, pages_top, pages_right, pages_bottom],
        fill=pages_color
    )

    # Draw page lines
    line_color = (140, 140, 140, 255)
    num_lines = 4
    line_spacing = (pages_bottom - pages_top) // (num_lines + 1)
    for i in range(1, num_lines + 1):
        y = pages_top + i * line_spacing
        draw.line(
            [(pages_left + 2, y), (pages_right - 2, y)],
            fill=line_color,
            width=1
        )

    return img


# --- Batch Generation ---

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

    # Generate toolbar backup icon (same as backup)
    toolbar_backup = create_backup_icon(32)
    toolbar_backup.save(output_dir / "toolbar_backup.png")
    print(f"Created: {output_dir / 'toolbar_backup.png'}")

    # Generate toolbar restore icon (same as restore)
    toolbar_restore = create_restore_icon(32)
    toolbar_restore.save(output_dir / "toolbar_restore.png")
    print(f"Created: {output_dir / 'toolbar_restore.png'}")

    # Generate materials icon
    materials = create_materials_icon(32)
    materials.save(output_dir / "toolbar_materials.png")
    print(f"Created: {output_dir / 'toolbar_materials.png'}")

    # Generate help icon (greyscale book)
    help_icon = create_help_icon(32)
    help_icon.save(output_dir / "help.png")
    print(f"Created: {output_dir / 'help.png'}")

    # Note: app_icon.png and app_icon.ico are based on logo.png, not generated
    # To recreate them, use:
    #   logo = Image.open(output_dir / "logo.png")
    #   logo.save(output_dir / "app_icon.png")
    #   logo.save(output_dir / "app_icon.ico", format='ICO', sizes=[(16,16),(32,32),(48,48),(256,256)])


if __name__ == "__main__":
    generate_all_icons()
