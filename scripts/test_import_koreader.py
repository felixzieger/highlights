import json
from pathlib import Path
import tempfile
import unittest
import yaml
from import_koreader import import_book, load_books


class ImportTests(unittest.TestCase):
    def test_merge_preserves_edits_and_post(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            row = {
                "text": "First highlight",
                "page": "KOReader page 2",
                "pos0": "a",
                "pos1": "b",
                "datetime": "2026-10-11 12:00:00",
            }
            self.assertEqual(import_book(root, "Die Brüder", "Author", [row]), 1)
            post = next((root / "posts").glob("*.md"))
            original = post.read_bytes()
            target = root / "_data/books/die-bruder.yaml"
            data = yaml.safe_load(target.read_text())
            data[0]["text"] = "Manually edited quote"
            target.write_text(yaml.safe_dump(data))
            second = dict(row, text="Second quote", pos0="c", pos1="d")
            self.assertEqual(
                import_book(root, "Die Brüder", "Author", [row, second]), 1
            )
            self.assertEqual(
                import_book(root, "Die Brüder", "Author", [row, second]), 0
            )
            self.assertEqual(post.read_bytes(), original)
            self.assertEqual(
                yaml.safe_load(target.read_text())[0]["text"], "Manually edited quote"
            )
            with self.assertRaises(ValueError):
                import_book(root, "Die Brüder", "Different author", [row])

    def test_native_export_and_bookmarks(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "export.json"
            path.write_text(
                json.dumps(
                    {
                        "documents": [
                            {
                                "title": "Book",
                                "author": "Writer",
                                "entries": [
                                    {"text": "bookmark", "page": 2},
                                    {
                                        "text": "Quote\nwith Ünicode",
                                        "drawer": "lighten",
                                        "page": 4,
                                        "time": 1791712800,
                                        "note": "My note",
                                    },
                                ],
                            }
                        ]
                    }
                )
            )
            _, _, rows = load_books(path)[0]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["page"], "KOReader page 4")
            self.assertEqual(rows[0]["note"], "My note")
            self.assertIn("Ünicode", rows[0]["text"])


if __name__ == "__main__":
    unittest.main()
