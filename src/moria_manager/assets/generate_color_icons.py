"""Generate colorful versions of all icons for preview.

Run this script to generate color icons:
    python -m moria_manager.assets.generate_color_icons
"""

from pathlib import Path
import math

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Pillow is required: pip install pillow")
    raise


def create_gear_icon_color(size: int = 32) -> Image.Image:
    """Create a colorful gear/cog icon - orange/gold metallic."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    center = size // 2
    outer_radius = size // 2 - 2
    inner_radius = outer_radius * 0.65
    hole_radius = size // 6
    num_teeth = 8

    points = []
    for i in range(num_teeth * 2):
        angle = (i * math.pi / num_teeth) - math.pi / 2
        if i % 2 == 0:
            r = outer_radius
        else:
            r = inner_radius
        x = center + r * math.cos(angle)
        y = center + r * math.sin(angle)
        points.append((x, y))

    # Orange/gold gear body
    draw.polygon(points, fill=(218, 165, 32, 255))  # Goldenrod

    # Darker hub
    hub_radius = inner_radius * 0.7
    draw.ellipse(
        [center - hub_radius, center - hub_radius,
         center + hub_radius, center + hub_radius],
        fill=(184, 134, 11, 255)  # Dark goldenrod
    )

    # Center hole
    draw.ellipse(
        [center - hole_radius, center - hole_radius,
         center + hole_radius, center + hole_radius],
        fill=(0, 0, 0, 0)
    )

    return img


def create_backup_icon_color(size: int = 32) -> Image.Image:
    """Create a colorful backup icon - blue with up arrow."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 8
    
    # Blue rounded rectangle (cloud/storage shape)
    draw.rounded_rectangle(
        [margin, margin + 4, size - margin, size - margin],
        radius=4,
        fill=(65, 105, 225, 255),  # Royal blue
        outline=(30, 60, 180, 255),
        width=1
    )

    # White up arrow
    center_x = size // 2
    arrow_top = margin + 6
    arrow_bottom = size - margin - 4
    arrow_width = size // 4

    # Arrow head (triangle)
    draw.polygon([
        (center_x, arrow_top),
        (center_x - arrow_width, arrow_top + arrow_width),
        (center_x + arrow_width, arrow_top + arrow_width)
    ], fill=(255, 255, 255, 255))

    # Arrow shaft
    shaft_width = size // 6
    draw.rectangle([
        center_x - shaft_width // 2, arrow_top + arrow_width - 2,
        center_x + shaft_width // 2, arrow_bottom
    ], fill=(255, 255, 255, 255))

    return img


def create_restore_icon_color(size: int = 32) -> Image.Image:
    """Create a colorful restore icon - green with down arrow."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 8
    
    # Green rounded rectangle
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin - 4],
        radius=4,
        fill=(46, 139, 87, 255),  # Sea green
        outline=(34, 100, 64, 255),
        width=1
    )

    # White down arrow
    center_x = size // 2
    arrow_top = margin + 4
    arrow_bottom = size - margin - 6
    arrow_width = size // 4

    # Arrow shaft
    shaft_width = size // 6
    draw.rectangle([
        center_x - shaft_width // 2, arrow_top,
        center_x + shaft_width // 2, arrow_bottom - arrow_width + 2
    ], fill=(255, 255, 255, 255))

    # Arrow head (triangle pointing down)
    draw.polygon([
        (center_x, arrow_bottom),
        (center_x - arrow_width, arrow_bottom - arrow_width),
        (center_x + arrow_width, arrow_bottom - arrow_width)
    ], fill=(255, 255, 255, 255))

    return img


def create_help_icon_color(size: int = 32) -> Image.Image:
    """Create a colorful book icon - rich brown leather with gold pages."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 8
    book_left = margin
    book_right = size - margin
    book_top = margin + 2
    book_bottom = size - margin

    # Rich brown leather cover
    cover_color = (139, 69, 19, 255)  # Saddle brown
    outline_color = (101, 67, 33, 255)  # Dark brown

    draw.rounded_rectangle(
        [book_left, book_top, book_right, book_bottom],
        radius=2,
        fill=cover_color,
        outline=outline_color,
        width=1
    )

    # Darker spine
    spine_width = size // 8
    draw.rectangle(
        [book_left, book_top, book_left + spine_width, book_bottom],
        fill=(101, 67, 33, 255),
        outline=outline_color,
        width=1
    )

    # Cream/gold pages
    pages_color = (255, 248, 220, 255)  # Cornsilk
    pages_left = book_left + spine_width + 2
    pages_right = book_right - 3
    pages_top = book_top + 3
    pages_bottom = book_bottom - 3

    draw.rectangle(
        [pages_left, pages_top, pages_right, pages_bottom],
        fill=pages_color
    )

    # Gold page lines
    line_color = (218, 165, 32, 255)  # Goldenrod
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


def create_materials_icon_color(size: int = 32) -> Image.Image:
    """Create a colorful materials icon - tan burlap sack with gold coins."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 8
    sack_top = margin + size // 6
    sack_bottom = size - margin
    sack_left = margin + 2
    sack_right = size - margin - 2
    sack_width = sack_right - sack_left

    # Tan/burlap sack body
    body_color = (210, 180, 140, 255)  # Tan
    outline_color = (139, 119, 101, 255)  # Rosy brown

    draw.rounded_rectangle(
        [sack_left, sack_top, sack_right, sack_bottom],
        radius=size // 6,
        fill=body_color,
        outline=outline_color,
        width=2
    )

    # Neck
    neck_width = sack_width // 2
    neck_left = sack_left + sack_width // 4
    neck_top = margin

    draw.rectangle(
        [neck_left + 2, neck_top, neck_left + neck_width - 2, sack_top + 2],
        fill=body_color,
        outline=outline_color,
        width=1
    )

    # Red tie/ribbon
    tie_y = sack_top - 1
    draw.line(
        [(neck_left, tie_y), (neck_left + neck_width, tie_y)],
        fill=(178, 34, 34, 255),  # Firebrick red
        width=3
    )

    # Gold coin peeking out
    coin_x = (sack_left + sack_right) // 2
    coin_y = (sack_top + sack_bottom) // 2
    coin_r = size // 8
    draw.ellipse(
        [coin_x - coin_r, coin_y - coin_r, coin_x + coin_r, coin_y + coin_r],
        fill=(255, 215, 0, 255),  # Gold
        outline=(184, 134, 11, 255),  # Dark goldenrod
        width=1
    )

    return img


def create_trash_icon_color(size: int = 32) -> Image.Image:
    """Create a colorful trash icon - red trash can."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 6
    
    # Lid
    lid_height = size // 6
    draw.rounded_rectangle(
        [margin - 2, margin, size - margin + 2, margin + lid_height],
        radius=2,
        fill=(220, 20, 60, 255),  # Crimson
        outline=(139, 0, 0, 255),  # Dark red
        width=1
    )

    # Lid handle
    handle_width = size // 4
    handle_height = size // 10
    center_x = size // 2
    draw.rounded_rectangle(
        [center_x - handle_width // 2, margin - handle_height,
         center_x + handle_width // 2, margin + 2],
        radius=2,
        fill=(220, 20, 60, 255),
        outline=(139, 0, 0, 255),
        width=1
    )

    # Can body
    body_top = margin + lid_height + 1
    body_bottom = size - margin
    draw.rounded_rectangle(
        [margin, body_top, size - margin, body_bottom],
        radius=2,
        fill=(220, 20, 60, 255),
        outline=(139, 0, 0, 255),
        width=1
    )

    # Vertical lines on can
    line_color = (139, 0, 0, 255)
    num_lines = 3
    spacing = (size - 2 * margin) // (num_lines + 1)
    for i in range(1, num_lines + 1):
        x = margin + i * spacing
        draw.line(
            [(x, body_top + 2), (x, body_bottom - 2)],
            fill=line_color,
            width=1
        )

    return img


def create_import_icon_color(size: int = 32) -> Image.Image:
    """Create a colorful import icon - purple folder with arrow."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 8
    
    # Folder back
    folder_top = margin + 4
    tab_height = size // 6
    tab_width = size // 3
    
    draw.polygon([
        (margin, folder_top + tab_height),
        (margin, size - margin),
        (size - margin, size - margin),
        (size - margin, folder_top + tab_height),
        (margin + tab_width + 4, folder_top + tab_height),
        (margin + tab_width, folder_top),
        (margin, folder_top),
    ], fill=(138, 43, 226, 255), outline=(75, 0, 130, 255))  # Blue violet

    # Arrow pointing into folder
    center_x = size // 2
    arrow_top = folder_top + tab_height + 4
    arrow_bottom = size - margin - 4
    arrow_width = size // 5

    # Arrow head
    draw.polygon([
        (center_x, arrow_bottom),
        (center_x - arrow_width, arrow_bottom - arrow_width),
        (center_x + arrow_width, arrow_bottom - arrow_width)
    ], fill=(255, 255, 255, 255))

    # Arrow shaft
    shaft_width = size // 8
    draw.rectangle([
        center_x - shaft_width // 2, arrow_top,
        center_x + shaft_width // 2, arrow_bottom - arrow_width + 2
    ], fill=(255, 255, 255, 255))

    return img


def create_backup_all_icon_color(size: int = 32) -> Image.Image:
    """Create a colorful backup-all icon - blue with double up arrows."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 8
    
    # Blue rounded rectangle
    draw.rounded_rectangle(
        [margin, margin + 4, size - margin, size - margin],
        radius=4,
        fill=(65, 105, 225, 255),  # Royal blue
        outline=(30, 60, 180, 255),
        width=1
    )

    # Double white up arrows
    center_x = size // 2
    arrow_width = size // 5

    # First arrow (top)
    arrow1_top = margin + 5
    draw.polygon([
        (center_x, arrow1_top),
        (center_x - arrow_width, arrow1_top + arrow_width),
        (center_x + arrow_width, arrow1_top + arrow_width)
    ], fill=(255, 255, 255, 255))

    # Second arrow (bottom)
    arrow2_top = margin + 5 + arrow_width + 2
    draw.polygon([
        (center_x, arrow2_top),
        (center_x - arrow_width, arrow2_top + arrow_width),
        (center_x + arrow_width, arrow2_top + arrow_width)
    ], fill=(255, 255, 255, 255))

    return img


def create_restore_green_icon_color(size: int = 32) -> Image.Image:
    """Create a bright green restore icon for 'restore to game' action."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 8
    
    # Bright green rounded rectangle
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin - 4],
        radius=4,
        fill=(50, 205, 50, 255),  # Lime green
        outline=(34, 139, 34, 255),  # Forest green
        width=1
    )

    # White down arrow
    center_x = size // 2
    arrow_top = margin + 4
    arrow_bottom = size - margin - 6
    arrow_width = size // 4

    # Arrow shaft
    shaft_width = size // 6
    draw.rectangle([
        center_x - shaft_width // 2, arrow_top,
        center_x + shaft_width // 2, arrow_bottom - arrow_width + 2
    ], fill=(255, 255, 255, 255))

    # Arrow head
    draw.polygon([
        (center_x, arrow_bottom),
        (center_x - arrow_width, arrow_bottom - arrow_width),
        (center_x + arrow_width, arrow_bottom - arrow_width)
    ], fill=(255, 255, 255, 255))

    return img


def create_mark_bad_icon_color(size: int = 32) -> Image.Image:
    """Create an orange/yellow warning X icon for marking saves as bad."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 6
    
    # Orange circle background
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(255, 140, 0, 255),  # Dark orange
        outline=(205, 92, 0, 255),
        width=1
    )

    # White X
    x_margin = size // 4
    line_width = max(2, size // 10)
    
    # Draw X with two lines
    draw.line(
        [(x_margin, x_margin), (size - x_margin, size - x_margin)],
        fill=(255, 255, 255, 255),
        width=line_width
    )
    draw.line(
        [(size - x_margin, x_margin), (x_margin, size - x_margin)],
        fill=(255, 255, 255, 255),
        width=line_width
    )

    return img


def create_toolbar_mods_icon_color(size: int = 32) -> Image.Image:
    """Create a colorful mods icon - cyan puzzle piece."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 6
    
    # Puzzle piece shape (simplified)
    # Main body
    body_left = margin
    body_right = size - margin
    body_top = margin + size // 8
    body_bottom = size - margin
    
    # Cyan/teal color
    fill_color = (0, 191, 255, 255)  # Deep sky blue
    outline_color = (0, 139, 139, 255)  # Dark cyan
    
    # Draw main rectangle body
    draw.rounded_rectangle(
        [body_left, body_top, body_right, body_bottom],
        radius=3,
        fill=fill_color,
        outline=outline_color,
        width=1
    )
    
    # Draw puzzle tab on top (circle bump)
    tab_radius = size // 8
    tab_center_x = size // 2
    tab_center_y = body_top
    draw.ellipse(
        [tab_center_x - tab_radius, tab_center_y - tab_radius,
         tab_center_x + tab_radius, tab_center_y + tab_radius],
        fill=fill_color,
        outline=outline_color,
        width=1
    )
    
    # Draw puzzle hole on right side (darker circle)
    hole_radius = size // 10
    hole_center_x = body_right
    hole_center_y = (body_top + body_bottom) // 2
    draw.ellipse(
        [hole_center_x - hole_radius, hole_center_y - hole_radius,
         hole_center_x + hole_radius, hole_center_y + hole_radius],
        fill=outline_color
    )

    return img


def create_toolbar_servers_icon_color(size: int = 32) -> Image.Image:
    """Create a colorful servers icon - purple server stack."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 6
    server_height = (size - 2 * margin) // 3 - 2
    
    # Purple colors
    fill_color = (147, 112, 219, 255)  # Medium purple
    outline_color = (75, 0, 130, 255)  # Indigo
    
    # Draw 3 stacked server units
    for i in range(3):
        top = margin + i * (server_height + 3)
        bottom = top + server_height
        
        draw.rounded_rectangle(
            [margin, top, size - margin, bottom],
            radius=2,
            fill=fill_color,
            outline=outline_color,
            width=1
        )
        
        # Status light
        light_y = (top + bottom) // 2
        light_r = 2
        draw.ellipse(
            [size - margin - 6 - light_r, light_y - light_r,
             size - margin - 6 + light_r, light_y + light_r],
            fill=(50, 205, 50, 255)  # Green light
        )

    return img


def create_toolbar_trade_icon_color(size: int = 32) -> Image.Image:
    """Create a colorful trade icon - gold coins with exchange arrows."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Gold coin colors
    gold = (255, 215, 0, 255)
    gold_dark = (184, 134, 11, 255)
    
    margin = size // 6
    
    # Draw two overlapping coins
    coin1_center = (size // 2 - 4, size // 2 + 2)
    coin2_center = (size // 2 + 4, size // 2 - 2)
    coin_radius = size // 4
    
    # Back coin
    draw.ellipse(
        [coin1_center[0] - coin_radius, coin1_center[1] - coin_radius,
         coin1_center[0] + coin_radius, coin1_center[1] + coin_radius],
        fill=gold_dark,
        outline=(139, 90, 0, 255),
        width=1
    )
    
    # Front coin
    draw.ellipse(
        [coin2_center[0] - coin_radius, coin2_center[1] - coin_radius,
         coin2_center[0] + coin_radius, coin2_center[1] + coin_radius],
        fill=gold,
        outline=gold_dark,
        width=1
    )
    
    # Small exchange arrows in corner
    arrow_color = (34, 139, 34, 255)  # Forest green
    # Right arrow at top
    draw.polygon([
        (size - margin - 2, margin + 2),
        (size - margin - 6, margin),
        (size - margin - 6, margin + 4)
    ], fill=arrow_color)
    # Left arrow at bottom
    draw.polygon([
        (margin + 2, size - margin - 2),
        (margin + 6, size - margin - 4),
        (margin + 6, size - margin)
    ], fill=arrow_color)

    return img


def create_install_to_game_icon_color(size: int = 32) -> Image.Image:
    """Create a solid left-pointing arrow icon for Install to Game - green."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 6
    
    # Green solid left arrow
    arrow_color = (50, 205, 50, 255)  # Lime green
    
    center_y = size // 2
    arrow_left = margin
    arrow_right = size - margin
    arrow_height = size // 3
    
    # Solid left-pointing arrow (chevron style)
    draw.polygon([
        (arrow_left, center_y),  # Left point
        (arrow_left + arrow_height, center_y - arrow_height),  # Top
        (arrow_left + arrow_height, center_y - arrow_height // 3),  # Top inner
        (arrow_right, center_y - arrow_height // 3),  # Top right
        (arrow_right, center_y + arrow_height // 3),  # Bottom right
        (arrow_left + arrow_height, center_y + arrow_height // 3),  # Bottom inner
        (arrow_left + arrow_height, center_y + arrow_height),  # Bottom
    ], fill=arrow_color)

    return img


def create_move_to_available_icon_color(size: int = 32) -> Image.Image:
    """Create a solid right-pointing arrow icon for Move to Available - blue."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size // 6
    
    # Blue solid right arrow
    arrow_color = (65, 105, 225, 255)  # Royal blue
    
    center_y = size // 2
    arrow_left = margin
    arrow_right = size - margin
    arrow_height = size // 3
    
    # Solid right-pointing arrow (chevron style)
    draw.polygon([
        (arrow_right, center_y),  # Right point
        (arrow_right - arrow_height, center_y - arrow_height),  # Top
        (arrow_right - arrow_height, center_y - arrow_height // 3),  # Top inner
        (arrow_left, center_y - arrow_height // 3),  # Top left
        (arrow_left, center_y + arrow_height // 3),  # Bottom left
        (arrow_right - arrow_height, center_y + arrow_height // 3),  # Bottom inner
        (arrow_right - arrow_height, center_y + arrow_height),  # Bottom
    ], fill=arrow_color)

    return img


def create_pencil_icon_color(size: int = 32) -> Image.Image:
    """Create a colorful pencil/edit icon - simple diagonal pencil."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Colors
    pencil_yellow = (255, 200, 50, 255)  # Classic yellow pencil
    pencil_outline = (180, 140, 30, 255)  # Darker outline
    wood_color = (210, 160, 100, 255)  # Tan wood
    graphite = (60, 60, 60, 255)  # Dark graphite tip
    eraser_pink = (255, 150, 170, 255)  # Pink eraser
    metal_band = (180, 180, 190, 255)  # Metal ferrule

    # Pencil runs from bottom-left to top-right at 45 degrees
    # Use line width for pencil thickness
    pencil_width = size // 5

    # Key points along the pencil diagonal
    tip_x, tip_y = 4, size - 4  # Bottom-left tip
    eraser_x, eraser_y = size - 4, 4  # Top-right eraser end

    # Draw main pencil body (yellow) as a thick line
    draw.line([(tip_x + 6, tip_y - 6), (eraser_x - 4, eraser_y + 4)],
              fill=pencil_yellow, width=pencil_width)

    # Draw wood/sharpened part near tip
    draw.line([(tip_x + 2, tip_y - 2), (tip_x + 6, tip_y - 6)],
              fill=wood_color, width=pencil_width)

    # Draw graphite tip point
    draw.polygon([
        (tip_x, tip_y),
        (tip_x + 3, tip_y - 5),
        (tip_x + 5, tip_y - 3),
    ], fill=graphite)

    # Draw metal ferrule band
    draw.line([(eraser_x - 6, eraser_y + 6), (eraser_x - 4, eraser_y + 4)],
              fill=metal_band, width=pencil_width)

    # Draw pink eraser at end
    draw.line([(eraser_x - 4, eraser_y + 4), (eraser_x, eraser_y)],
              fill=eraser_pink, width=pencil_width)

    # Add outline for definition
    # Left edge of pencil
    draw.line([(tip_x + 1, tip_y - 4), (eraser_x - 5, eraser_y + 2)],
              fill=pencil_outline, width=1)
    # Right edge of pencil
    draw.line([(tip_x + 5, tip_y), (eraser_x - 1, eraser_y + 6)],
              fill=pencil_outline, width=1)

    return img


def generate_all_color_icons():
    """Generate all color icons and save them."""
    output_dir = Path(__file__).parent / "icons"
    output_dir.mkdir(parents=True, exist_ok=True)

    icons = [
        ("gear.png", create_gear_icon_color(32)),
        ("backup.png", create_backup_icon_color(32)),
        ("restore.png", create_restore_icon_color(32)),
        ("toolbar_backup.png", create_backup_icon_color(32)),
        ("toolbar_restore.png", create_restore_icon_color(32)),
        ("help.png", create_help_icon_color(32)),
        ("toolbar_materials.png", create_materials_icon_color(32)),
        ("trash.png", create_trash_icon_color(32)),
        ("import.png", create_import_icon_color(32)),
        ("backup_all.png", create_backup_all_icon_color(32)),
        ("restore_green.png", create_restore_green_icon_color(32)),
        ("mark_bad.png", create_mark_bad_icon_color(32)),
        ("toolbar_mods.png", create_toolbar_mods_icon_color(32)),
        ("toolbar_servers.png", create_toolbar_servers_icon_color(32)),
        ("toolbar_trade.png", create_toolbar_trade_icon_color(32)),
        ("install_to_game.png", create_install_to_game_icon_color(32)),
        ("move_to_available.png", create_move_to_available_icon_color(32)),
        ("pencil.png", create_pencil_icon_color(32)),
    ]

    for name, icon in icons:
        icon.save(output_dir / name)
        print(f"Created: {output_dir / name}")

    print("\nColor palette used:")
    print("  Gear: Gold/Goldenrod")
    print("  Backup/Toolbar Backup: Royal Blue with white arrow up")
    print("  Restore/Toolbar Restore: Sea Green with white arrow down")
    print("  Help: Saddle Brown leather book with cream pages")
    print("  Materials: Tan burlap sack with gold coin")
    print("  Trash: Crimson red trash can")
    print("  Import: Blue Violet folder with white arrow")
    print("  Backup All: Royal Blue with double white arrows")
    print("  Restore Green: Lime Green with white arrow down (restore to game)")
    print("  Mark Bad: Dark Orange circle with white X (mark save as bad)")
    print("  Toolbar Mods: Cyan puzzle piece")
    print("  Toolbar Servers: Purple server stack")
    print("  Toolbar Trade: Gold coins with exchange arrows")
    print("  Install to Game: Lime green left arrow")
    print("  Move to Available: Royal blue right arrow")


if __name__ == "__main__":
    generate_all_color_icons()
