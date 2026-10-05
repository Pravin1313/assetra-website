# assetra365.com

Static site on Netlify. One source document, real pages.

- `src/site.html` — the whole site: styles, header, one `<main data-page="…">` per page,
  footer, the assistant. **Edit this file.**
- `python3 build.py` — writes `/index.html`, `/services/index.html`, … plus `404.html`,
  `sitemap.xml` and `robots.txt`, each page with its own title, description, canonical and
  structured data (the FAQ page's schema is read from its own questions). Titles and
  descriptions live in `PAGES` at the top of `build.py`.
- Commit the source **and** the generated files; Netlify publishes the repo as-is.
- `inkplop/`, `look-closer/`, `tapri-tycoon/` are the app privacy/support pages; untouched.

Old `#/services`-style links still work: the page sends them on to `/services`.
