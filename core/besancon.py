"""core/besancon.py — Phase AM Tier-3 `besancon-query`: the Besançon Galaxy Model field-population
route that builds the sister project's T8 `age_dist` prior.

**Not `astroquery.besancon`.** That module targets the dead 2003 form (`modele_form.php`) + an
email-gated FTP pull from `modele2003/`. This talks directly to the **modern UWS 1.0 REST web
service** at `https://model.obs-besancon.fr/ws/` (the `galmod_client.py` protocol), which runs the
**renewed `m1612` model** and authenticates with an account (HTTP Basic Auth) instead of email.

**Live, stateful, and hosted by individuals** who ask that the service not take large or repeated
requests. Safeguards (per the 2026-07-23 policy check — no published limits, so these are courtesy):
  1. **Cache-first** — an identical query is served from `data/catalog_cache/` (30-day TTL) and never
     re-runs the model. The single biggest protection against "repeated requests".
  2. **30 s poll cadence** (the reference client's `ping_delay`), **one job at a time**, no concurrency.
  3. **Always DELETE the job** after retrieval — no accumulation.
  4. **`sendmail=0`** — never triggers their mail system.
  5. **Field-size guard** — `SOLI` (solid angle) capped; the model is smallfield-only.
  6. **Bounded total wait + server-side `EXECUTIONDURATION`** so nothing runs away.
  7. **Identifying User-Agent** (the BGM login) so operators can reach us, not silently block.
  8. **No live CI** — the offline tests use a saved fixture; any live check is manual + opt-in.

Credentials come from the environment: `BESANCON_USER` / `BESANCON_PASS` (register at
https://model.obs-besancon.fr/ws/subscribe.php). Missing creds → a curated `{"error"}`, never a crash.

**The output is a synthetic model, not observation** — every result carries a
`verify_against_observation` flag; T8 must still cross-check the age distribution against observational
field ages before pinning the prior (spec §4.4.2).
"""

import os

from core import catalog_cache
from core.shared import _network_error_msg, _route_error, _with_retries, _timeout_ctx

_BASE_URL = "https://model.obs-besancon.fr/ws"
_UWS_NS = "{http://www.ivoa.net/xml/UWS/v1.0}"
_XLINK_HREF = "{http://www.w3.org/1999/xlink}href"

_POLL_INTERVAL_S = 30.0            # the reference client's ping_delay — the polite cadence
_MAX_WAIT_S = 1800.0               # 30 min hard ceiling on total polling
_EXEC_DURATION_S = 1800            # server-side self-destruct for a runaway job
_SOLI_MAX_DEG2 = 10.0              # field-size guard (smallfield-only model)
_REQ_TIMEOUT = 60
_CACHE_TTL_S = 30 * 86400.0        # model output for identical params is stable → 30-day cache

_LOCAL_PRESET_LB = (90.0, 45.0)    # a representative mid-latitude, off-plane sightline for --local

# Pop code → Galactic component (BGM m1612 convention; exposed raw too, so a caller can regroup).
def _pop_group(pop):
    try:
        p = int(round(float(pop)))
    except (TypeError, ValueError):
        return "unknown"
    if 1 <= p <= 7:
        return "thin"
    if p == 8:
        return "thick"
    if p == 9:
        return "halo"
    if p == 10:
        return "bulge"
    return "other"


def _credentials():
    u = os.environ.get("BESANCON_USER")
    p = os.environ.get("BESANCON_PASS")
    if not u or not p:
        return None, None
    return u, p


# ── output parsing ────────────────────────────────────────────────────────────

def _parse_besancon_output(text):
    """Parse the fixed-width `output` catalogue into a list of per-star dicts.

    The file has a single `#`-prefixed header line naming the columns (V, B-V, …, Pop, Age, Mass,
    [M/H], [a/Fe], Dist, UU/VV/WW, …) followed by whitespace-separated numeric rows."""
    header = None
    rows = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            if header is None:
                header = s.lstrip("#").split()
            continue
        if header is None:
            continue
        vals = s.split()
        if not vals:
            continue
        row = {}
        for col, v in zip(header, vals):
            try:
                row[col] = float(v)
            except ValueError:
                row[col] = v
        rows.append(row)
    return header or [], rows


def _get(row, *names):
    """First present column value among aliases (columns vary slightly across model options)."""
    for n in names:
        if n in row and row[n] is not None:
            return row[n]
    return None


# ── derived age-distribution summary (pure Python, no numpy) ──────────────────

def _histogram(values, lo, hi, width):
    edges = []
    x = lo
    while x < hi - 1e-9:
        edges.append((x, min(x + width, hi)))
        x += width
    counts = [0] * len(edges)
    for v in values:
        if v is None:
            continue
        for i, (a, b) in enumerate(edges):
            if (a <= v < b) or (i == len(edges) - 1 and v == b):
                counts[i] += 1
                break
    n = sum(counts) or 1
    return [{"lo": round(a, 3), "hi": round(b, 3), "count": c, "fraction": round(c / n, 5)}
            for (a, b), c in zip(edges, counts)]


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else 0.5 * (xs[m - 1] + xs[m])


def _std(xs, mean=None):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return 0.0
    mu = mean if mean is not None else sum(xs) / len(xs)
    return (sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5


def build_age_dist(rows):
    """Derive the T8 `age_dist` summary from parsed catalogue rows: the age histogram, the
    mass-conditional age distribution, the thin/thick/halo/bulge mix, and the age–metallicity
    relation — all model-derived (carry the verify-against-observation flag)."""
    ages = [_get(r, "Age") for r in rows]
    fehs = [_get(r, "[M/H]", "M/H", "Met") for r in rows]
    masses = [_get(r, "Mass") for r in rows]
    n = len(rows)

    # population mix
    by_pop = {}
    group_counts = {}
    for r in rows:
        pop = _get(r, "Pop")
        key = str(int(round(float(pop)))) if pop is not None else "unknown"
        by_pop[key] = by_pop.get(key, 0) + 1
        g = _pop_group(pop)
        group_counts[g] = group_counts.get(g, 0) + 1
    denom = n or 1
    population_mix = {g: round(c / denom, 5) for g, c in group_counts.items()}

    # mass-conditional age
    mass_bins = [(0.0, 0.5), (0.5, 0.8), (0.8, 1.0), (1.0, 1.5), (1.5, 3.0), (3.0, 90.0)]
    mass_cond = []
    for a, b in mass_bins:
        sub = [_get(r, "Age") for r in rows
               if (m := _get(r, "Mass")) is not None and a <= m < b]
        if sub:
            mass_cond.append({"mass_lo": a, "mass_hi": b, "n": len(sub),
                              "mean_age_gyr": round(_mean(sub), 4),
                              "median_age_gyr": round(_median(sub), 4)})

    # age–metallicity relation
    amr = []
    for band in _histogram(ages, 0.0, 14.0, 2.0):
        a, b = band["lo"], band["hi"]
        sub = [f for r in rows
               if (ag := _get(r, "Age")) is not None and a <= ag < b
               and (f := _get(r, "[M/H]", "M/H", "Met")) is not None]
        if sub:
            mu = _mean(sub)
            amr.append({"age_lo": a, "age_hi": b, "n": len(sub),
                        "mean_feh": round(mu, 4), "std_feh": round(_std(sub, mu), 4)})

    return {
        "n_stars": n,
        "histogram": _histogram(ages, 0.0, 14.0, 1.0),
        "mean_age_gyr": round(_mean(ages), 4) if n else None,
        "median_age_gyr": round(_median(ages), 4) if n else None,
        "mass_conditional_age": mass_cond,
        "population_mix": population_mix,
        "population_by_pop_code": by_pop,
        "age_metallicity_relation": amr,
        "feh_mean": round(_mean(fehs), 4) if any(f is not None for f in fehs) else None,
        "feh_std": round(_std(fehs), 4) if any(f is not None for f in fehs) else None,
    }


# ── the UWS job run (cached) ──────────────────────────────────────────────────

def _run_job(user, password, params, contact, timeout_s):
    """Create → set params → run → poll (30 s) → retrieve → DELETE one UWS job. Returns parsed
    (header, rows) on success; raises on network/job error (caller translates to `_route_error`)."""
    import time
    import requests
    import xml.etree.ElementTree as ET

    sess = requests.Session()
    sess.auth = (user, password)
    sess.headers["User-Agent"] = (f"SpaceAndScienceFictionApp/besancon-query "
                                  f"(BGM account: {contact})")

    def _xml(r):
        r.raise_for_status()
        return ET.fromstring(r.text)

    jid = None
    try:
        with _timeout_ctx(_REQ_TIMEOUT + 10):
            root = _xml(_with_retries(sess.post, f"{_BASE_URL}/jobs", timeout=_REQ_TIMEOUT))
            jid = root.findtext(f"{_UWS_NS}jobId")
            if not jid:
                raise RuntimeError("Besançon service did not return a jobId")
            # server-side self-destruct + no email + parameters, then run
            sess.post(f"{_BASE_URL}/jobs/{jid}/executionduration",
                      data={"EXECUTIONDURATION": _EXEC_DURATION_S}, timeout=_REQ_TIMEOUT)
            r = _with_retries(sess.post, f"{_BASE_URL}/jobs/{jid}/parameters",
                              data=params, timeout=_REQ_TIMEOUT)
            r.raise_for_status()
            _with_retries(sess.post, f"{_BASE_URL}/jobs/{jid}/phase",
                          data={"PHASE": "RUN"}, timeout=_REQ_TIMEOUT).raise_for_status()

        # poll at the courtesy cadence
        waited, phase, job = 0.0, "PENDING", None
        while waited < timeout_s:
            time.sleep(_POLL_INTERVAL_S)
            waited += _POLL_INTERVAL_S
            job = _xml(sess.get(f"{_BASE_URL}/jobs/{jid}", timeout=_REQ_TIMEOUT))
            phase = job.findtext(f"{_UWS_NS}phase")
            if phase in ("COMPLETED", "ERROR", "ABORTED"):
                break
        if phase != "COMPLETED":
            if phase in ("ERROR", "ABORTED"):
                err = job.findtext(f"{_UWS_NS}errorSummary/{_UWS_NS}message") if job is not None else None
                raise RuntimeError(f"Besançon job {phase.lower()}"
                                  + (f": {err}" if err else ""))
            raise TimeoutError(f"Besançon job did not complete within {int(timeout_s)} s "
                               f"(phase={phase})")

        # retrieve the 'output' result
        results = job.find(f"{_UWS_NS}results")
        href = None
        if results is not None:
            for res in results.findall(f"{_UWS_NS}result"):
                if res.get("id") == "output":
                    href = res.get(_XLINK_HREF)
                    break
            if href is None:                        # fall back to the first result
                first = results.find(f"{_UWS_NS}result")
                href = first.get(_XLINK_HREF) if first is not None else None
        if not href:
            raise RuntimeError("Besançon job completed but returned no output result")
        text = _with_retries(sess.get, href, timeout=_REQ_TIMEOUT * 2).text
        return _parse_besancon_output(text)
    finally:
        if jid:                                     # always clean up — no job accumulation
            try:
                sess.delete(f"{_BASE_URL}/jobs/{jid}", timeout=_REQ_TIMEOUT)
            except Exception:
                pass


def besancon_query(glon=None, glat=None, local=False, area_deg2=1.0, dist_max_pc=100.0,
                   mag_max=None, sample_max=1000, contact_email=None, timeout_s=_MAX_WAIT_S):
    """Query the Besançon Galaxy Model (m1612) for a synthetic local field population and derive the
    T8 `age_dist` summary. `--local` samples a representative mid-latitude sightline; the `dist_max_pc`
    cut isolates the solar-neighbourhood slice. **Model-derived — carries a verify-against-observation
    flag.** Cached (30 d); missing `BESANCON_USER`/`BESANCON_PASS` → a curated error."""
    # ── validate ──
    if local and (glon is None or glat is None):
        glon, glat = _LOCAL_PRESET_LB
    if glon is None or glat is None:
        return _route_error("besancon-query requires --glon/--glat, or --local for a representative "
                            "mid-latitude sightline", ["besancon-query"])
    if area_deg2 is None or not (0 < area_deg2 <= _SOLI_MAX_DEG2):
        return _route_error(f"--area (solid angle, deg²) must be in (0, {_SOLI_MAX_DEG2}] — the model "
                            "is smallfield-only; tile several small fields for a wider survey",
                            ["besancon-query"])
    if dist_max_pc is None or dist_max_pc <= 0:
        return _route_error("--dist-max-pc must be > 0", ["besancon-query"])

    user, password = _credentials()
    if not user:
        return _route_error(
            "Besançon credentials not set — export BESANCON_USER / BESANCON_PASS "
            "(register at https://model.obs-besancon.fr/ws/subscribe.php). "
            "Put them in ~/.zshenv so subprocesses inherit them.", ["besancon-query"])

    dist_kpc = dist_max_pc / 1000.0
    params = {
        "Coor1_min": f"{glon:.4f}", "Coor1_max": f"{glon:.4f}",
        "Coor2_min": f"{glat:.4f}", "Coor2_max": f"{glat:.4f}",
        "SOLI": f"{area_deg2}", "KLEG": "1", "sendmail": "0",
        "Dist_min": "0.0", "Dist_max": f"{dist_kpc:.5f}", "Dist_step": f"{dist_kpc:.5f}",
    }
    if mag_max is not None:
        params["band_max"] = f"{mag_max}," + ",".join(["99."] * 8)

    contact = contact_email or user

    def _producer():
        try:
            header, rows = _run_job(user, password, params, contact, timeout_s)
        except (TimeoutError, RuntimeError) as e:
            return _route_error(str(e), ["besancon-query"])
        except Exception as e:
            return _route_error(_network_error_msg(e, "Besançon Galaxy Model"), ["besancon-query"])
        n = len(rows)
        sample = rows if (sample_max is None or n <= sample_max) else rows[:sample_max]
        return {
            "query": {"glon": glon, "glat": glat, "local": bool(local),
                      "area_deg2": area_deg2, "dist_max_pc": dist_max_pc, "mag_max": mag_max},
            "model_version": "m1612",
            "n_stars": n,
            "columns": header,
            "catalogue_sample": sample,
            "catalogue_truncated": n > len(sample),
            "age_dist": build_age_dist(rows),
            "coverage": {
                "model": "Besançon Galaxy Model (m1612) — synthetic population synthesis",
                "sightline_lb": [glon, glat], "dist_max_pc": dist_max_pc,
                "verify_against_observation": True,
                "notes": [
                    "MODEL-DERIVED, NOT OBSERVATION — T8 must cross-check the age distribution "
                    "against observational field ages (asteroseismic / spectroscopic AMR / local WD) "
                    "before pinning the age_dist prior.",
                    "Single representative sightline; a distance cut (not the full line of sight) "
                    "isolates the local slice. Widen coverage by tiling several small fields.",
                    "Pop→component mapping (thin=1–7, thick=8, halo=9, bulge=10) is the BGM m1612 "
                    "convention — population_by_pop_code is exposed raw so it can be regrouped.",
                ],
            },
            "units": {"age_gyr": "Gyr", "mass": "M_sun", "[M/H]": "dex", "dist": "kpc (Dist column)",
                      "UU/VV/WW": "km/s", "area": "deg^2"},
        }

    sig = {"glon": round(glon, 4), "glat": round(glat, 4), "area": area_deg2,
           "dist_max_pc": dist_max_pc, "mag_max": mag_max, "sample_max": sample_max}
    return catalog_cache.cached("besancon", sig, _producer, ttl_s=_CACHE_TTL_S)
