"""3D interstellar-dust extinction queries (Phase T2 Part A).

A read-only ISM-dust layer over the `dustmaps` package — the optional 'dust'
extra (`requirements-dust.txt`: dustmaps, healpy, …). It is the ONLY module that
imports `dustmaps`/`healpy`, and it does so lazily (function-local), so the
stellar layer (`core/calculators.py` etc.) stays importable on a checkout that
never installed the extra (e.g. native Windows, where pip has no healpy wheel).
Run the dust path from the WSL/Linux venv — see `docs/integration.md`.

Two maps (selected via `map_sel`):
  - "near-field" → Leike, Glatzle & Enßlin 2020 (`dustmaps.leike2020`):
       Cartesian box ±370/±370/±270 pc, 1-pc voxels, native unit
       = extinction DENSITY in e-foldings/kpc (Gaia G-band optical depth).
  - "edenhofer"  → Edenhofer et al. 2024 (`dustmaps.edenhofer2023`; note the
       module/key is 2023, the A&A paper is 2024): HEALPix sphere ~69 pc–1.25 kpc,
       native unit = ZGR23 (Zhang, Green & Rix 2023) `E` per pc.
  - "auto"       → Leike ≤ ~69 pc, Edenhofer > ~69 pc (no overlap double-count:
       we query DIFFERENTIAL density and integrate per-segment ourselves, which
       sidesteps dustmaps' `integrated=True` inner-<69 pc add-back entirely).

Output is standardized to A_V (mag, R_V=3.1) via two per-map scalar conversions
pinned against the cited extinction curves (see the constants below), with each
bin echoing its native value + `native_quantity` and a top-level `units` string.
"""

import math
import pathlib
import warnings

# dustmaps warns (to stderr) the first time its config is imported if ~/.dustmapsrc
# is absent — harmless, since we set data_dir programmatically. Silence it.
warnings.filterwarnings("ignore", message=".*[Cc]onfiguration file not found.*")

# astropy + numpy are BASE dependencies (always present). dustmaps/healpy are the
# OPTIONAL extra and are imported lazily inside the functions below.
import numpy as np
import astropy.units as u
from astropy.coordinates import SkyCoord, CartesianRepresentation

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
# Fetch-once cache, gitignored, on the native filesystem (GCNS space_app.db model).
_DUST_CACHE_DIR = _REPO_ROOT / "data" / "dust"

# ── native → A_V (mag, R_V=3.1) conversions — the T2 build-time pin ───────────
# Edenhofer 2024 / ZGR23: multiply the ZGR23 unit-extinction E by 2.8 to get A_V
# (Edenhofer et al. 2024, from the Zhang, Green & Rix 2023 extinction curve at
# https://doi.org/10.5281/zenodo.6674521).
_AV_PER_ZGR23_E = 2.8
# Leike 2020: integrating the density (e-foldings/kpc) over the path (kpc) yields
# the Gaia-G optical depth tau_G in e-foldings (natural log). A_G = (2.5/ln10)·tau_G,
# then A_V = 1.202·A_G at R_V=3.1 (G→V band ratio; O'Neill et al. 2024, Local Bubble).
_EFOLD_TO_AG = 2.5 / math.log(10.0)        # 1.085736 — optical depth → A_G (mag)
_AG_TO_AV = 1.202                          # A_G → A_V at R_V=3.1
_LEIKE_TAU_TO_AV = _EFOLD_TO_AG * _AG_TO_AV  # ≈ 1.30506

# Deliberately kept at full precision here (3.2615637771), NOT unified with
# core.shared.LY_PER_PC (3.26156) — that rounded value is pinned across tests/docs
# and the downstream consumer, so it stays. The ~1.2e-6 relative difference is
# sub-ppm on any dust sightline length; not worth breaking the pinned 3.26156 (P4.5).
_LY_PER_PC = 3.2615637771

# Seam between the two maps under "auto" (Edenhofer's inner edge ≈ 69 pc).
_SEAM_PC = 69.0
_SEAM_HALFWIDTH_PC = 5.0     # bins within this of the seam are flagged "seam"
_CAVITY_AV = 1e-2            # below this A_V with σ ≥ A_V → low_dust_high_uncertainty

UNITS = "A_V_mag_RV3.1"

# query.py / CLI map selector → dustmaps map key.
_MAP_KEY = {"near-field": "leike2020", "edenhofer": "edenhofer2023"}
_NATIVE_QTY = {
    "leike2020": "leike2020_density_efoldings_per_kpc_gaiaG",
    "edenhofer2023": "edenhofer2023_ZGR23_E_per_pc",
}
# Cached map data filenames (under the dustmaps data dir) for --check / load.
_MAP_FILE = {
    "leike2020": ("leike_2020", "mean_std.h5"),
    "edenhofer2023": ("edenhofer_2023", "mean_and_std_healpix.fits"),
}

_DUST_EXTRA_MSG = (
    "Dust maps require the optional 'dust' extra — install it in the WSL/Linux "
    "venv with `pip install -r requirements-dust.txt` (dustmaps needs healpy, "
    "which has no native-Windows pip wheel)."
)

_MAP_CACHE = {}  # map_key -> dustmaps Query object (one-time per-process load)


# ── dependency / cache plumbing ──────────────────────────────────────────────

def _dustmaps_available() -> bool:
    """True iff the optional dust extra (dustmaps + healpy) is importable."""
    try:
        import dustmaps  # noqa: F401
        import healpy     # noqa: F401
        return True
    except Exception:
        return False


def _set_cache_dir():
    """Point dustmaps at the repo-local, gitignored dust cache (native FS)."""
    _DUST_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    from dustmaps.config import config
    config["data_dir"] = str(_DUST_CACHE_DIR)


def _map_path(map_key: str) -> pathlib.Path:
    sub, fn = _MAP_FILE[map_key]
    return _DUST_CACHE_DIR / sub / fn


def _load_map(map_key: str):
    """Lazily construct + process-cache a dustmaps Query. Differential mode for
    Edenhofer (integrated=False) so we never trigger the inner-<69 pc add-back.

    Returns (query, None) or (None, {"error": str}).
    """
    if map_key in _MAP_CACHE:
        return _MAP_CACHE[map_key], None
    _set_cache_dir()
    try:
        if map_key == "leike2020":
            from dustmaps.leike2020 import Leike2020Query
            q = Leike2020Query()
        elif map_key == "edenhofer2023":
            from dustmaps.edenhofer2023 import Edenhofer2023Query
            q = Edenhofer2023Query(load_samples=False, integrated=False, flavor="main")
        else:
            return None, {"error": f"Unknown dust map '{map_key}'."}
    except FileNotFoundError:
        return None, {"error": f"{map_key} map data not fetched — run CLI option "
                               f"59 (dust-fetch) first."}
    except Exception as e:  # corrupt file, healpy mismatch, etc.
        return None, {"error": f"Failed to load {map_key} dust map: {e}"}
    _MAP_CACHE[map_key] = q
    return q, None


def _query_native(map_key: str, q, coords):
    """Query mean + std density for a SkyCoord array. Returns (mean, std) arrays."""
    if map_key == "leike2020":
        mean = np.atleast_1d(np.asarray(q.query(coords, component="mean"), dtype=float))
        std = np.atleast_1d(np.asarray(q.query(coords, component="std"), dtype=float))
    else:  # edenhofer2023
        mean = np.atleast_1d(np.asarray(q.query(coords, mode="mean"), dtype=float))
        std = np.atleast_1d(np.asarray(q.query(coords, mode="std"), dtype=float))
    return mean, std


def _to_av(map_key: str, density_mean: float, density_std: float, dlen_pc: float):
    """Convert a per-bin native density + its σ to (a_v, sigma_av) over a bin of
    physical length dlen_pc. NaN density (out of coverage) → (None, None)."""
    if density_mean is None or not np.isfinite(density_mean):
        return None, None
    if map_key == "leike2020":
        # density in e-foldings/kpc → tau over the bin (kpc) → A_V.
        tau = density_mean * (dlen_pc / 1000.0)
        av = _LEIKE_TAU_TO_AV * tau
        sig = (_LEIKE_TAU_TO_AV * abs(density_std) * (dlen_pc / 1000.0)
               if density_std is not None and np.isfinite(density_std) else None)
    else:  # edenhofer2023: density in ZGR23 E/pc → E over the bin → A_V.
        e_bin = density_mean * dlen_pc
        av = _AV_PER_ZGR23_E * e_bin
        sig = (_AV_PER_ZGR23_E * abs(density_std) * dlen_pc
               if density_std is not None and np.isfinite(density_std) else None)
    return av, sig


# ── the shared sightline-integration engine ──────────────────────────────────

def _integrate(coords, helio_pc, report_pc, dlen_pc, map_sel, report_l, report_b):
    """Integrate extinction along a sampled path.

    coords: SkyCoord array (N bin centers); helio_pc: heliocentric distance per
    bin (drives map ownership under auto); report_pc: the distance reported per
    bin (== helio_pc for a sightline; path-from-origin for dust-between);
    dlen_pc: each bin's physical length.

    Returns the bins[] + cumulative_* + units + notes block shared by both
    dust-sightline and dust-between, or {"error": str}.
    """
    n = len(helio_pc)
    if map_sel == "auto":
        owner = ["leike2020" if d <= _SEAM_PC else "edenhofer2023" for d in helio_pc]
    else:
        owner = [_MAP_KEY[map_sel]] * n

    mean = np.full(n, np.nan)
    std = np.full(n, np.nan)
    # Query each owning map once over its subset of bins (vectorized).
    for mk in sorted(set(owner)):
        idx = [i for i in range(n) if owner[i] == mk]
        q, err = _load_map(mk)
        if err:
            return err
        m_sub, s_sub = _query_native(mk, q, coords[idx])
        for k, i in enumerate(idx):
            mean[i] = m_sub[k]
            std[i] = s_sub[k]

    bins = []
    cum_av = 0.0
    cum_var = 0.0
    any_oob = False
    any_seam = False
    any_cavity = False
    for i in range(n):
        mk = owner[i]
        av, sig = _to_av(mk, mean[i], std[i], dlen_pc[i])
        notes = []
        seam = (map_sel == "auto"
                and abs(helio_pc[i] - _SEAM_PC) <= _SEAM_HALFWIDTH_PC)
        if seam:
            any_seam = True
            notes.append("seam")
        if av is None:
            any_oob = True
            notes.append("out_of_coverage")
            a_v = a_v_lo = a_v_hi = None
        else:
            cum_av += av
            if sig is not None:
                cum_var += sig * sig
            a_v = av
            a_v_lo = max(0.0, av - sig) if sig is not None else None
            a_v_hi = av + sig if sig is not None else None
            if av < _CAVITY_AV and sig is not None and sig >= av:
                any_cavity = True
                notes.append("low_dust_high_uncertainty")
        cum_sig = math.sqrt(cum_var) if cum_var > 0 else 0.0
        bins.append({
            "dist_pc": float(report_pc[i]),
            "dist_ly": float(report_pc[i]) * _LY_PER_PC,
            "map": mk,
            "a_v": a_v,
            "a_v_lo": a_v_lo,
            "a_v_hi": a_v_hi,
            "cumulative_a_v": cum_av,
            "cumulative_a_v_lo": max(0.0, cum_av - cum_sig),
            "cumulative_a_v_hi": cum_av + cum_sig,
            "native_value": (None if not np.isfinite(mean[i]) else float(mean[i])),
            "native_quantity": _NATIVE_QTY[mk],
            "seam": seam,
            "notes": notes,
        })

    cum_sig = math.sqrt(cum_var) if cum_var > 0 else 0.0
    notes = []
    if any_seam:
        notes.append("seam_crossed")
    if any_oob:
        notes.append("out_of_coverage" if any(b["a_v"] is not None for b in bins)
                     else "all_out_of_coverage")
    if any_cavity:
        notes.append("low_dust_high_uncertainty")
    return {
        "bins": bins,
        "cumulative_a_v": cum_av,
        "cumulative_a_v_lo": max(0.0, cum_av - cum_sig),
        "cumulative_a_v_hi": cum_av + cum_sig,
        "units": UNITS,
        "rv": 3.1,
        "notes": notes,
    }


def _bin_geometry(dist_start_pc, dist_end_pc, n_steps):
    """Edges → (center distances, bin lengths). Bin i spans [edge_i, edge_{i+1}]."""
    edges = np.linspace(dist_start_pc, dist_end_pc, n_steps + 1)
    centers = 0.5 * (edges[:-1] + edges[1:])
    lengths = np.diff(edges)
    return centers, lengths


def _galactic_lb_of(coords1) -> tuple:
    """(l, b) in degrees of a single SkyCoord, in galactic frame."""
    g = coords1.galactic
    return float(np.atleast_1d(g.l.deg)[0]), float(np.atleast_1d(g.b.deg)[0])


# ── direction resolution for dust-sightline --star/--id ──────────────────────

def _resolve_direction(star=None, source_id=None):
    """Resolve a star/id to a heliocentric unit direction (ICRS cartesian) + l,b.

    Returns {"unit": (ux,uy,uz), "name": str} or {"error": str}. Sol/origin has
    no direction → error.
    """
    from core.calculators import _resolve_star_position
    if source_id is not None:
        from core.databases import _resolve_gcns_row, _gcns_endpoint_xyz
        row = _resolve_gcns_row(source_id=source_id)
        if "error" in row:
            return row
        xyz, err = _gcns_endpoint_xyz(row, "star")
        if err:
            return err
        x, y, z = xyz
        name = row.get("star_name") or str(source_id)
    else:
        rec = _resolve_star_position(star)
        if "error" in rec:
            return rec
        x, y, z = rec["x"], rec["y"], rec["z"]
        name = rec["name"]
    r = math.sqrt(x * x + y * y + z * z)
    if r <= 1e-9:
        return {"error": f"'{name}' is at the origin — it has no sightline "
                         f"direction (use --l/--b or --ra/--dec)."}
    return {"unit": (x / r, y / r, z / r), "name": name}


def _endpoint(star=None, source_id=None):
    """Resolve a dust-between endpoint to a heliocentric position in pc + info.

    Returns {"pos_pc": (x,y,z), "info": {...}} or {"error": str}. Sol → origin.
    """
    from core.calculators import _resolve_star_position
    if source_id is not None:
        from core.databases import _resolve_gcns_row, _gcns_endpoint_xyz
        row = _resolve_gcns_row(source_id=source_id)
        if "error" in row:
            return row
        xyz, err = _gcns_endpoint_xyz(row, "endpoint")
        if err:
            return err
        x_ly, y_ly, z_ly = xyz
        info = {"name": row.get("star_name") or str(source_id),
                "source": "gcns", "ly": row.get("light_years")}
    else:
        rec = _resolve_star_position(star)
        if "error" in rec:
            return rec
        x_ly, y_ly, z_ly = rec["x"], rec["y"], rec["z"]
        info = {"name": rec["name"], "source": rec.get("source", ""), "ly": rec["ly"]}
    pos_pc = (x_ly / _LY_PER_PC, y_ly / _LY_PER_PC, z_ly / _LY_PER_PC)
    info["dist_pc"] = math.sqrt(sum(c * c for c in pos_pc))
    info["dist_ly"] = info["dist_pc"] * _LY_PER_PC
    return {"pos_pc": pos_pc, "info": info}


# ── public Part-A API ────────────────────────────────────────────────────────

def compute_dust_sightline(l=None, b=None, ra=None, dec=None, star=None, id=None,
                           dist_start_pc=0.0, dist_end_pc=None, n_steps=50,
                           step_pc=None, map_sel="auto") -> dict:
    """Extinction profile along one direction (Galactic l/b, equatorial ra/dec,
    or the direction of a --star/--id), from dist_start_pc to dist_end_pc.

    Returns the integration block (see _integrate) plus {map, frame, l, b,
    dist_start_pc, dist_end_pc, n_steps} or {"error": str}.
    """
    if not _dustmaps_available():
        return {"error": _DUST_EXTRA_MSG}
    if map_sel not in ("near-field", "edenhofer", "auto"):
        return {"error": "map must be 'near-field', 'edenhofer', or 'auto'."}

    # Exactly one direction mode.
    modes = [("lb", l is not None and b is not None),
             ("radec", ra is not None and dec is not None),
             ("star", star is not None or id is not None)]
    chosen = [m for m, on in modes if on]
    if len(chosen) != 1:
        return {"error": "Supply exactly one direction: --l/--b, --ra/--dec, or "
                         "--star/--id."}
    mode = chosen[0]

    # Distance range + binning.
    if dist_end_pc is None:
        return {"error": "dist_end_pc is required."}
    if dist_start_pc is None or dist_start_pc < 0:
        return {"error": "dist_start_pc must be ≥ 0."}
    if dist_end_pc <= dist_start_pc:
        return {"error": "dist_end_pc must be greater than dist_start_pc."}
    if step_pc is not None:
        if step_pc <= 0:
            return {"error": "step_pc must be positive."}
        n_steps = max(1, int(round((dist_end_pc - dist_start_pc) / step_pc)))
    else:
        try:
            n_steps = int(n_steps)
        except (TypeError, ValueError):
            return {"error": "n_steps must be a positive integer."}
        if n_steps < 1:
            return {"error": "n_steps must be a positive integer."}

    centers, lengths = _bin_geometry(dist_start_pc, dist_end_pc, n_steps)

    # Build the bin-center SkyCoord array for the chosen direction.
    if mode == "lb":
        coords = SkyCoord(l=l * u.deg, b=b * u.deg, distance=centers * u.pc,
                          frame="galactic")
        frame, rl, rb = "galactic", float(l), float(b)
    elif mode == "radec":
        coords = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, distance=centers * u.pc,
                          frame="icrs")
        rl, rb = _galactic_lb_of(coords[0])
        frame = "icrs"
    else:  # star/id direction
        d = _resolve_direction(star=star, source_id=id)
        if "error" in d:
            return d
        ux, uy, uz = d["unit"]
        rep = CartesianRepresentation(ux * centers * u.pc, uy * centers * u.pc,
                                      uz * centers * u.pc)
        coords = SkyCoord(rep, frame="icrs")
        rl, rb = _galactic_lb_of(coords[0])
        frame = f"star:{d['name']}"

    block = _integrate(coords, helio_pc=centers, report_pc=centers,
                       dlen_pc=lengths, map_sel=map_sel, report_l=rl, report_b=rb)
    if "error" in block:
        return block
    return {
        "map": map_sel, "frame": frame, "l": rl, "b": rb,
        "dist_start_pc": float(dist_start_pc), "dist_end_pc": float(dist_end_pc),
        "n_steps": int(n_steps), **block,
    }


def compute_dust_between(star1=None, id1=None, star2=None, id2=None,
                         n_steps=50, step_pc=None, map_sel="auto") -> dict:
    """Extinction along the straight line between two stars (Sol/Sun → origin).

    Returns the integration block plus {star1_info, star2_info, separation_pc,
    separation_ly, map, frame, n_steps} or {"error": str}. Per-bin dist_pc is the
    path distance from star1; map ownership uses each bin's heliocentric distance.
    """
    if not _dustmaps_available():
        return {"error": _DUST_EXTRA_MSG}
    if map_sel not in ("near-field", "edenhofer", "auto"):
        return {"error": "map must be 'near-field', 'edenhofer', or 'auto'."}

    e1 = _endpoint(star=star1, source_id=id1)
    if "error" in e1:
        return e1
    e2 = _endpoint(star=star2, source_id=id2)
    if "error" in e2:
        return e2

    p1 = np.array(e1["pos_pc"], dtype=float)
    p2 = np.array(e2["pos_pc"], dtype=float)
    sep_pc = float(np.linalg.norm(p2 - p1))
    if sep_pc <= 1e-9:
        return {"error": "The two endpoints are the same point."}

    if step_pc is not None:
        if step_pc <= 0:
            return {"error": "step_pc must be positive."}
        n_steps = max(1, int(round(sep_pc / step_pc)))
    else:
        try:
            n_steps = int(n_steps)
        except (TypeError, ValueError):
            return {"error": "n_steps must be a positive integer."}
        if n_steps < 1:
            return {"error": "n_steps must be a positive integer."}

    # Sample bin centers along the segment; each bin spans sep_pc/n_steps.
    fr_edges = np.linspace(0.0, 1.0, n_steps + 1)
    fr_centers = 0.5 * (fr_edges[:-1] + fr_edges[1:])
    pts = p1[None, :] + fr_centers[:, None] * (p2 - p1)[None, :]
    helio_pc = np.linalg.norm(pts, axis=1)
    path_pc = fr_centers * sep_pc
    lengths = np.full(n_steps, sep_pc / n_steps)

    coords = SkyCoord(
        CartesianRepresentation(pts[:, 0] * u.pc, pts[:, 1] * u.pc, pts[:, 2] * u.pc),
        frame="icrs")

    block = _integrate(coords, helio_pc=helio_pc, report_pc=path_pc,
                       dlen_pc=lengths, map_sel=map_sel, report_l=None, report_b=None)
    if "error" in block:
        return block
    return {
        "map": map_sel, "frame": "star-to-star", "n_steps": int(n_steps),
        "star1_info": e1["info"], "star2_info": e2["info"],
        "separation_pc": sep_pc, "separation_ly": sep_pc * _LY_PER_PC,
        **block,
    }


def integrate_segment_av(p1_pc, p2_pc, step_pc=5.0, map_sel="auto") -> dict:
    """Integrated A_V (mag, R_V=3.1) along the segment between two heliocentric
    points (pc) — the per-leg cost primitive for dust-weighted routing (Part B).

    Returns {a_v, a_v_lo, a_v_hi, n_steps, covered} (a_v sums only covered bins;
    `covered` is False if any bin fell out of a map box) or {"error": str}.
    Assumes the caller has already preflighted the extra/map availability.
    """
    p1 = np.asarray(p1_pc, dtype=float)
    p2 = np.asarray(p2_pc, dtype=float)
    seg = float(np.linalg.norm(p2 - p1))
    if seg <= 1e-9:
        return {"a_v": 0.0, "a_v_lo": 0.0, "a_v_hi": 0.0, "n_steps": 0, "covered": True}
    n = max(1, int(round(seg / step_pc)))
    fr_edges = np.linspace(0.0, 1.0, n + 1)
    fr_centers = 0.5 * (fr_edges[:-1] + fr_edges[1:])
    pts = p1[None, :] + fr_centers[:, None] * (p2 - p1)[None, :]
    helio_pc = np.linalg.norm(pts, axis=1)
    lengths = np.full(n, seg / n)
    coords = SkyCoord(
        CartesianRepresentation(pts[:, 0] * u.pc, pts[:, 1] * u.pc, pts[:, 2] * u.pc),
        frame="icrs")
    block = _integrate(coords, helio_pc=helio_pc, report_pc=fr_centers * seg,
                       dlen_pc=lengths, map_sel=map_sel, report_l=None, report_b=None)
    if "error" in block:
        return block
    covered = all(b["a_v"] is not None for b in block["bins"])
    return {
        "a_v": block["cumulative_a_v"],
        "a_v_lo": block["cumulative_a_v_lo"],
        "a_v_hi": block["cumulative_a_v_hi"],
        "n_steps": n,
        "covered": covered,
    }


def get_dust_map_status() -> list:
    """File-presence/size status of the cached dust maps, in menu order.

    Pure pathlib — does NOT import dustmaps/healpy, so it works on a checkout
    without the optional 'dust' extra (the files can be present regardless). Used
    by the Database Status panel (option 57). Returns a list of
    {map, label, path, present, size_mb}.
    """
    labels = {
        "leike2020": "Dust Map: Leike 2020 (near-field)",
        "edenhofer2023": "Dust Map: Edenhofer 2024",
    }
    out = []
    for mk in ("leike2020", "edenhofer2023"):
        path = _map_path(mk)
        present = path.is_file()
        size_mb = round(path.stat().st_size / 1e6, 1) if present else None
        out.append({"map": mk, "label": labels[mk], "path": str(path),
                    "present": present, "size_mb": size_mb})
    return out


def compute_dust_fetch(map_sel="auto", check_only=False, progress_callback=None) -> dict:
    """Download (or report status of) the dust map data into the gitignored cache.

    map_sel "auto" handles both maps; "near-field"/"edenhofer" one map. With
    check_only, reports cached/size/path without downloading. Returns
    {map, cache_dir, fetched:[{map, status, path, size_mb}]} or {"error": str}.
    """
    if not _dustmaps_available():
        return {"error": _DUST_EXTRA_MSG}
    _set_cache_dir()
    keys = (["leike2020", "edenhofer2023"] if map_sel == "auto"
            else [_MAP_KEY.get(map_sel)])
    if keys == [None]:
        return {"error": "map must be 'near-field', 'edenhofer', or 'auto'."}

    def _emit(msg):
        if progress_callback:
            progress_callback(msg)

    fetched = []
    for mk in keys:
        path = _map_path(mk)
        exists = path.is_file()
        size_mb = round(path.stat().st_size / 1e6, 1) if exists else None
        if check_only:
            fetched.append({"map": mk, "status": "cached" if exists else "missing",
                            "path": str(path), "size_mb": size_mb})
            continue
        if exists:
            _emit(f"{mk}: already cached ({size_mb} MB).")
            fetched.append({"map": mk, "status": "cached", "path": str(path),
                            "size_mb": size_mb})
            continue
        _emit(f"{mk}: downloading (this is large — Edenhofer ≈ 3.2 GB)…")
        try:
            if mk == "leike2020":
                from dustmaps.leike2020 import fetch as _fetch
                _fetch()
            else:
                from dustmaps.edenhofer2023 import fetch as _fetch
                _fetch()
        except Exception as e:
            from core.shared import _network_error_msg
            return {"error": _network_error_msg(e, "dust map server (Zenodo)")}
        size_mb = round(path.stat().st_size / 1e6, 1) if path.is_file() else None
        _emit(f"{mk}: done ({size_mb} MB).")
        fetched.append({"map": mk, "status": "downloaded", "path": str(path),
                        "size_mb": size_mb})

    return {"map": map_sel, "cache_dir": str(_DUST_CACHE_DIR), "fetched": fetched}
