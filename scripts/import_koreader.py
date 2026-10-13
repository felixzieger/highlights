"""Import KOReader JSON exports or SSH sidecar snapshots into the existing site."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import unicodedata
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[1]


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def slugify(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def load_books(path):
    data = json.loads(Path(path).read_text())
    books = data.get("documents", [data])
    if not isinstance(books, list):
        raise ValueError("Expected a documents array")
    result = []
    for book in books:
        title, author = book.get("title"), book.get("author", "")
        if (
            not isinstance(title, str)
            or not title.strip()
            or not isinstance(author, str)
        ):
            raise ValueError("Book needs a title and an author string")
        entries = book.get("highlights", book.get("entries"))
        if not isinstance(entries, list):
            raise ValueError(f"{title}: expected highlights or entries array")
        rows = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("Invalid highlight entry")
            if entry.get("drawer") is None or not entry.get("text"):
                continue  # Plain bookmarks have no selection style.
            text = entry["text"]
            if not isinstance(text, str):
                raise ValueError("Highlight text must be a string")
            page = entry.get("pageno", entry.get("page"))
            chapter = entry.get("chapter", "")
            location = f"KOReader page {page}" if str(page).isdigit() else chapter
            row = {"text": text, "page": location, "source": "koreader"}
            for key in ("chapter", "note", "datetime", "pos0", "pos1", "pn_xp"):
                if entry.get(key) is not None:
                    row[key] = entry[key]
            if not row.get("datetime") and entry.get("time") is not None:
                row["datetime"] = datetime.fromtimestamp(
                    entry["time"], ZoneInfo("Europe/Berlin")
                ).isoformat()
            rows.append(row)
        result.append((title.strip(), author.strip(), rows))
    return result


def import_book(root, title, author, rows):
    if not rows:
        return 0
    posts = root / "posts"
    books_dir = root / "_data/books"
    posts.mkdir(parents=True, exist_ok=True)
    books_dir.mkdir(parents=True, exist_ok=True)
    matched = []
    for path in posts.glob("*.md"):
        parts = path.read_text().split("---", 2)
        meta = yaml.safe_load(parts[1]) if len(parts) == 3 else {}
        if normalized(str(meta.get("title", ""))) == normalized(title) and normalized(
            str(meta.get("author", ""))
        ) == normalized(author):
            matched.append((path, meta))
    if len(matched) > 1:
        raise ValueError(f"Ambiguous existing posts for {title}")
    slug = str(matched[0][1]["book"]) if matched else slugify(title)
    if not slug or not re.fullmatch(r"[a-zA-Z0-9_-]+", slug):
        raise ValueError("Unsafe or empty book slug")
    target = books_dir / f"{slug}.yaml"
    if not matched and target.exists():
        raise ValueError(
            f"Slug collision: {slug}; match the existing title/author first"
        )
    existing = yaml.safe_load(target.read_text()) or [] if target.exists() else []
    if not isinstance(existing, list):
        raise ValueError(f"{target}: expected a highlight list")
    texts = {normalized(row["text"]) for row in existing}
    positions = {
        (row.get("pos0"), row.get("pos1")) for row in existing if row.get("pos0")
    }
    added = []
    for row in rows:
        key = normalized(row["text"])
        position = (row.get("pos0"), row.get("pos1"))
        if key in texts or (position[0] and position in positions):
            continue
        added.append(row)
        texts.add(key)
        if position[0]:
            positions.add(position)
    if added:
        temp = target.with_suffix(".yaml.tmp")
        temp.write_text(
            yaml.safe_dump(existing + added, allow_unicode=True, sort_keys=False)
        )
        temp.replace(target)
    if not matched:
        dates = [str(row["datetime"])[:10] for row in rows if row.get("datetime")]
        date = (
            max(dates)
            if dates
            else datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()
        )
        datetime.strptime(date, "%Y-%m-%d")
        meta = {
            "title": title,
            "book": slug,
            "author": author,
            "kindle": True,
            "date": date,
            "tags": "posts",
            "highlight_source": "koreader",
        }
        (posts / f"{date}-{slug}.md").write_text(
            "---\n"
            + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
            + "---\n"
        )
    return len(added)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    # Validate every input before writing anything.
    books = [book for path in args.files for book in load_books(path)]
    for title, author, rows in books:
        added = import_book(ROOT, title, author, rows)
        print(f"{title}: {added} new highlights ({len(rows)} in export)")


if __name__ == "__main__":
    main()
