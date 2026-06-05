# core/hypatia_elements.py — single source of truth for Hypatia Catalog element species.
#
# The Hypatia Catalog API exposes 104 element/species (GET /hypatia/api/v2/element/),
# including singly-ionized species (e.g. "Fe", "Fe_II", "Ba_II"). This module defines the
# full set with display names, atomic numbers, and a nucleosynthetic-family category for
# each, and derives the ordered request list used by core.databases.compute_hypatia_data.
#
# Everything that needs element names, ordering, or category grouping (core/databases.py,
# core/viz.py, gui/panels/hypatia_tab.py, gui/visualizations/plot_helpers.py, main.py)
# imports from here so there is exactly one place to edit.

# ── Canonical species list, in the API's periodic-table order ─────────────────
# This is the ground-truth set returned by GET /hypatia/api/v2/element/ (104 entries).
# A live drift test (tests/test_hypatia_element_drift.py) asserts this matches the API.
_RAW_SPECIES = [
    "Li", "Be", "Be_II", "B", "C", "N", "O", "F", "Na", "Mg", "Al", "Al_II",
    "Si", "Si_II", "P", "S", "Cl", "K", "Ca", "Ca_II", "Sc", "Sc_II", "Ti",
    "Ti_II", "V", "V_II", "Cr", "Cr_II", "Mn", "Mn_II", "Fe", "Co", "Co_II",
    "Ni", "Ni_II", "Cu", "Cu_II", "Zn", "Zn_II", "Ga_II", "Ge", "Se", "Rb",
    "Sr", "Sr_II", "Y", "Y_II", "Zr", "Zr_II", "Nb", "Nb_II", "Mo", "Mo_II",
    "Tc", "Ru", "Ru_II", "Rh", "Pd", "Ag", "Cd", "In_II", "Sn", "Sb", "Te",
    "Ba", "Ba_II", "La", "La_II", "Ce", "Ce_II", "Pr", "Pr_II", "Nd", "Nd_II",
    "Sm", "Sm_II", "Eu", "Eu_II", "Gd", "Gd_II", "Tb_II", "Dy", "Dy_II",
    "Ho_II", "Er", "Er_II", "Tm_II", "Yb_II", "Lu_II", "Hf", "Hf_II", "W",
    "W_II", "Re_II", "Os", "Os_II", "Ir", "Pt", "Au", "Hg_II", "Pb", "Pb_II",
    "Th", "Th_II",
]

# ── Per-element metadata: base symbol → (full name, atomic number) ─────────────
_ELEMENT_META = {
    "Li": ("Lithium", 3),     "Be": ("Beryllium", 4),   "B": ("Boron", 5),
    "C": ("Carbon", 6),       "N": ("Nitrogen", 7),     "O": ("Oxygen", 8),
    "F": ("Fluorine", 9),     "Na": ("Sodium", 11),     "Mg": ("Magnesium", 12),
    "Al": ("Aluminum", 13),   "Si": ("Silicon", 14),    "P": ("Phosphorus", 15),
    "S": ("Sulfur", 16),      "Cl": ("Chlorine", 17),   "K": ("Potassium", 19),
    "Ca": ("Calcium", 20),    "Sc": ("Scandium", 21),   "Ti": ("Titanium", 22),
    "V": ("Vanadium", 23),    "Cr": ("Chromium", 24),   "Mn": ("Manganese", 25),
    "Fe": ("Iron", 26),       "Co": ("Cobalt", 27),     "Ni": ("Nickel", 28),
    "Cu": ("Copper", 29),     "Zn": ("Zinc", 30),       "Ga": ("Gallium", 31),
    "Ge": ("Germanium", 32),  "Se": ("Selenium", 34),   "Rb": ("Rubidium", 37),
    "Sr": ("Strontium", 38),  "Y": ("Yttrium", 39),     "Zr": ("Zirconium", 40),
    "Nb": ("Niobium", 41),    "Mo": ("Molybdenum", 42), "Tc": ("Technetium", 43),
    "Ru": ("Ruthenium", 44),  "Rh": ("Rhodium", 45),    "Pd": ("Palladium", 46),
    "Ag": ("Silver", 47),     "Cd": ("Cadmium", 48),    "In": ("Indium", 49),
    "Sn": ("Tin", 50),        "Sb": ("Antimony", 51),   "Te": ("Tellurium", 52),
    "Ba": ("Barium", 56),     "La": ("Lanthanum", 57),  "Ce": ("Cerium", 58),
    "Pr": ("Praseodymium", 59), "Nd": ("Neodymium", 60), "Sm": ("Samarium", 62),
    "Eu": ("Europium", 63),   "Gd": ("Gadolinium", 64), "Tb": ("Terbium", 65),
    "Dy": ("Dysprosium", 66), "Ho": ("Holmium", 67),    "Er": ("Erbium", 68),
    "Tm": ("Thulium", 69),    "Yb": ("Ytterbium", 70),  "Lu": ("Lutetium", 71),
    "Hf": ("Hafnium", 72),    "W": ("Tungsten", 74),    "Re": ("Rhenium", 75),
    "Os": ("Osmium", 76),     "Ir": ("Iridium", 77),    "Pt": ("Platinum", 78),
    "Au": ("Gold", 79),       "Hg": ("Mercury", 80),    "Pb": ("Lead", 82),
    "Th": ("Thorium", 90),
}

# ── Nucleosynthetic-family categories (ordered light → heavy) ─────────────────
# (key, label, color). Color is used for the abundance bar chart and is purely cosmetic.
CATEGORIES = [
    ("light",   "Light",                  "#8c9eff"),
    ("cno",     "Volatile (CNO)",         "#26a69a"),
    ("alpha",   "Alpha",                  "#66bb6a"),
    ("oddz",    "Odd-Z",                  "#d4af37"),
    ("iron",    "Iron-peak",              "#e06c4a"),
    ("s_light", "s-process (light)",      "#ab47bc"),
    ("s_heavy", "s/r-process (heavy)",    "#7e57c2"),
    ("ree",     "r-process / rare earth", "#ec407a"),
    ("heavy",   "Heavy / actinide",       "#8d6e63"),
]

_CATEGORY_MEMBERS = {
    "light":   ["Li", "Be", "B"],
    "cno":     ["C", "N", "O", "F"],
    "alpha":   ["Mg", "Si", "S", "Ca", "Ti"],
    "oddz":    ["Na", "Al", "P", "Cl", "K", "Sc", "V", "Cu"],
    "iron":    ["Cr", "Mn", "Fe", "Co", "Ni", "Zn"],
    "s_light": ["Ga", "Ge", "Se", "Rb", "Sr", "Y", "Zr", "Nb", "Mo"],
    "s_heavy": ["Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn", "Sb", "Te",
                "Ba", "La", "Ce"],
    "ree":     ["Pr", "Nd", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm",
                "Yb", "Lu"],
    "heavy":   ["Hf", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg", "Pb", "Th"],
}

# ── Derived structures (built once at import) ─────────────────────────────────

_CATEGORY_ORDER = {key: i for i, (key, _label, _color) in enumerate(CATEGORIES)}
_CATEGORY_LABEL = {key: label for key, label, _color in CATEGORIES}
_CATEGORY_COLOR = {key: color for key, _label, color in CATEGORIES}

# base symbol → category key
_BASE_CATEGORY = {}
for _key, _members in _CATEGORY_MEMBERS.items():
    for _base in _members:
        _BASE_CATEGORY[_base] = _key


def display_symbol(api_symbol: str) -> str:
    """Convert an API species symbol to a human-readable form: 'Ba_II' -> 'Ba II'."""
    return api_symbol.replace("_II", " II").replace("_", " ")


def _base_of(api_symbol: str) -> str:
    """Strip an ionization suffix: 'Ba_II' -> 'Ba', 'Fe' -> 'Fe'."""
    return api_symbol.split("_", 1)[0]


def _build_species():
    species = []
    for sym in _RAW_SPECIES:
        base = _base_of(sym)
        if base not in _ELEMENT_META:
            raise ValueError(f"hypatia_elements: no metadata for base element {base!r} (from {sym!r})")
        if base not in _BASE_CATEGORY:
            raise ValueError(f"hypatia_elements: no category for base element {base!r} (from {sym!r})")
        name, z = _ELEMENT_META[base]
        ionized = "_II" in sym
        cat = _BASE_CATEGORY[base]
        species.append({
            "symbol":   sym,                       # API casing, e.g. "Fe", "Ba_II"
            "name":     name + (" II" if ionized else ""),
            "z":        z,
            "ionized":  ionized,
            "category": cat,
        })
    # Order: category (light->heavy), then atomic number, then neutral before ionized.
    species.sort(key=lambda s: (_CATEGORY_ORDER[s["category"]], s["z"], s["ionized"]))
    return species


HYPATIA_SPECIES = _build_species()
HYPATIA_REQUEST_SYMBOLS = [s["symbol"] for s in HYPATIA_SPECIES]
SPECIES_BY_SYMBOL = {s["symbol"].lower(): s for s in HYPATIA_SPECIES}

# Index of each species in display order (used by the parser to sort response rows).
SPECIES_ORDER = {s["symbol"].lower(): i for i, s in enumerate(HYPATIA_SPECIES)}


def category_label(key: str) -> str:
    return _CATEGORY_LABEL.get(key, key)


def category_color(key: str) -> str:
    return _CATEGORY_COLOR.get(key, "#888888")
