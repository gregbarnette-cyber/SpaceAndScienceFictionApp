"""core/wikipedia.py — resolve a star to its Wikipedia article and fetch the lead summary.

Pure resolution logic (offline-testable) plus a thin network layer that reuses the app's
shared retry / timeout / error helpers. **No Qt** — the GUI ``WikipediaView`` calls this on a
background thread. There is deliberately no ``query.py`` subcommand (this is presentation, not a
calculator); the logic lives here only so it can be unit-tested. See completed_plans/WIKIPEDIA_TABS_PLAN.md.

Resolution strategy: build an ordered list of candidate article titles from a star's SIMBAD
designations (proper name → spelled-out Bayer → Flamsteed → HR → HD → GJ/Gliese → HIP → main id),
query the Wikipedia REST *summary* endpoint for each (following redirects), and return the first
that is a real **star** article — guarding against disambiguation pages and unrelated topics so a
bad candidate can never surface the wrong page.
"""

import html
import re
import urllib.parse

from core.shared import (
    _with_retries,
    _network_error_msg,
    strip_star_prefix,
    format_star_designation,
    constellation_genitive,
)

# ── Constants ────────────────────────────────────────────────────────────────
_WIKI_REST = "https://en.wikipedia.org/api/rest_v1/page/summary/"
_WIKI_API = "https://en.wikipedia.org/w/api.php"
_WIKI_PAGE = "https://en.wikipedia.org/wiki/"
# Descriptive User-Agent per Wikipedia API etiquette. Deliberately NO personal email
# (the userEmail memory rule): app identity only. Add a repo URL here if one is wanted.
_WIKI_UA = "SpaceAndScienceFictionApp/1.0 (astronomy worldbuilding desktop tool)"
_WIKI_TIMEOUT = 15

# Star / non-star word sets. All matching is WORD-BOUNDARY (\b…\b, case-insensitive) so a
# substring like "star" inside "starling"/"restart" or "stellar" inside "interstellar" does NOT
# match (_STAR_RE / _NON_STAR_RE below). The guard (see _is_star_article) is layered:
#   1. a star word in the short Wikidata description  → accept (the common case: a star's
#      description reads "star in the constellation …" / "red dwarf" / "binary star system");
#   2. else a disqualifier word in the description    → reject (constellation / film / genus /
#      company / … — this is what rejects the *constellation* article whose extract says
#      "its brightest star is …", which a plain extract scan would wrongly accept);
#   3. else (a generic/absent description)            → fall back to the lead extract, so a real
#      star whose description is e.g. "astronomical X-ray source" is still recognised.
_STAR_WORDS = frozenset({
    "star", "stellar", "dwarf", "subdwarf", "subgiant", "giant", "supergiant",
    "binary", "multiple star", "planetary system", "brown dwarf",
    "main sequence", "sun-like", "solar analog", "solar-type", "exoplanet",
})
_NON_STAR_DESC = frozenset({
    "constellation", "film", "genus", "species", "song", "album", "video game",
    "novel", "comics", "given name", "surname", "municipality", "company",
    "supermarket", "river", "mountain", "band", "actor", "actress", "moth",
})


def _word_re(words):
    return re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.IGNORECASE)


_STAR_RE = _word_re(_STAR_WORDS)
_NON_STAR_RE = _word_re(_NON_STAR_DESC)

# Greek abbreviation → English word. Wikipedia spells the Greek letter out in article titles
# ("Tau Ceti", "Alpha Centauri"), whereas core.shared._GREEK_ABBREVIATIONS maps the same keys to
# the *symbol* (α/β/…). Keys mirror that table (including the trailing-period three-char forms and
# the tolerated alternates) so the two can't drift on the abbreviations they accept.
_GREEK_ENGLISH = {
    "alf": "Alpha", "bet": "Beta", "gam": "Gamma", "del": "Delta",
    "eps": "Epsilon", "zet": "Zeta", "eta": "Eta", "tet": "Theta",
    "iot": "Iota", "kap": "Kappa", "lam": "Lambda", "mu.": "Mu",
    "nu.": "Nu", "ksi": "Xi", "omi": "Omicron", "pi.": "Pi",
    "rho": "Rho", "sig": "Sigma", "tau": "Tau", "ups": "Upsilon",
    "phi": "Phi", "chi": "Chi", "psi": "Psi", "ome": "Omega",
    # tolerated alternates (mirror core.shared._GREEK_ABBREVIATIONS.update(...))
    "mu": "Mu", "nu": "Nu", "pi": "Pi", "xi": "Xi", "the": "Theta", "omc": "Omicron",
}

# A Bayer token may carry a trailing numeral ("alf01" → Alpha, superscript 1 dropped for the
# Wikipedia system article). The letter part is Greek-abbreviation characters + the padding dot.
_BAYER_TOKEN_RE = re.compile(r"^([A-Za-z.]+)(\d+)?$")


def _bayer_wikipedia_title(raw):
    """Spell a raw SIMBAD Bayer id for Wikipedia, or None if it isn't renderable.

        "* tau Cet"    → "Tau Ceti"
        "* eps Eri"    → "Epsilon Eridani"
        "* alf01 Cen"  → "Alpha Centauri"     (numeral dropped — system article)
        "* alf Cen A"  → "Alpha Centauri"     (component dropped — system article)
        "* b Vel"      → None                 (extension letter, not Greek)
        "** LDS 6248A" → None                 (double-system id, not this star)
        "*  10 CMi"    → None                 (Flamsteed shape — first token is a number)

    Degrades to None (never invents) on an unknown Greek token or unknown constellation, so the
    resolver moves on to the next candidate. Wikipedia's primary article for a Bayer star is the
    *system* name, so the component letter and superscript numeral are intentionally dropped.
    """
    if not raw or str(raw).strip().startswith("**"):
        return None
    body = strip_star_prefix(raw)            # strips "* " / "V* " / "NAME "; leaves "** " alone
    tokens = body.split()
    if len(tokens) < 2:
        return None
    m = _BAYER_TOKEN_RE.match(tokens[0])
    if not m:
        return None
    word = _GREEK_ENGLISH.get(m.group(1).lower())
    if word is None:
        return None                          # extension letter or non-Greek token
    genitive = constellation_genitive(tokens[1])
    if genitive is None:
        return None                          # unknown constellation — don't guess
    return "{} {}".format(word, genitive)


def _bayer_candidates(raw):
    """Ordered Wikipedia title candidates for a Bayer id.

    A numbered Bayer letter names a *distinct* member, not the system, so the numbered form is
    tried first and the bare/system form second::

        "* tau01 Eri" → ["Tau1 Eridani", "Tau Eridani"]     (τ¹ Eri is its own article)
        "* alf01 Cen" → ["Alpha1 Centauri", "Alpha Centauri"]
        "* tau Cet"   → ["Tau Ceti"]                          (no numeral — one form)

    Wikipedia titles a numbered member "Tau1 Eridani" (word + digit, no space, no superscript),
    with the bare form kept as a fallback. Returns [] if the id isn't a renderable Bayer.
    """
    base = _bayer_wikipedia_title(raw)
    if base is None:
        return []
    tokens = strip_star_prefix(raw).split()
    m = _BAYER_TOKEN_RE.match(tokens[0]) if tokens else None
    out = []
    if m and m.group(2):                     # a numeral is present
        num = m.group(2).lstrip("0") or "0"
        word, _sep, genitive = base.partition(" ")
        out.append("{}{} {}".format(word, num, genitive))   # "Tau1 Eridani"
    out.append(base)
    return out


def build_candidates(designations, main_id=None, name=None):
    """Ordered ``[(query_title, matched_on_label), …]`` candidates. Pure, offline.

    Order (strongest first): proper NAME → spelled Bayer → Flamsteed → HR → HD → GJ (both "GJ N"
    and "Gliese N") → HIP → MAIN_ID → the user-typed name. Case-insensitively de-duplicated,
    order preserved. ``matched_on_label`` is the raw designation string that produced the query.
    """
    out = []
    seen = set()

    def add(query, label):
        if not query:
            return
        q = str(query).strip()
        if not q or q.lower() in seen:
            return
        seen.add(q.lower())
        out.append((q, label))

    d = designations or {}

    nm = d.get("NAME")
    if nm:
        add(strip_star_prefix(nm), nm)          # "NAME Vega" → "Vega"

    bayer = d.get("Bayer")
    if bayer:
        for title in _bayer_candidates(bayer):
            add(title, bayer)

    flam = d.get("Flamsteed")
    if flam:
        add(format_star_designation(flam), flam)  # "*  10 CMi" → "10 Canis Minoris"

    for key in ("HR", "HD"):
        v = d.get(key)
        if v:
            add(v, v)

    gj = d.get("GJ")
    if gj:
        add(gj, gj)                              # "GJ 71"
        add(gj.replace("GJ", "Gliese", 1), gj)   # "Gliese 71" (Wikipedia's title form)

    hip = d.get("HIP")
    if hip:
        add(hip, hip)

    mid = main_id or d.get("MAIN_ID")
    if mid:
        add(strip_star_prefix(mid), mid)

    if name:
        add(name, name)                          # last resort / typed identifier

    return out


def _fetch_summary(title):
    """GET the Wikipedia REST summary for *title* (following redirects).

    Returns the parsed JSON dict, or **None on a 404** (a legitimate miss — returned without
    raising so ``_with_retries`` does not spin on it). Any other transport failure raises, so
    ``_with_retries`` retries and, exhausted, re-raises for the caller to classify.
    """
    import requests

    url = _WIKI_REST + urllib.parse.quote(str(title).replace(" ", "_"), safe="") + "?redirect=true"

    def _get():
        resp = requests.get(
            url,
            headers={"User-Agent": _WIKI_UA, "Accept": "application/json"},
            timeout=_WIKI_TIMEOUT,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    # retries=2 (not the default 3): this is a best-effort UI fetch iterated over several
    # candidates, so a failing title should give up quickly rather than sleep through a long
    # backoff ladder per candidate. No _timeout_ctx — requests carries an explicit timeout, and
    # _timeout_ctx mutates the process-global default socket timeout, which is unsafe when several
    # of the GUI's background workers run concurrently.
    return _with_retries(_get, retries=2)


def _fetch_extract(title):
    """Fetch the FULL article text (all sections, limited HTML) for *title* via the MediaWiki
    Action API. Best-effort → None on any failure, so the caller keeps the short REST-summary
    lead as a fallback. This is what makes the tab show the whole article, not just the lead.
    """
    import requests

    params = {
        "action": "query", "prop": "extracts", "format": "json",
        "redirects": 1, "titles": title,
    }

    def _get():
        resp = requests.get(
            _WIKI_API, params=params,
            headers={"User-Agent": _WIKI_UA, "Accept": "application/json"},
            timeout=_WIKI_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    try:
        data = _with_retries(_get, retries=2)
    except Exception:
        return None
    pages = ((data or {}).get("query") or {}).get("pages") or {}
    for page in pages.values():
        extract = page.get("extract")
        if extract:
            return extract
    return None


def _is_star_article(summary):
    """True iff *summary* looks like a real star / planetary-system article (pure guard).

    Layered, word-boundary matched (see _STAR_WORDS): a star word in the description accepts; a
    disqualifier word in the description rejects (so a constellation / film / company page is
    rejected even though its extract might contain "star"); a generic/absent description falls
    back to the lead extract (so a star described only as "X-ray source" is still recognised).
    """
    if not summary:
        return False
    if summary.get("type") == "disambiguation":
        return False
    desc = (summary.get("description") or "").strip()
    if desc:
        if _STAR_RE.search(desc):
            return True
        if _NON_STAR_RE.search(desc):
            return False
        # generic description (no star word, no disqualifier) → consult the lead extract
    return bool(_STAR_RE.search(summary.get("extract") or ""))


def _found(summary, query, matched_on):
    """Build the GUI-facing 'found' dict from a REST summary."""
    thumb = summary.get("thumbnail") or {}
    page = ((summary.get("content_urls") or {}).get("desktop") or {}).get("page")
    title = summary.get("title") or query
    extract_html = summary.get("extract_html")
    if not extract_html:
        extract = summary.get("extract") or ""
        # The REST extract_html path is already HTML; this plain-text fallback is not, so it
        # must be escaped or a stray <, >, & would be injected into the QTextBrowser as markup.
        extract_html = "<p>{}</p>".format(html.escape(extract)) if extract else ""
    return {
        "found": True,
        "title": title,
        "url": page or (_WIKI_PAGE + urllib.parse.quote(str(title).replace(" ", "_"), safe="")),
        "extract_html": extract_html,
        "summary_text": summary.get("extract") or "",
        "thumbnail_url": thumb.get("source"),
        "description": summary.get("description") or "",
        "matched_on": matched_on,
        "query": query,
    }


def resolve_and_fetch(designations=None, main_id=None, name=None):
    """Resolve the best star article and fetch its summary.

    Returns one of:
        {"found": True, title, url, extract_html, summary_text, thumbnail_url,
         description, matched_on, query}
        {"found": False, "tried": [candidate titles …]}
        {"error": "<friendly network message>"}

    When *designations* is None but *name* is given, a SIMBAD lookup is performed first to obtain
    designations (best-effort — on failure, *name* is still tried directly). Network only insofar
    as it actually fetches; pass *designations* to skip the SIMBAD round-trip.
    """
    if designations is None and name:
        try:
            from core.databases import compute_simbad_lookup
            sl = compute_simbad_lookup(name)
        except Exception:
            sl = None
        if isinstance(sl, dict) and "error" not in sl:
            designations = sl.get("designations")
            main_id = main_id or sl.get("main_id")

    candidates = build_candidates(designations, main_id, name)
    tried = []
    last_error = None
    for query, matched_on in candidates:
        tried.append(query)
        try:
            summary = _fetch_summary(query)
        except Exception as e:
            # A hard "can't reach Wikipedia at all" fails fast — every remaining candidate
            # would fail identically. A title-specific timeout / 5xx is remembered but we try
            # the next candidate, so a transient error on the strongest name doesn't sink a
            # lookup a weaker (e.g. HD/HIP) candidate could still satisfy.
            try:
                import requests
                if isinstance(e, requests.exceptions.ConnectionError):
                    return {"error": _network_error_msg(e, "Wikipedia")}
            except ImportError:
                pass
            last_error = _network_error_msg(e, "Wikipedia")
            continue
        if summary is None or not _is_star_article(summary):
            continue
        result = _found(summary, query, matched_on)
        # Upgrade the lead-only summary extract to the full article text (best-effort).
        full = _fetch_extract(result["title"])
        if full:
            result["extract_html"] = full
        return result

    if last_error is not None:
        return {"error": last_error}
    return {"found": False, "tried": tried}


def fetch_thumbnail(url):
    """Best-effort image fetch → raw bytes, or None on any failure (text renders regardless)."""
    if not url:
        return None
    try:
        import requests

        def _get():
            resp = requests.get(url, headers={"User-Agent": _WIKI_UA}, timeout=_WIKI_TIMEOUT)
            resp.raise_for_status()
            return resp.content

        data = _with_retries(_get)   # explicit requests timeout; no global _timeout_ctx (see above)
        return data or None
    except Exception:
        return None
