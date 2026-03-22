# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
```

## Architecture

`main.py` is the single entry point. All features live as functions in this file (for now) and are registered in the `MENU_OPTIONS` dict at the bottom, which drives the main menu loop.

```
MENU_OPTIONS = {
    "1": ("Query Star Information (SIMBAD)", query_star),
    # add new features here
}
```

The main menu loop calls whichever function the user picks, then returns to the menu after the function ends. Every feature function must call `input("\nPress Enter to Return to the Main Menu")` before returning.

## Adding New Features

1. Write the feature as a top-level function.
2. Register it in `MENU_OPTIONS` with the next available key and a short label.
3. End the function with the "Press Enter to Return to the Main Menu" prompt.

## SIMBAD Query Feature

- Uses `astroquery.simbad.Simbad` with votable fields: `sptype`, `plx`, `flux(V)`, `fe_h` (temperature in `Fe_H_Teff` column). Field names are specific to astroquery 0.4.x.
- `query_star()` → `_parse_designations()` → `_display_results()`.
- Parallax (mas) from `PLX_VALUE`; distance in parsecs = 1000 / plx; light years = parsecs × 3.26156; all rounded to 4 decimal places.
- Designations are pulled from `Simbad.query_objectids()` and matched by prefix in `_parse_designations()`.
- Missing/masked SIMBAD fields are handled by `_safe_get()` and shown as `N/A`.
