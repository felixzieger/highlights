from PIL import Image
import os
import glob
from collections import Counter
import colorsys
import argparse


def get_dominant_colors(image_path, num_colors=3):
    """Extract dominant colors from an image."""
    try:
        # Open and resize image for faster processing
        img = Image.open(image_path)
        img = img.resize((150, 150))

        # Convert to RGB if necessary
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Get colors from image
        pixels = list(img.getdata())
        color_counts = Counter(pixels)

        # Sort by count and get top colors
        dominant_colors = sorted(color_counts.items(), key=lambda x: x[1], reverse=True)
        return [color for color, count in dominant_colors[:num_colors]]
    except Exception as e:
        print(f"Error processing {image_path}: {str(e)}")
        return get_fallback_colors()


def get_fallback_colors():
    """Generate a pleasing color palette for books without covers."""
    return [
        (158, 158, 158),  # Mid gray
        (108, 108, 108),  # Darker gray
        (198, 198, 198),  # Lighter gray
    ]


def rgb_to_hex(rgb):
    """Convert RGB tuple to hex color string."""
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def generate_abstract_svg(colors, output_path, width=200, height=302):
    """Generate an abstract SVG pattern using the dominant colors."""
    svg_template = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" version="1.1" xmlns="http://www.w3.org/2000/svg">
    <rect width="{width}" height="{height}" fill="{rgb_to_hex(colors[0])}"/>
    <path d="M0 {height/2}L{width} 0L{width} {height}L0 {height/2}Z" fill="{rgb_to_hex(colors[1])}"/>
    <path d="M0 {height}L{width/2} {height/2}L{width} {height}L0 {height}Z" fill="{rgb_to_hex(colors[2])}"/>
</svg>"""

    with open(output_path, "w") as f:
        f.write(svg_template)


def extract_book_slug(file_path):
    """Extract book slug from post file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            parts = content.split("---")
            if len(parts) >= 3:
                front_matter = {}
                for line in parts[1].strip().split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        value = value.strip().strip('"')
                        if key.strip() == "book":
                            return value.strip()
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
    return None


def main():
    # Add argument parser for --force flag
    parser = argparse.ArgumentParser(
        description="Generate SVG abstractions for book covers"
    )
    parser.add_argument(
        "--force", action="store_true", help="Force regeneration of all SVGs"
    )
    args = parser.parse_args()

    # Create SVG directory if it doesn't exist
    svg_dir = "assets/svgs"
    os.makedirs(svg_dir, exist_ok=True)

    # Get all book slugs from posts
    post_files = glob.glob("posts/*.md")
    book_slugs = set()

    for post_file in post_files:
        slug = extract_book_slug(post_file)
        if slug:
            book_slugs.add(slug)

    # Process each book slug
    for book_slug in book_slugs:
        svg_path = os.path.join(svg_dir, f"{book_slug}.svg")
        cover_path = os.path.join("assets/images/covers", f"{book_slug}.jpg")

        # Skip if SVG already exists and not forcing regeneration
        if os.path.exists(svg_path) and not args.force:
            print(
                f"Skipping {book_slug}, SVG already exists (use --force to regenerate)"
            )
            continue

        print(f"Generating SVG for {book_slug}...")

        # Get colors from cover if it exists, otherwise use fallback
        if os.path.exists(cover_path):
            colors = get_dominant_colors(cover_path)
        else:
            print(f"No cover found for {book_slug}, using fallback colors")
            colors = get_fallback_colors()

        generate_abstract_svg(colors, svg_path)
        print(f"Generated SVG for {book_slug}")


if __name__ == "__main__":
    main()
