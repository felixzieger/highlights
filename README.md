# highlights

This is the source for https://highlights.felixzieger.de/.

Forked from [melanierichards/highlights](https://github.com/melanierichards/highlights).

## To build

1. Run `pnpm install`
2. Run `pnpm run dev`
3. Visit `localhost:8080`

## Commands

| Command                    | Purpose                      |
| -------------------------- | ---------------------------- |
| pnpm run dev               | Serve project + watch Sass   |

## Data syntax

### Book front-page matter

```
---
title: ""
book: dash-separated
author:
kindle: true
spoilers: false
content_warnings:
date: YYYY-MM-DD
bookshop_id:
---
```

* Where "dash-separated" is also the file name for the `_data` file, JPG, and SVG.

### Each highlight

```
- text: 
  page: 
  attribution: 
```

## Importing Kindle clippings

Copy `My Clippings.txt` from your Kindle (`documents/My Clippings.txt`) into the
repo root, then run the whole import pipeline with one command:

```bash
pnpm run update            # parse -> dedup -> ISBNs -> covers
pnpm run update -- --build # ...and build the site afterwards
```

Review the new files under `posts/`, `_data/books/`, and
`assets/images/covers/`, then commit.

### Individual steps

The pipeline runs these `scripts/` in order; each is idempotent, git-aware, and
can be run on its own:

1. `uv run python scripts/parse_kindle_clippings.py` — parse clippings into posts + highlight data
2. `uv run python scripts/deduplicate_highlights.py` — clean up newly imported highlights
3. `uv run python scripts/find_missing_isbns.py` — look up missing ISBNs
4. `uv run python scripts/fetch_covers.py` — download cover images

### Covers

Covers prefer **portrait** orientation and edition-specific sources (so the
cover language matches the recorded ISBN), picking the highest resolution.

- **Hand-pick a cover:** drop a `<book-slug>.jpg` (or `.png`/`.webp`) in the
  repo root. It overrides any fetched cover and is consumed after processing.
- **Choose between candidates interactively** (opens previews, prompts you):
  ```bash
  uv run python scripts/fetch_covers.py --interactive
  uv run python scripts/fetch_covers.py --interactive --force --book tempo
  ```
  `--force` re-fetches even if a cover exists; `--book <slug>` limits to one book.
