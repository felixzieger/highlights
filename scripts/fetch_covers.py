import requests
from PIL import Image
from io import BytesIO
import os
import re
import sys
import yaml
import glob
import argparse
import tempfile
import subprocess


def isbn13_to_10(isbn13):
    """Convert ISBN-13 to ISBN-10."""
    isbn13 = isbn13.replace("-", "")
    if len(isbn13) != 13:
        return None
    body = isbn13[3:12]
    check = 0
    for i, digit in enumerate(body):
        check += int(digit) * (10 - i)
    check = (11 - (check % 11)) % 11
    return body + ("X" if check == 10 else str(check))


def get_amazon_hires_cover(isbn, title, author):
    """Search Amazon for the book and extract the high-res cover image URL.

    Amazon product pages embed a data-old-hires attribute on the landing image
    with a URL like .../images/I/<ID>._SL1500_.jpg. Stripping the size suffix
    (everything between the last dot of the ID and .jpg) gives the original
    full-resolution image.
    """
    isbn10 = isbn13_to_10(isbn) if len(isbn.replace("-", "")) == 13 else isbn
    search_query = f"{title} {author}".replace(" ", "+")

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    # Try direct product page via ISBN-10 first
    urls_to_try = []
    if isbn10:
        urls_to_try.append(f"https://www.amazon.com/dp/{isbn10}")
    urls_to_try.append(f"https://www.amazon.com/s?k={search_query}&i=stripbooks")

    for url in urls_to_try:
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                continue

            # Look for data-old-hires attribute (high-res image URL)
            hires_match = re.search(
                r'data-old-hires="(https://m\.media-amazon\.com/images/I/[^"]+)"',
                response.text,
            )
            if hires_match:
                hires_url = hires_match.group(1)
                # Strip size suffix to get original resolution
                # e.g. 71+pnb1BMOL._SL1500_.jpg -> 71+pnb1BMOL.jpg
                full_res_url = re.sub(r"\._[^.]+_\.jpg", ".jpg", hires_url)
                return full_res_url

            # Fallback: look for any large product image
            img_match = re.search(
                r'"(https://m\.media-amazon\.com/images/I/[^"]+\._SL1[0-9]+_\.jpg)"',
                response.text,
            )
            if img_match:
                full_res_url = re.sub(r"\._[^.]+_\.jpg", ".jpg", img_match.group(1))
                return full_res_url

            # If this was a search page, try to find the first product link
            if "/s?" in url:
                product_match = re.search(
                    r'href="(/[^"]+/dp/[A-Z0-9]{10}[^"]*)"', response.text
                )
                if product_match:
                    product_url = f"https://www.amazon.com{product_match.group(1)}"
                    product_response = requests.get(
                        product_url, headers=headers, timeout=15
                    )
                    if product_response.status_code == 200:
                        hires_match = re.search(
                            r'data-old-hires="(https://m\.media-amazon\.com/images/I/[^"]+)"',
                            product_response.text,
                        )
                        if hires_match:
                            full_res_url = re.sub(
                                r"\._[^.]+_\.jpg", ".jpg", hires_match.group(1)
                            )
                            return full_res_url
        except requests.RequestException:
            continue

    return None


def _google_imagelinks_url(volume_info):
    """Pick the largest available image URL from a Google Books volume."""
    links = volume_info.get("imageLinks", {})
    for key in ("extraLarge", "large", "medium", "thumbnail", "smallThumbnail"):
        if key in links:
            # Bump zoom and drop the page-curl effect for a cleaner, larger image
            url = links[key].replace("&edge=curl", "")
            url = re.sub(r"&zoom=\d+", "&zoom=3", url)
            return url.replace("http://", "https://")
    return None


def collect_cover_candidates(isbn, title, author):
    """Gather candidate cover image URLs.

    Edition-specific sources (keyed by ISBN) come first so the cover language
    matches the edition we recorded for the book. Title/author search is only a
    last resort, since it can return a different-language edition.
    """
    edition_specific = []
    fallback = []

    def add(bucket, url):
        if url and url not in bucket:
            bucket.append(url)

    isbn10 = isbn13_to_10(isbn) if len(isbn.replace("-", "")) == 13 else isbn

    # Amazon high-res, edition-specific product page (/dp/<isbn10>)
    add(edition_specific, get_amazon_hires_cover(isbn, title, author))

    # OpenLibrary covers by ISBN
    add(edition_specific, f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg")
    try:
        r = requests.get(
            f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data",
            timeout=15,
        )
        if r.status_code == 200:
            book = r.json().get(f"ISBN:{isbn}", {})
            add(edition_specific, book.get("cover", {}).get("large"))
    except requests.RequestException:
        pass

    # Google Books by ISBN (edition-specific)
    try:
        r = requests.get(
            f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}", timeout=15
        )
        if r.status_code == 200:
            items = r.json().get("items", [])
            if items:
                add(edition_specific, _google_imagelinks_url(items[0]["volumeInfo"]))
    except requests.RequestException:
        pass

    # Fallback: Google Books by title/author (may not match language)
    try:
        query = f"{title} {author}".replace(" ", "+")
        r = requests.get(
            f"https://www.googleapis.com/books/v1/volumes?q={query}", timeout=15
        )
        if r.status_code == 200:
            items = r.json().get("items", [])
            if items:
                add(fallback, _google_imagelinks_url(items[0]["volumeInfo"]))
    except requests.RequestException:
        pass

    return edition_specific, fallback


def _download(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code == 200 and r.content:
            return r.content
    except requests.RequestException:
        pass
    return None


def select_best_cover(candidates):
    """Download candidates and return the bytes of the best one.

    Preference: portrait orientation first (book covers are taller than wide),
    then highest resolution. OpenLibrary returns a tiny 1x1 pixel placeholder
    when it has no cover, which is filtered out by the minimum-size check.
    """
    portrait = []  # (area, data)
    other = []

    for url in candidates:
        data = _download(url)
        if not data:
            continue
        try:
            img = Image.open(BytesIO(data))
            w, h = img.size
        except Exception:
            continue

        # Skip placeholders / tiny thumbnails
        if w < 200 or h < 200:
            continue

        area = w * h
        if h > w:  # portrait
            portrait.append((area, data))
        else:
            other.append((area, data))

    pool = portrait or other
    if not pool:
        return None
    return max(pool, key=lambda x: x[0])[1]


def get_cover_image(isbn, title, author):
    """Return image bytes for the best cover, preferring portrait + edition match."""
    edition_specific, fallback = collect_cover_candidates(isbn, title, author)

    # Try edition-specific (correct language) candidates first
    best = select_best_cover(edition_specific)
    if best:
        return best

    # Only fall back to title/author search if nothing edition-specific worked
    return select_best_cover(fallback)


def process_image(image_data, output_path):
    """Save image as high-quality WebP without resizing."""
    img = Image.open(BytesIO(image_data))

    # Convert to RGB if necessary (in case of PNG with transparency)
    if img.mode in ("RGBA", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Save as high-quality WebP (no resize -- let the browser/CSS handle display size)
    img.save(output_path, "WEBP", quality=85)


OVERRIDE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def find_local_override(book):
    """Return path to a hand-placed cover in the repo root, e.g. '<book>.jpg'.

    Drop a '<book-slug>.jpg/.png/...' file in the project root to force that
    image as the cover. It is consumed (deleted) after being processed.
    """
    for ext in OVERRIDE_EXTS:
        path = f"{book}{ext}"
        if os.path.exists(path):
            return path
    return None


def _measure(data):
    try:
        w, h = Image.open(BytesIO(data)).size
        return w, h
    except Exception:
        return None


def choose_cover_interactive(book, candidates):
    """Download all candidates, open previews, and let the user pick one.

    Returns the chosen image bytes, or None to skip the book.
    """
    options = []
    for url in candidates:
        data = _download(url)
        if not data:
            continue
        size = _measure(data)
        if not size or size[0] < 200 or size[1] < 200:
            continue
        options.append({"url": url, "data": data, "w": size[0], "h": size[1]})

    if not options:
        print(f"  No usable candidates for {book}.")
        return None

    # Portrait first, then by resolution
    options.sort(key=lambda o: (o["h"] > o["w"], o["w"] * o["h"]), reverse=True)

    # Write previews to a temp dir and open them for visual comparison
    preview_dir = os.path.join(tempfile.gettempdir(), "highlights_cover_choices")
    os.makedirs(preview_dir, exist_ok=True)
    print(f"\n  Candidates for '{book}':")
    for i, opt in enumerate(options, start=1):
        orient = "portrait" if opt["h"] > opt["w"] else "landscape/square"
        preview = os.path.join(preview_dir, f"{book}_{i}.jpg")
        try:
            img = Image.open(BytesIO(opt["data"]))
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(preview, "JPEG")
            opt["preview"] = preview
        except Exception:
            opt["preview"] = None
        print(f"    [{i}] {opt['w']}x{opt['h']} ({orient})  {opt['url'][:70]}")

    previews = [o["preview"] for o in options if o.get("preview")]
    if previews and sys.platform == "darwin":
        subprocess.run(["open", *previews], check=False)

    while True:
        choice = (
            input(f"  Choose 1-{len(options)} (Enter = [1] best, 's' = skip): ")
            .strip()
            .lower()
        )
        if choice == "":
            return options[0]["data"]
        if choice == "s":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1]["data"]
        print("  Invalid choice.")


def parse_front_matter(post_file):
    with open(post_file, "r") as f:
        content = f.read()
    parts = content.split("---")
    if len(parts) < 3:
        return None
    front_matter = {}
    for line in parts[1].strip().split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            front_matter[key.strip()] = value.strip().strip('"')
    return front_matter


def main():
    parser = argparse.ArgumentParser(description="Fetch book cover images.")
    parser.add_argument(
        "-i", "--interactive", action="store_true",
        help="Show multiple candidates and choose one per book.",
    )
    parser.add_argument(
        "-f", "--force", action="store_true",
        help="Re-fetch covers even if one already exists.",
    )
    parser.add_argument(
        "--book", default=None,
        help="Only process the post with this book slug.",
    )
    args = parser.parse_args()

    output_dir = "assets/images/covers"
    os.makedirs(output_dir, exist_ok=True)

    all_posts = sorted(glob.glob("posts/*.md"))
    known_books = {
        (parse_front_matter(p) or {}).get("book") for p in all_posts
    }

    for post_file in all_posts:
        try:
            front_matter = parse_front_matter(post_file)
            if not front_matter:
                continue

            book = front_matter.get("book")
            if not book or (args.book and book != args.book):
                continue

            output_path = os.path.join(output_dir, f"{book}.webp")
            override = find_local_override(book)

            # A hand-placed override always wins (even over an existing cover).
            if override:
                print(f"Using local override for {book}: {override}")
                with open(override, "rb") as f:
                    process_image(f.read(), output_path)
                os.remove(override)
                print(f"  Saved cover for {book} (consumed {override})")
                continue

            if os.path.exists(output_path) and not args.force:
                continue

            if not front_matter.get("bookshop_id"):
                print(f"No ISBN for {book}, skipping (add bookshop_id or a {book}.jpg)")
                continue

            isbn = str(front_matter["bookshop_id"])
            title = front_matter.get("title", "")
            author = front_matter.get("author", "")
            print(f"Fetching cover for {book}...")

            if args.interactive:
                edition_specific, fallback = collect_cover_candidates(
                    isbn, title, author
                )
                data = choose_cover_interactive(book, edition_specific + fallback)
            else:
                data = get_cover_image(isbn, title, author)

            if data:
                process_image(data, output_path)
                print(f"  Saved cover for {book}")
            else:
                print(f"  No cover found for {book}")
        except Exception as e:
            print(f"Error processing file {post_file}: {str(e)}")

    # Warn about leftover override files that have no matching post
    leftovers = glob.glob("*.jpg") + glob.glob("*.jpeg") + glob.glob("*.png")
    for path in leftovers:
        book = os.path.splitext(os.path.basename(path))[0]
        if book not in known_books:
            print(
                f"Note: '{path}' has no matching post (book slug '{book}'); left in place."
            )


if __name__ == "__main__":
    main()
