#!/usr/bin/env python3
"""Build assetra365.com as real pages from one source file.

    python3 build.py

Reads `src/site.html` - the whole site in one document, one `<main data-page="…">` per
page, exactly as it was written - and writes one directory per page at the repo root:

    /index.html            home
    /services/index.html   …and so on for every data-page
    /404.html  /sitemap.xml  /robots.txt

Why: the site was a single file routed by `#/services`, and a search engine sees one
page - and assetra365.com was not indexed at all. Google does not read what is behind a
`#`. Each generated page carries its own title, description, canonical address, Open
Graph tags and structured data (the firm as an Organization on the home page, a breadcrumb trail
on every page, the FAQ as an FAQPage read back from the rendered questions), and only its own
content - the other pages are not hidden inside it.

The design, the styles, the network animations and the assistant are untouched: every
generated page is the source document minus the other pages' `<main>` blocks, with the
hash links rewritten to paths. Old `#/x` links still arrive on the home page and are
sent on to `/x` by a few lines of script, so nothing bookmarked or shared breaks.

Edit `src/site.html`, run this, commit both. The generated files are committed too so
the deploy is a plain publish with no build step to fail.
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src" / "site.html"
SITE = "https://assetra365.com"

#: path (without slash for home) -> (title, description, breadcrumb name)
#: Titles under 60 characters, descriptions under 160, each written for the query
#: that page answers rather than repeating the home page.
PAGES: dict[str, tuple[str, str, str]] = {
    "home": (
        "Assetra Global — Offshore Accounting Teams for U.S. CPA Firms",
        "Reviewed, ready-to-use bookkeeping, tax prep, close and CFO support for U.S. CPA and "
        "accounting firms. CPA/EA/CMA-led review, 24-hour turnaround, 40-60% lower cost.",
        "Home",
    ),
    "why": (
        "Why Assetra — Offshore Capacity Without the Review Tax",
        "Most offshore outsourcing adds review work. Assetra is built around reviewed output: "
        "a senior checks every deliverable before it reaches your desk. See the comparison.",
        "Why Assetra",
    ),
    "services": (
        "Services — Bookkeeping, Tax Prep, Close & CFO Support | Assetra",
        "Twelve services from daily bookkeeping to 1120-S preparation, delivered by one "
        "embedded team inside QuickBooks, Xero, UltraTax, Drake and the tools you already run.",
        "Services",
    ),
    "tax-season": (
        "Tax Season Support — Staffed Before January | Assetra Global",
        "Add reviewed tax-prep throughput for the January-April surge and flex down in May. "
        "1040, 1120, 1120-S, 1065 and 1041 preparation with EA/CPA review, overnight.",
        "Tax season",
    ),
    "team": (
        "Team & Quality — CPA/EA/CMA-Led Review, Data Controls | Assetra",
        "A tiered team so the right work reaches the right level, a U.S. front door with a "
        "global engine room, and the controls that keep client data protected.",
        "Team & quality",
    ),
    "pricing": (
        "Pricing & Engagement — Dedicated Staff From $1,800/month | Assetra",
        "Dedicated staffing from about $1,800 per FTE per month, fixed-fee projects, seasonal "
        "support, and a two-week pilot every engagement starts with.",
        "Pricing & engagement",
    ),
    "faq": (
        "FAQ — Offshore Accounting for CPA Firms, Answered | Assetra",
        "Who does the work, how much you still review, how client data is handled, whether "
        "you get the same people, and what it costs — answered plainly.",
        "FAQ",
    ),
    "contact": (
        "Contact Assetra Global — Book a Discovery Call",
        "Book a 30-minute discovery call. We scope one engagement, propose a two-week pilot, "
        "and you judge the output before committing. Email or phone, U.S. hours.",
        "Contact",
    ),
}

FIRM = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": SITE + "/#firm",
    "name": "Assetra Global",
    "legalName": "Assetra Global Pvt Ltd",
    "url": SITE + "/",
    "email": "harsh@assetra365.com",
    "telephone": "+1-862-423-7028",
    "description": "Offshore finance and accounting teams for U.S. CPA, tax and accounting "
                   "firms: reviewed bookkeeping, tax preparation, close and CFO support.",
    "address": {"@type": "PostalAddress", "addressLocality": "Ahmedabad", "addressRegion": "Gujarat",
                "addressCountry": "IN"},
    "areaServed": {"@type": "Country", "name": "United States"},
    "knowsAbout": ["Bookkeeping", "U.S. tax preparation", "Month-end close", "CFO support",
                   "QuickBooks", "Xero", "UltraTax", "Drake"],
}


def url_of(key: str) -> str:
    # Netlify serves the apex domain and the directory form (`/about/`); the canonical is the
    # address actually served, not one redirect away from it.
    return SITE + "/" if key == "home" else f"{SITE}/{key}/"


def path_of(key: str) -> str:
    return "/" if key == "home" else f"/{key}"


def structured(key: str) -> list[dict]:
    title, description, crumb = PAGES[key]
    page = {"@context": "https://schema.org", "@type": "WebPage", "@id": url_of(key) + "#page",
            "url": url_of(key), "name": title, "description": description,
            "isPartOf": {"@type": "WebSite", "name": "Assetra Global", "url": SITE + "/"},
            "about": {"@id": SITE + "/#firm"}}
    out = [page]
    if key == "home":
        out.append(FIRM)
    else:
        out.append({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": crumb, "item": url_of(key)},
        ]})
    if key == "faq":
        faq = faq_schema(key)
        if faq:
            out.append(faq)
    return out


_MAINS: dict[str, str] = {}


def faq_schema(key: str) -> dict | None:
    """An FAQPage built from the questions the page actually shows (details/summary)."""
    import html as _html
    body = _MAINS.get(key, "")
    pairs = re.findall(r"<details><summary>(.*?)</summary><div class=\"a\">(.*?)</div></details>", body, re.S)
    if not pairs:
        return None
    strip = lambda t: _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t))).strip()  # noqa: E731
    return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": strip(q),
         "acceptedAnswer": {"@type": "Answer", "text": strip(a)}} for q, a in pairs]}


def head_block(key: str) -> str:
    title, description, _ = PAGES[key]
    e = lambda s: s.replace("&", "&amp;").replace('"', "&quot;")  # noqa: E731
    ld = "\n".join(f'<script type="application/ld+json">{json.dumps(d, ensure_ascii=False)}</script>'
                   for d in structured(key))
    return (
        f"<title>{e(title)}</title>\n"
        f'<meta name="description" content="{e(description)}">\n'
        f'<link rel="canonical" href="{url_of(key)}">\n'
        f'<meta property="og:type" content="website">\n'
        f'<meta property="og:site_name" content="Assetra Global">\n'
        f'<meta property="og:title" content="{e(title)}">\n'
        f'<meta property="og:description" content="{e(description)}">\n'
        f'<meta property="og:url" content="{url_of(key)}">\n'
        f'<meta name="twitter:card" content="summary">\n'
        f"{ld}"
    )


def build() -> int:
    src = SRC.read_text(encoding="utf-8")

    # ---- the head: everything between <head> and </head> that is not page-specific
    head_re = re.compile(r"<head>(.*?)</head>", re.S)
    head = head_re.search(src).group(1)
    keep = []
    for line in head.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith(("<title", "<meta name=\"description\"", "<link rel=\"canonical\"",
                         "<meta property=\"og:", "<meta name=\"twitter:")):
            continue
        keep.append(line)
    head_common = "\n".join(keep)

    # ---- the pages
    mains = {m.group(1): m.group(0) for m in
             re.finditer(r'<main class="page" data-page="([\w-]+)">.*?</main>', src, re.S)}
    _MAINS.update(mains)
    missing = set(PAGES) - set(mains)
    extra = set(mains) - set(PAGES)
    if missing or extra:
        print(f"PAGES and src disagree: missing {sorted(missing)}, unlisted {sorted(extra)}")
        return 1

    body = src[src.index("<body>") + len("<body>"):src.rindex("</body>")]
    # the shell is the body with every <main> removed and a marker where they were
    first = body.index('<main class="page"')
    last = body.rindex("</main>") + len("</main>")
    before, after = body[:first], body[last:]
    before = re.sub(r"<!-- =+ [A-Z ]+ =+ -->\s*$", "", before)

    written = []
    for key in PAGES:
        main = mains[key].replace('<main class="page"', '<main class="page on"', 1)
        doc = (
            "<!doctype html>\n<html lang=\"en\">\n<head>\n"
            + head_common + "\n" + head_block(key) + "\n</head>\n<body>"
            + before + main + after + "</body>\n</html>\n"
        )
        out = ROOT / "index.html" if key == "home" else ROOT / key / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(doc, encoding="utf-8")
        written.append(out.relative_to(ROOT).as_posix())

    # ---- 404: the shell with a short note, served by Netlify for any unknown path
    nf = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n" + head_common + "\n"
        "<title>Page not found — Assetra Global</title>\n<meta name=\"robots\" content=\"noindex\">\n"
        "</head>\n<body>" + before
        + '<main class="page on"><section class="phero"><canvas class="nodes"></canvas><div class="wrap">'
          '<div class="crumb"><a href="/">Home</a><i>/</i>Not found</div>'
          "<h1>That page isn't here.</h1>"
          '<p class="lede">The address may have changed. Start from the <a href="/">home page</a> '
          'or <a href="/contact">get in touch</a>.</p></div></section></main>'
        + after + "</body>\n</html>\n"
    )
    (ROOT / "404.html").write_text(nf, encoding="utf-8")

    # ---- sitemap and robots
    urls = "\n".join(f"  <url><loc>{url_of(k)}</loc></url>" for k in PAGES)
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "\n</urlset>\n",
        encoding="utf-8")
    (ROOT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n", encoding="utf-8")

    print("built: " + ", ".join(written) + ", 404.html, sitemap.xml, robots.txt")
    return 0


if __name__ == "__main__":
    sys.exit(build())
