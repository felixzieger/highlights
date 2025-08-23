import re
from datetime import datetime
import yaml
import os
import locale
import subprocess


def clean_title(title):
    """Extract main title before common subtitle separators and clean special characters."""
    # Common subtitle separators
    separators = [
        ": ",  # Most common
        " - ",  # Also common
        ". ",  # Sometimes used
        "– ",  # En dash
        "— ",  # Em dash
    ]

    # First clean any special characters or weird encoding
    title = title.replace("\ufeff", "")  # Remove BOM
    title = title.replace("\u200b", "")  # Remove zero-width space
    title = "".join(char for char in title if ord(char) < 128)  # Remove non-ASCII chars

    # Get the part before the first separator
    for sep in separators:
        if sep in title:
            title = title.split(sep)[0]

    return title.strip()


def format_author_name(author):
    """Format author name(s) as 'First Last' and handle multiple authors."""
    if not author:
        return ""

    # Split multiple authors
    authors = [a.strip() for a in author.split(";")]

    formatted_authors = []
    for author in authors:
        # Remove any parentheses and their contents
        author = re.sub(r"\([^)]*\)", "", author).strip()

        # Check if in "Last, First" format
        if "," in author:
            last_name, first_name = author.split(",", 1)
            formatted_authors.append(f"{first_name.strip()} {last_name.strip()}")
        else:
            # Split the name parts
            parts = author.split()
            if len(parts) >= 2:
                # Assume last word is last name, everything before is first name(s)
                last_name = parts[-1]
                first_names = " ".join(parts[:-1])
                formatted_authors.append(f"{first_names} {last_name}")
            else:
                # If only one part, use as is
                formatted_authors.append(author)

    # Join multiple authors with commas
    return ", ".join(formatted_authors)


def parse_clipping(text):
    # Set locale to German for date parsing
    locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")

    # Split into individual clippings
    clippings = text.split("==========")
    parsed_clippings = []

    for clipping in clippings:
        if not clipping.strip():
            continue

        lines = clipping.strip().split("\n")
        if len(lines) < 2:
            continue

        # Parse title and author
        title_author = lines[0].strip()
        title_match = re.match(r"^(.*?)(?:\s+\(([^)]+)\))?$", title_author)
        if title_match:
            # Clean the title to remove subtitle
            title = clean_title(title_match.group(1).strip())
            # Format author name(s)
            author = format_author_name(
                title_match.group(2) if title_match.group(2) else ""
            )

        # Parse highlight info
        metadata = lines[1].strip()

        # Parse text
        text = "\n".join(lines[3:]).strip()
        if not text:
            continue

        # Skip notes (we only want highlights)
        if "Notiz" in metadata or "Note" in metadata:
            continue

        # Extract page/location
        page_match = re.search(r"Seite (\d+)|Position (\d+)", metadata)
        page = ""
        if page_match:
            page = (
                f"Page {page_match.group(1)}"
                if page_match.group(1)
                else f"Location {page_match.group(2)}"
            )

        # Extract date
        date_match = re.search(r"Added on (.+)$|Hinzugefügt am (.+)$", metadata)
        date = None
        if date_match:
            date_str = date_match.group(1) or date_match.group(2)
            try:
                date = datetime.strptime(date_str, "%A, %d. %B %Y %H:%M:%S")
            except ValueError as e:
                print(f"Could not parse date: {date_str}")
                print(f"Error: {e}")

        parsed_clippings.append(
            {"title": title, "author": author, "text": text, "page": page, "date": date}
        )

    # Reset locale back to default
    locale.setlocale(locale.LC_TIME, "")

    return parsed_clippings


def generate_yaml(clippings, title):
    # Group highlights by book title
    book_highlights = []
    for c in clippings:
        if c["title"] == title:
            book_highlights.append({"text": c["text"], "page": c["page"]})

    return yaml.dump(book_highlights, allow_unicode=True, sort_keys=False)


def get_last_highlight_date(clippings, title):
    """Get the date of the last highlight for a book"""
    book_dates = [
        c["date"] for c in clippings if c["title"] == title and c["date"] is not None
    ]
    return max(book_dates) if book_dates else datetime.today()


def generate_post(title, author, date):
    # Escape quotes in title
    escaped_title = title.replace('"', '\\"')
    post = f"""---
title: "{escaped_title}"
book: {slugify(title)}
author: {author}
kindle: true
date: {date.strftime('%Y-%m-%d')}
tags: posts
---
"""
    return post


def slugify(text):
    # Convert to lowercase and replace spaces with hyphens
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-")


def get_latest_tracked_book_date():
    """Get the date of the most recent book tracked in git"""
    try:
        # Get the most recent git-tracked post file
        result = subprocess.run(
            ["git", "ls-files", "posts/*.md"],
            capture_output=True,
            text=True,
            check=True
        )
        
        if not result.stdout:
            return None
            
        # Sort the files and get the most recent one
        files = result.stdout.strip().split('\n')
        files.sort(reverse=True)
        
        if files:
            # Extract date from filename (format: posts/YYYY-MM-DD-*.md)
            latest_file = files[0]
            date_match = re.search(r'posts/(\d{4}-\d{2}-\d{2})', latest_file)
            if date_match:
                return datetime.strptime(date_match.group(1), '%Y-%m-%d')
    except subprocess.CalledProcessError:
        print("Warning: Could not get git-tracked files")
    
    return None


def main():
    # Read My Clippings.txt
    with open("My Clippings.txt", "r", encoding="utf-8") as f:
        content = f.read()

    # Parse clippings
    clippings = parse_clipping(content)

    # Get unique books
    books = {(c["title"], c["author"]) for c in clippings}

    # Get the latest tracked book date
    latest_tracked_date = get_latest_tracked_book_date()
    
    if latest_tracked_date:
        print(f"Latest tracked book date: {latest_tracked_date.strftime('%Y-%m-%d')}")
        print("Only importing books newer than this date...")
    else:
        print("No existing tracked books found. Importing all books...")

    # Create _data/books directory if it doesn't exist
    os.makedirs("_data/books", exist_ok=True)
    os.makedirs("posts", exist_ok=True)

    # Track imported and skipped books
    imported_books = []
    skipped_books = []

    # Generate files for each book
    for title, author in books:
        # Get last highlight date for this book
        last_highlight_date = get_last_highlight_date(clippings, title)
        
        # Skip if book is older than or equal to the latest tracked book
        if latest_tracked_date and last_highlight_date <= latest_tracked_date:
            skipped_books.append((title, last_highlight_date))
            continue
            
        # Generate YAML file
        yaml_filename = f"_data/books/{slugify(title)}.yaml"
        if os.path.exists(yaml_filename):
            print(f"Skipping {yaml_filename}: File already exists")
        else:
            yaml_content = generate_yaml(clippings, title)
            with open(yaml_filename, "w", encoding="utf-8") as f:
                f.write(yaml_content)
            imported_books.append((title, last_highlight_date))

        # Generate post file
        post_filename = f"posts/{last_highlight_date.strftime('%Y-%m-%d')}-{slugify(title)}.md"
        if os.path.exists(post_filename):
            print(f"Skipping {post_filename}: File already exists")
        else:
            post_content = generate_post(title, author, last_highlight_date)
            with open(post_filename, "w", encoding="utf-8") as f:
                f.write(post_content)
    
    # Print summary
    print(f"\n--- Import Summary ---")
    print(f"Imported {len(imported_books)} new book(s):")
    for title, date in sorted(imported_books, key=lambda x: x[1]):
        print(f"  - {title} ({date.strftime('%Y-%m-%d')})")
    
    if skipped_books:
        print(f"\nSkipped {len(skipped_books)} older book(s) (before {latest_tracked_date.strftime('%Y-%m-%d')}):")
        for title, date in sorted(skipped_books, key=lambda x: x[1], reverse=True)[:5]:
            print(f"  - {title} ({date.strftime('%Y-%m-%d')})")
        if len(skipped_books) > 5:
            print(f"  ... and {len(skipped_books) - 5} more")


if __name__ == "__main__":
    main()
