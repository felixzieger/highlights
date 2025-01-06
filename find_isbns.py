import glob
import requests
import time
from typing import Optional, Dict


def extract_front_matter(file_path: str) -> Dict:
    """Extract and parse front matter from markdown file."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    parts = content.split("---")
    if len(parts) >= 3:
        front_matter = {}
        for line in parts[1].strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                value = value.strip().strip('"')
                front_matter[key.strip()] = value
        return front_matter
    return {}


def search_book(title: str, author: str) -> Optional[str]:
    """Search OpenLibrary for a book and return its ISBN."""

    def try_search(search_query: str) -> Optional[str]:
        url = f"https://openlibrary.org/search.json?q={search_query}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                if data.get("docs"):
                    # Get the first result that has an ISBN
                    for doc in data["docs"]:
                        if "isbn" in doc:
                            # Try ISBN 13 first
                            for isbn in doc["isbn"]:
                                if len(isbn) == 13:
                                    return isbn
                            # If no ISBN 13 found, return the first ISBN
                            return doc["isbn"][0]
        except Exception as e:
            print(f"Error searching for {search_query}: {str(e)}")
        return None

    # Clean up the search query
    if not author:
        return try_search(f"title:{title}")

    # Try different author formats
    # 1. Try with original "First Last" format
    isbn = try_search(f"title:{title} author:{author}")
    if isbn:
        return isbn

    # 2. Try with "Last, First" format
    if " " in author:
        first_name, *middle_names, last_name = author.split()
        reversed_author = f"{last_name}, {first_name}"
        if middle_names:
            reversed_author += f" {' '.join(middle_names)}"
        isbn = try_search(f"title:{title} author:{reversed_author}")
        if isbn:
            return isbn

    # 3. Try with just the title (as fallback)
    return try_search(f"title:{title}")


def update_post_with_isbn(file_path: str, isbn: str) -> None:
    """Update the post file with the found ISBN."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    parts = content.split("---")
    if len(parts) >= 3:
        # Add bookshop_id to front matter
        front_matter_lines = parts[1].strip().split("\n")

        # Check if bookshop_id already exists
        has_bookshop_id = any("bookshop_id:" in line for line in front_matter_lines)

        if not has_bookshop_id:
            # Add bookshop_id before the last line
            front_matter_lines.append(f"bookshop_id: {isbn}")

            # Reconstruct the file content
            new_front_matter = "\n".join(front_matter_lines)
            new_content = f"---\n{new_front_matter}\n---{parts[2]}"

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Updated {file_path} with ISBN {isbn}")


def main():
    post_files = glob.glob("posts/*.md")
    for post_file in post_files:
        front_matter = extract_front_matter(post_file)

        # Skip if already has bookshop_id
        if front_matter.get("bookshop_id"):
            continue

        title = front_matter.get("title", "").strip('"')
        author = front_matter.get("author", "").strip('"')

        if title:
            print(f"Searching for {title} by {author}...")
            isbn = search_book(title, author)

            if isbn:
                print(f"Found ISBN {isbn} for {title}")
                update_post_with_isbn(post_file, isbn)
            else:
                print(f"No ISBN found for {title}")

            # Be nice to the API
            time.sleep(1)


if __name__ == "__main__":
    main()
