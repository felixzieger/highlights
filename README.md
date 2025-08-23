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

## Python helpers for importing kindle clippings

### Setup

Install [uv](https://docs.astral.sh/uv/) if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then install Python dependencies:
```bash
uv sync
```

### Usage

```bash
uv run python parse_kindle_clippings.py
uv run python deduplicate_highlights.py
```

Or activate the virtual environment:
```bash
source .venv/bin/activate
python parse_kindle_clippings.py
python deduplicate_highlights.py
```
