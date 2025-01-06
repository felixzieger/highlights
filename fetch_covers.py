import requests
from PIL import Image
from io import BytesIO
import os
import yaml
import glob


def get_cover_url(isbn, title, author):
    """Try to get cover URL from multiple book APIs"""
    # Try OpenLibrary first
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

    # Try Google Books API with ISBN
    google_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    response = requests.get(google_url)
    if response.status_code == 200:
        data = response.json()
        if "items" in data and len(data["items"]) > 0:
            volume_info = data["items"][0]["volumeInfo"]
            if "imageLinks" in volume_info:
                # Get largest available image
                if "extraLarge" in volume_info["imageLinks"]:
                    return volume_info["imageLinks"]["extraLarge"]
                elif "large" in volume_info["imageLinks"]:
                    return volume_info["imageLinks"]["large"]
                elif "thumbnail" in volume_info["imageLinks"]:
                    return volume_info["imageLinks"]["thumbnail"]

    # Try Google Books API with title and author as final fallback
    search_query = f"{title} {author}".replace(" ", "+")
    google_url = f"https://www.googleapis.com/books/v1/volumes?q={search_query}"
    response = requests.get(google_url)
    if response.status_code == 200:
        data = response.json()
        if "items" in data and len(data["items"]) > 0:
            volume_info = data["items"][0]["volumeInfo"]
            if "imageLinks" in volume_info:
                # Get largest available image
                if "extraLarge" in volume_info["imageLinks"]:
                    return volume_info["imageLinks"]["extraLarge"]
                elif "large" in volume_info["imageLinks"]:
                    return volume_info["imageLinks"]["large"]
                elif "thumbnail" in volume_info["imageLinks"]:
                    return volume_info["imageLinks"]["thumbnail"]

    return None


def process_image(image_data, output_path, width=400):
    """Process image to correct size and save as JPG"""
    img = Image.open(BytesIO(image_data))

    # Calculate new height maintaining aspect ratio
    aspect_ratio = img.height / img.width
    new_height = int(width * aspect_ratio)

    # Resize image
    img = img.resize((width, new_height), Image.Resampling.LANCZOS)

    # Convert to RGB if necessary (in case of PNG with transparency)
    if img.mode in ("RGBA", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background

    # Save as JPG
    img.save(output_path, "JPEG", quality=85)


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
