import re
from datetime import datetime
import yaml
import os
import locale


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


def main():
    # Read My Clippings.txt
    with open("My Clippings.txt", "r", encoding="utf-8") as f:
        content = f.read()

    # Parse clippings
    clippings = parse_clipping(content)

    # Get unique books
    books = {(c["title"], c["author"]) for c in clippings}

    # Create _data/books directory if it doesn't exist
    os.makedirs("_data/books", exist_ok=True)
    os.makedirs("posts", exist_ok=True)

    # Generate files for each book
    for title, author in books:
        # Generate YAML file
        yaml_content = generate_yaml(clippings, title)
        yaml_filename = f"_data/books/{slugify(title)}.yaml"
        with open(yaml_filename, "w", encoding="utf-8") as f:
            f.write(yaml_content)

        # Get last highlight date
        last_highlight_date = get_last_highlight_date(clippings, title)

        # Generate post file
        post_content = generate_post(title, author, last_highlight_date)
        post_filename = (
            f"posts/{last_highlight_date.strftime('%Y-%m-%d')}-{slugify(title)}.md"
        )
        with open(post_filename, "w", encoding="utf-8") as f:
            f.write(post_content)


if __name__ == "__main__":
    main()
