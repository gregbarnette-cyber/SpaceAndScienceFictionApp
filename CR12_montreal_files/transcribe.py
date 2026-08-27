#!/usr/bin/env python3
"""CR-12 — regenerate core.cooling_tables._WD_COOLING from the archived Bedard 2020
Montreal WD cooling sequences (this directory's seq_0XX_thick.txt files).

Reproducible, offline, deterministic. Fixes the sparse-≤1.00 cooling-age defect (F3): the
old grid sampled ≤1.00 M_sun at ~10 nodes, skipping the ~18k-30k K mid-track, so linear-in-Teff
interpolation over-read the convex age(Teff) curve by +2..+86%. This re-derives the whole
0.40-1.30 grid (uniform 0.05 M_sun spacing, D-A) as one dense adaptive resample so linear interp
reproduces the source Age to <0.5%.

Run:  venv/bin/python CR12_montreal_files/transcribe.py [--emit out.txt]
It prints a validation report and (with --emit, ONLY IF validation passes) writes the
`_WD_COOLING = {...}` literal to splice into core/cooling_tables.py. **Exits non-zero on any
validation failure and does not emit** (so a build/CI harness cannot ship a known-bad grid).
radius/Teff/L stay source-faithful; only the age axis is densified.
"""
import argparse
import math
import os
import sys

# solar constants (must match core.cooling / cooling_tables)
_RSUN_CM = 6.957e10
_LSUN_ERG = 3.828e33
_TSUN = 5772.0

# 0.40-1.30 M_sun at 0.05 spacing (D-A): the tool's grid range.
_MASSES = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85,
           0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30]

# §3.1 verification anchors (Teff, K) — the re-gate targets. Sirius B's regime is 25970.
_ANCHOR_TEFFS = [25970.0, 15000.0, 10000.0, 6000.0]

# adaptive subsample tolerances
_AGE_TOL_REL = 0.005     # 0.5% relative age error (well inside the ~2% re-gate)
_AGE_TOL_ABS = 1.0e-4    # Gyr — absolute floor: don't over-sample the sub-Myr young/hot tail
_RAD_TOL_REL = 5.0e-4    # 0.05% radius (R nearly flat in Teff; rarely binds)
# CP1-F3: also bound Teff-at-age (the tool queries Teff/L/HZ at a given age too), but only in the
# output-relevant band — above ~40000 K Teff is Kopparapu-out-of-range/flagged, so the age floor governs.
_TEFF_TOL_REL = 0.005    # 0.5% Teff-at-age error
_TEFF_BAND_MIN = 2000.0  # K — cover the whole HZ-relevant range through the cool tail
_TEFF_BAND_MAX = 40000.0 # K — above this, Teff is flagged out-of-range regardless

# emit / gate
_AGE_DP, _TEFF_DP, _L_DP, _RAD_DP = 6, 4, 5, 6   # literal precision (must match the format strings)
_CLOSURE_GATE = 0.01     # matches tests/test_cooling_hz.py::test_closure_consistency
_ANCHOR_GATE = 2.0       # % — the WB re-gate tolerance

_HERE = os.path.dirname(os.path.abspath(__file__))


def parse_seq(path):
    """Return the full source sequence as [(age_gyr, teff_k, log10_l, radius_rsun), ...],
    sorted ascending by age, restricted to the strictly-monotone-cooling (Teff-decreasing) run."""
    rows = []
    with open(path) as f:
        for line in f:
            toks = line.split()
            # a model's PRIMARY line: 6 tokens, first is the integer model index.
            if len(toks) != 6 or not toks[0].isdigit():
                continue
            teff = float(toks[1])
            r_cm = float(toks[3])
            age_yr = float(toks[4])
            l_erg = float(toks[5])
            rows.append((age_yr / 1e9, teff, math.log10(l_erg / _LSUN_ERG), r_cm / _RSUN_CM))
    if not rows:                                                   # CP1-F4
        raise SystemExit(f"parse_seq: no model rows parsed from {path} "
                         f"(empty/truncated/renamed file, or column-layout drift?)")
    rows.sort(key=lambda r: r[0])
    # keep only the strictly-Teff-decreasing run from the hottest model onward (defensive;
    # the Bedard sequences are already monotone, so this is expected to drop 0 rows).
    mono = [rows[0]]
    for r in rows[1:]:
        if r[1] < mono[-1][1]:
            mono.append(r)
    return mono, len(rows) - len(mono)


def _interp_age_at_teff(lo, hi, teff):
    w = (teff - lo[1]) / (hi[1] - lo[1])
    return lo[0] + w * (hi[0] - lo[0])


def _interp_rad_at_teff(lo, hi, teff):
    w = (teff - lo[1]) / (hi[1] - lo[1])
    return lo[3] + w * (hi[3] - lo[3])


def _interp_teff_at_age(lo, hi, age):
    if hi[0] == lo[0]:
        return lo[1]
    w = (age - lo[0]) / (hi[0] - lo[0])
    return lo[1] + w * (hi[1] - lo[1])


def adaptive_subsample(rows):
    """Greedy: keep the endpoints, insert the worst-reproduced source row until the
    linear-in-Teff interpolant matches every source row's age, radius (age-at-Teff) AND — within
    the output-relevant Teff band — Teff-at-age, all within tolerance."""
    n = len(rows)
    if n <= 2:
        return list(range(n))
    kept = [0, n - 1]
    while True:
        worst_norm, worst_j = 0.0, -1
        for s in range(len(kept) - 1):
            lo, hi = rows[kept[s]], rows[kept[s + 1]]
            for j in range(kept[s] + 1, kept[s + 1]):
                aj, tj, _, rj = rows[j]
                norm = max(abs(_interp_age_at_teff(lo, hi, tj) - aj) / max(_AGE_TOL_REL * aj, _AGE_TOL_ABS),
                           abs(_interp_rad_at_teff(lo, hi, tj) - rj) / (_RAD_TOL_REL * rj))
                if _TEFF_BAND_MIN <= tj <= _TEFF_BAND_MAX:         # CP1-F3
                    norm = max(norm, abs(_interp_teff_at_age(lo, hi, aj) - tj) / (_TEFF_TOL_REL * tj))
                if norm > worst_norm:
                    worst_norm, worst_j = norm, j
        if worst_norm <= 1.0 or worst_j < 0:
            break
        kept.append(worst_j)
        kept.sort()
    return kept


def _round_row(r):
    return (round(r[0], _AGE_DP), round(r[1], _TEFF_DP), round(r[2], _L_DP), round(r[3], _RAD_DP))


def source_age_at_teff(rows, teff):
    """Dense-source cooling age at a target Teff (the ground truth WB re-derives)."""
    if teff >= rows[0][1] or teff <= rows[-1][1]:
        return None
    for i in range(1, len(rows)):
        if rows[i][1] <= teff:
            return _interp_age_at_teff(rows[i - 1], rows[i], teff)
    return None


def kept_age_at_teff(kept_rows, teff):
    """Cooling age at a target Teff from the SUBSAMPLED (rounded) nodes — mimics the tool."""
    if teff >= kept_rows[0][1] or teff <= kept_rows[-1][1]:
        return None
    for i in range(1, len(kept_rows)):
        if kept_rows[i][1] <= teff:
            return _interp_age_at_teff(kept_rows[i - 1], kept_rows[i], teff)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", help="write the _WD_COOLING literal here (ONLY if validation passes)")
    args = ap.parse_args()

    literal = ["_WD_COOLING = {"]
    total_nodes = 0
    max_anchor_err = 0.0
    worst_closure = 0.0
    failures = []                                                  # F1/F2 hard gates
    print("mass  src_rows dropped  nodes   anchor cooling-age (Gyr): kept vs source [%err]")
    for m in _MASSES:
        tag = f"{int(round(m * 100)):03d}"
        rows, dropped = parse_seq(os.path.join(_HERE, f"seq_{tag}_thick.txt"))
        kept = [_round_row(rows[i]) for i in adaptive_subsample(rows)]   # ROUNDED = what ships
        total_nodes += len(kept)

        # CP1-F2: the emitted (rounded) ages MUST strictly increase, else _interp_age divides by zero.
        for i in range(1, len(kept)):
            if kept[i][0] <= kept[i - 1][0]:
                failures.append(f"{m:.2f}: emitted ages not strictly increasing at node {i} "
                                f"(age {kept[i-1][0]} -> {kept[i][0]}) — raise _AGE_DP")
        # closure on the ROUNDED (shipped) values
        for age, teff, l10, rad in kept:
            worst_closure = max(worst_closure, abs(l10 - math.log10((rad ** 2) * (teff / _TSUN) ** 4)))

        # anchor accuracy: rounded-kept age vs dense-source age (F5: precise Teff labels)
        anchor_str = []
        for T in _ANCHOR_TEFFS:
            ksrc, ssrc = kept_age_at_teff(kept, T), source_age_at_teff(rows, T)
            if ksrc is None or ssrc is None:
                anchor_str.append(f"{T:.0f}K:--")
                continue
            err = abs(ksrc - ssrc) / ssrc * 100
            max_anchor_err = max(max_anchor_err, err)
            if err > _ANCHOR_GATE:
                failures.append(f"{m:.2f}@{T:.0f}K: anchor age error {err:.2f}% > {_ANCHOR_GATE}%")
            anchor_str.append(f"{T:.0f}K:{ksrc:.4f}/{ssrc:.4f}[{err:.2f}%]")
        print(f"{m:.2f}  {len(rows)+dropped:5d}  {dropped:4d}   {len(kept):4d}   " + "  ".join(anchor_str))

        literal.append(f"    # {m:.2f} M_sun DA (seq_{tag}_thick.txt), Bedard 2020 / Montreal thick-H, dense adaptive resample (CR-12).")
        literal.append(f"    {m:.2f}: [")
        for age, teff, l10, rad in kept:
            literal.append(f"        ({age:.{_AGE_DP}f}, {teff:.{_TEFF_DP}f}, {l10:.{_L_DP}f}, {rad:.{_RAD_DP}f}),")
        literal.append("    ],")
    literal.append("}")

    if worst_closure > _CLOSURE_GATE:
        failures.append(f"worst closure {worst_closure:.2e} > gate {_CLOSURE_GATE}")

    print(f"\ntotal nodes = {total_nodes} across {len(_MASSES)} masses (avg {total_nodes/len(_MASSES):.0f}/mass)")
    print(f"worst closure (rounded) = {worst_closure:.2e} (gate {_CLOSURE_GATE})")
    print(f"worst anchor age error vs source = {max_anchor_err:.3f}% (gate {_ANCHOR_GATE}%)")
    ok = not failures
    print(f"VALIDATION: {'PASS' if ok else 'FAIL'}")
    for f in failures:
        print(f"  ! {f}")

    if not ok:
        print("Not emitting (validation failed).")
        return 1
    if args.emit:
        with open(args.emit, "w") as f:
            f.write("\n".join(literal) + "\n")
        print(f"wrote literal -> {args.emit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
