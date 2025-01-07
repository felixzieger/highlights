# highlights

This is the source for https://highlights.felixzieger.de/.

Forked from [melanierichards/highlights](https://github.com/melanierichards/highlights).

## To build

1. [Install Node/npm](https://nodejs.org/)
2. Run `npm install`
3. Run `npx @11ty/eleventy --serve`
4. Visit `localhost:8080`

## Commands

| Command                    | Purpose                      |
| -------------------------- | ---------------------------- |
| npm run start              | Serve project + watch Sass   |

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