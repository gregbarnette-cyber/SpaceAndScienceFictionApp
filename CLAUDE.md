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
1. SIMBAD Lookup Query                              18. Distance Between 2 Stars
2. NASA Exoplanet Archive: All Tables               19. Stars within a Certain Distance of Sol
3. NASA Exoplanet Archive: Planetary Systems        20. Stars within a Certain Distance of a Star
4. NASA Exoplanet Archive: HWO ExEP Stars           21. Light Years per Hour to X Times the Speed of Light
5. NASA Exoplanet Archive: Mission Exocat Stars     22. X Times the Speed of Light to Light Years per Hour
6. Habitable Worlds Catalog                         23. Distance Traveled at a certain ly/hr within a certain time
7. Open Exoplanet Catalogue                         24. Distance Traveled at a certain X times the speed of light
8. Exoplanet EU Encyclopaedia                       25. Time to Travel # of Light Years at X LY/HR
                                                    26. Time to Travel # of Light Years at X Times the Speed of Light
  Star System Regions                               27. Travel Time Between 2 Stars (LYs/HR)
  ------------------                                28. Travel Time Between 2 Stars (X Times the Speed of Light)
9.  Star System Regions (SIMBAD)                    29. Distance Traveled at an Acceleration Within a Certain Time
10. Star System Regions (Semi-SIMBAD)               30. Travel Time Between 2 System Objs (Generic, Distance in AUs)
11. Star System Regions (Manual)                    31. Travel Time Between 2 System Objs (Generic, Distance in LMs)
                                                    32. Travel Time Between 2 System Objs (Planet/Moon/Asteroid)
  Science                                           33. Travel Time Between 2 System Objs (Custom Thrust Duration)
  -------
12. Solar System Planet/Dwarf Planets/Asteroids     Planetary Equations
13. Main Sequence Star Properties                   -------------------
14. Sol Solar System Regions                        34. Planetary Orbit Periastron & Apastron Distance Calculator
                                                    35. Orbital Distance of an Earth-sized Moon with a 24 hour day
  Science Fiction                                   36. Orbital Distance of an Earth-sized Moon with a X hour day
  ---------------
15. Honorverse Hyper Limits by Spectral Class       Rotating Habitat Equations
16. Honorverse Acceleration by Mass Table           --------------------------
17. Honorverse Effective Speed by Hyper Band        37. Centrifugal Artificial Gravity Acceleration at Point X (m/s^2)
                                                    38. Distance from Point X to the Center of Rotation (m)
  Utilities                                         39. Rotation Rate at Point X (rpm)
  ---------
50. Star Systems CSV Query                          Misc. Equations
Q.  Quit                                            ---------------
                                                    40. Habitable Zone Calculator
                                                    41. Habitable Zone Calculator w/SMA
                                                    42. Star Luminosity
```

@docs/star-databases.md
@docs/star-system-regions.md
@docs/science-and-scifi.md
@docs/calculators.md
@docs/equations.md
