# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the CLI app
python main.py

# Run the GUI app
python gui_main.py
```

## Architecture

The project has two entry points that share all computation through the `core/` package:

- **`main.py`** — CLI. All features are top-level functions registered in `MENU_OPTIONS`.
- **`gui_main.py`** — PySide6 GUI. Navigation tree on the left, panel stack on the right.
- **`core/`** — Pure computation layer (no I/O, no Qt). Called by both CLI and GUI.
- **`gui/`** — Qt presentation layer: `app.py` (MainWindow), `nav.py` (navigation tree), `panels/` (one class per feature).

See `@docs/gui-architecture.md` for the full GUI structure, panel class → option mapping, and phase completion status.

### CLI Architecture

`main.py` is the single entry point for the CLI. All features live as functions in this file (for now) and are registered in the `MENU_OPTIONS` dict at the bottom, which drives the main menu loop.

```
MENU_OPTIONS = {
    "1": ("SIMBAD Lookup Query", query_star),
    # add new features here
}
```

The main menu loop calls whichever function the user picks, then returns to the menu after the function ends. Every feature function must call `input("\nPress Enter to Return to the Main Menu")` before returning.

## Adding New Features

1. Write the feature as a top-level function.
2. Register it in `MENU_OPTIONS` with the next available key and a short label.
3. End the function with the "Press Enter to Return to the Main Menu" prompt.
4. Screen clearing rules:
   - If the function has **no user inputs** (pure data display): call `os.system("cls" if os.name == "nt" else "clear")` at the very start of the function, before any output.
   - If the function **collects user inputs first**: call `os.system("cls" if os.name == "nt" else "clear")` after all inputs are collected and before the first output `print()`.
   - The main menu loop clears the screen at the top of each iteration, so functions do **not** need to clear after the "Press Enter" prompt.

## Menu Options

```
  Star Databases                                    Calculators
  --------------                                    -----------
1. SIMBAD Lookup Query                              17. Distance Between 2 Stars
2. NASA Exoplanet Archive: All Tables               18. Stars within a Certain Distance of Sol
3. NASA Exoplanet Archive: Planetary Systems        19. Stars within a Certain Distance of a Star
4. NASA Exoplanet Archive: HWO ExEP Stars           20. Travel Time Between 2 Stars (LYs/HR)
5. NASA Exoplanet Archive: Mission Exocat Stars     21. Travel Time Between 2 Stars (X Times the Speed of Light)
6. Habitable Worlds Catalog                         22. Travel Time Between 2 System Objs (Planet/Moon/Asteroid)
7. Open Exoplanet Catalogue                         23. Travel Time Between 2 System Objs (Custom Thrust Duration)
                                                    24. Distance Traveled at an Acceleration Within a Certain Time
  Star System Regions                               25. Distance Traveled at a certain ly/hr within a certain time
  ------------------                                26. Distance Traveled at a certain X times the speed of light
8.  Star System Regions (SIMBAD)                    27. Time to Travel # of Light Years at X LY/HR
9.  Star System Regions (Semi-SIMBAD)               28. Time to Travel # of Light Years at X Times the Speed of Light
10. Star System Regions (Manual)                    29. Travel Time Between 2 System Objs (Generic, Distance in AUs)
                                                    30. Travel Time Between 2 System Objs (Generic, Distance in LMs)
  Science                                           31. Light Years per Hour to X Times the Speed of Light
  -------                                           32. X Times the Speed of Light to Light Years per Hour
11. Solar System Planet/Dwarf Planets/Asteroids
12. Main Sequence Star Properties                   Planetary Equations
13. Sol Solar System Regions                        -------------------
                                                    33. Planetary Orbit Periastron & Apastron Distance Calculator
  Science Fiction                                   34. Orbital Distance of an Earth-sized Moon with a 24 hour day
  ---------------                                   35. Orbital Distance of an Earth-sized Moon with a X hour day
14. Honorverse Hyper Limits by Spectral Class
15. Honorverse Acceleration by Mass Table           Rotating Habitat Equations
16. Honorverse Effective Speed by Hyper Band        --------------------------
                                                    36. Centrifugal Artificial Gravity Acceleration at Point X (m/s^2)
  Utilities                                         37. Distance from Point X to the Center of Rotation (m)
  ---------                                         38. Rotation Rate at Point X (rpm)
50. Star Systems CSV Query
Q.  Quit                                            Misc. Equations
                                                    ---------------
                                                    39. Habitable Zone Calculator
                                                    40. Habitable Zone Calculator w/SMA
                                                    41. Star Luminosity
```

@docs/star-databases.md
@docs/star-system-regions.md
@docs/science-and-scifi.md
@docs/calculators.md
@docs/equations.md
@docs/gui-architecture.md
