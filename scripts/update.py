#!/usr/bin/env python3
"""One-command Kindle highlights update.

Runs the full import pipeline in order:

  1. parse_kindle_clippings  - parse "My Clippings.txt" into posts + highlight data
  2. deduplicate_highlights  - clean up newly imported highlight files
  3. find_missing_isbns      - look up ISBNs for posts that lack one
  4. fetch_covers            - download cover images for posts with an ISBN

Each step is idempotent and git-aware, so re-running only processes what is new.

Usage:
    uv run python scripts/update.py            # run the import pipeline
    uv run python scripts/update.py --build    # also build the site afterwards
"""

import argparse
import os
import sys
import time
import subprocess

# Make sure imports resolve and all scripts run from the repo root, since they
# use paths relative to the working directory (e.g. "My Clippings.txt").
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
os.chdir(REPO_ROOT)

import parse_kindle_clippings
import deduplicate_highlights
import find_missing_isbns
import fetch_covers


STEPS = [
    ("Parsing Kindle clippings", parse_kindle_clippings.main),
    ("Deduplicating new highlights", deduplicate_highlights.main),
    ("Finding missing ISBNs", find_missing_isbns.main),
    ("Fetching book covers", fetch_covers.main),
]


def run_step(index, total, title, func):
    header = f"[{index}/{total}] {title}"
    print("\n" + "=" * 70)
    print(header)
    print("=" * 70)
    start = time.monotonic()
    func()
    elapsed = time.monotonic() - start
    print(f"\n-> done in {elapsed:.1f}s")


def main():
    parser = argparse.ArgumentParser(description="Update highlights from Kindle clippings.")
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build the Eleventy site after importing (runs `pnpm run build`).",
    )
    args = parser.parse_args()

    if not os.path.exists("My Clippings.txt"):
        print("Error: 'My Clippings.txt' not found in the repo root.")
        print("Copy it from your Kindle (documents/My Clippings.txt) and re-run.")
        sys.exit(1)

    total = len(STEPS)
    for i, (title, func) in enumerate(STEPS, start=1):
        run_step(i, total, title, func)

    if args.build:
        print("\n" + "=" * 70)
        print("Building site")
        print("=" * 70)
        subprocess.run(["pnpm", "run", "build"], check=True)

    print("\n" + "=" * 70)
    print("All done. Review the new posts/, _data/books/, and covers, then commit.")
    print("=" * 70)


if __name__ == "__main__":
    main()
