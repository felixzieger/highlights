import requests
from PIL import Image
from io import BytesIO
import os
import re
import yaml
import glob


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


def get_cover_url(isbn, title, author):
    """Try to get cover URL from multiple sources, preferring high-res."""
    # Try Amazon first for high-res covers
    amazon_url = get_amazon_hires_cover(isbn, title, author)
    if amazon_url:
        return amazon_url

    # Fallback: Try OpenLibrary
    url = (
        f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
    )
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if f"ISBN:{isbn}" in data:
            book_data = data[f"ISBN:{isbn}"]
            if "cover" in book_data:
                return book_data["cover"]["large"]

    # Fallback: Try Google Books API with ISBN
    google_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    response = requests.get(google_url)
    if response.status_code == 200:
        data = response.json()
        if "items" in data and len(data["items"]) > 0:
            volume_info = data["items"][0]["volumeInfo"]
            if "imageLinks" in volume_info:
                if "extraLarge" in volume_info["imageLinks"]:
                    return volume_info["imageLinks"]["extraLarge"]
                elif "large" in volume_info["imageLinks"]:
                    return volume_info["imageLinks"]["large"]
                elif "thumbnail" in volume_info["imageLinks"]:
                    return volume_info["imageLinks"]["thumbnail"]

    # Fallback: Try Google Books API with title and author
    search_query = f"{title} {author}".replace(" ", "+")
    google_url = f"https://www.googleapis.com/books/v1/volumes?q={search_query}"
    response = requests.get(google_url)
    if response.status_code == 200:
        data = response.json()
        if "items" in data and len(data["items"]) > 0:
            volume_info = data["items"][0]["volumeInfo"]
            if "imageLinks" in volume_info:
                if "extraLarge" in volume_info["imageLinks"]:
                    return volume_info["imageLinks"]["extraLarge"]
                elif "large" in volume_info["imageLinks"]:
                    return volume_info["imageLinks"]["large"]
                elif "thumbnail" in volume_info["imageLinks"]:
                    return volume_info["imageLinks"]["thumbnail"]

    return None


def process_image(image_data, output_path):
    """Save image as high-quality JPG without resizing."""
    img = Image.open(BytesIO(image_data))

    # Convert to RGB if necessary (in case of PNG with transparency)
    if img.mode in ("RGBA", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Save as high-quality JPG (no resize -- let the browser/CSS handle display size)
    img.save(output_path, "JPEG", quality=90)


def main():
    # Create output directory if it doesn't exist
    output_dir = "assets/images/covers"
    os.makedirs(output_dir, exist_ok=True)

    # Process all post files
    post_files = glob.glob("posts/*.md")
    for post_file in post_files:
        try:
            # Read post file
            with open(post_file, "r") as f:
                content = f.read()

            # Extract front matter between --- markers
            parts = content.split("---")
            if len(parts) >= 3:
                # Create a properly formatted YAML document
                front_matter = {}
                for line in parts[1].strip().split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        # Strip quotes and whitespace
                        value = value.strip().strip('"')
                        front_matter[key.strip()] = value

                if "bookshop_id" in front_matter and front_matter["bookshop_id"]:
                    isbn = str(front_matter["bookshop_id"])
                    output_path = os.path.join(
                        output_dir, f"{front_matter['book']}.jpg"
                    )

                    # Skip if file already exists
                    if os.path.exists(output_path):
                        # print(f"Skipping {front_matter['book']}, cover already exists")
                        continue

                    print(f"Fetching cover for {front_matter['book']}...")
                    cover_url = get_cover_url(
                        isbn,
                        title=front_matter["title"],
                        author=front_matter["author"],
                    )

                    if cover_url:
                        try:
                            response = requests.get(cover_url)
                            if response.status_code == 200:
                                process_image(response.content, output_path)
                                print(
                                    f"Successfully saved cover for {front_matter['book']}"
                                )
                            else:
                                print(
                                    f"Failed to download image for {front_matter['book']}"
                                )
                        except Exception as e:
                            print(f"Error processing {front_matter['book']}: {str(e)}")
                    else:
                        print(f"No cover found for {front_matter['book']}")
                else:
                    print("No ISBN found for book", post_file)
        except Exception as e:
            print(f"Error processing file {post_file}: {str(e)}")


if __name__ == "__main__":
    main()
