# Hypatia Catalog — Data Overview

**Source:** https://www.hypatiacatalog.com/  
**API Docs:** https://www.hypatiacatalog.com/api  
**Reference:** Hinkel et al. (2014), AJ 148, 54

## What it is

A multidimensional stellar abundance database covering:
- **FGKM-type stars** within 500 parsecs of the Sun
- **All exoplanet host stars** regardless of distance
- Each star has at minimum [Fe/H] + at least one other elemental abundance

No API key required — free, open access.

---

## API Base URL

```
https://hypatiacatalog.com/hypatia/api/v2/
```

## Endpoints

| Endpoint | What it returns |
|---|---|
| `GET /solarnorm` | Available solar normalizations (Lodders 2009, Asplund 2009, absolute, etc.) |
| `GET /element` | Full list of measurable elements and ionized species (Li, Be, C, N, O, Fe, Co, Ca, Si, etc.) |
| `GET /catalog` | All literature catalogs that contributed abundance data (~hundreds of papers) |
| `GET /star` | Full stellar properties + planet data for any SIMBAD-recognized star name |
| `GET /composition` | Element abundance values for a specific star+element+solar norm — returns mean, median, min, max, std, and per-catalog values |
| `GET /data` | Scatter plot or histogram data across the full catalog, with filtering |

---

## Stellar Properties Available (per star)

- **Identifiers:** HIP, HD, BD, 2MASS, Gaia DR2, TYC, other aliases
- **Position:** RA, Dec, X/Y/Z (pc), distance (pc)
- **Kinematics:** U/V/W velocities, proper motion (RA and Dec)
- **Photometry:** V mag, B mag, B-V color
- **Physics:** T_eff, log g, spectral type
- **Galactic disk membership:** thin/thick disk

## Planetary Properties (where applicable)

- Period (P) with asymmetric errors
- Orbital semi-major axis (a) with asymmetric errors
- Eccentricity (e) with asymmetric errors
- Planet mass (M_p) with asymmetric errors
- Cross-matched with NASA Exoplanet Archive (NEA) names

## Elemental Abundances (per star, per element)

- Mean, median, min, max, ±error, std deviation across all catalog measurements
- Per-catalog breakdown — each value traceable to its source paper
- Re-normalizable to any solar standard (Lodders et al. 2009 is default)
- Available elements include: Li, Be, C, N, O, Na, Mg, Al, Si, S, Ca, Sc, Ti, V, Cr, Mn, Fe, Co, Ni, Cu, Zn, Sr, Y, Zr, Ba, La, Ce, Nd, Eu, and more (including ionized species)

---

## Python Examples

### Get stellar properties + planets for a star
```python
import requests

params = {"name": ["HIP 113044"]}
r = requests.get("https://hypatiacatalog.com/hypatia/api/v2/star", params=params)
print(r.json())
```

### Get element abundances for a star
```python
import requests

# Fe and Ca for HIP 32970, normalized to Asplund 2009
params = {
    "name": ["HIP 32970", "HIP 32970"],
    "element": ["fe", "ca"],
    "solarnorm": ["asplund09", "asplund09"]
}
r = requests.get("https://hypatiacatalog.com/hypatia/api/v2/composition", params=params)
print(r.json())
```

### Get scatter plot data across full catalog
```python
import requests

# [Fe/H] vs [Si/H] for all stars
r = requests.get("https://hypatiacatalog.com/hypatia/api/v2/data/",
                 params={"xaxis1": "Fe", "yaxis1": "Si"})
print(r.json())
```

### List all available solar normalizations
```python
import requests

r = requests.get("https://hypatiacatalog.com/hypatia/api/v2/solarnorm")
print(r.json())
```

---

## Notes

- Star names are matched case-insensitively with spaces removed; any SIMBAD name works
- Default solar normalization is **Lodders et al. (2009)** when `solarnorm` is omitted
- The `/data` endpoint supports filters on stellar properties, planet properties, or element ratios
- Cross-referenced with NASA Exoplanet Archive for exoplanet host identification
