# gui/panels/__init__.py
# Panel classes are imported here so that gui/nav.py can resolve them by name
# via getattr(pkg, panel_name).

# ── Phase B panels ────────────────────────────────────────────────────────────
from gui.panels.science_tables      import SolarSystemPanel, MainSequencePanel
from gui.panels.sol_regions         import SolRegionsPanel
from gui.panels.honorverse          import HonorverseHyperPanel, HonorverseAccelPanel, HonorverseSpeedPanel
from gui.panels.velocity            import VelocityLyHrPanel, VelocityTimesCPanel
from gui.panels.distance            import DistanceLyHrPanel, DistanceTimesCPanel
from gui.panels.travel_time         import TravelTimeLyHrPanel, TravelTimeTimesCPanel
from gui.panels.orbit_calc          import OrbitPeriastronPanel, MoonDistance24Panel, MoonDistanceXPanel
from gui.panels.rotating_habitat    import GravityAccelPanel, GravityDistancePanel, GravityRpmPanel
from gui.panels.habitable_zone_calc import HabZonePanel, HabZoneSmaPanel
from gui.panels.luminosity          import LuminosityPanel

# ── Phase C panels ────────────────────────────────────────────────────────────
from gui.panels.simbad         import SimbadPanel
from gui.panels.star_regions   import (StarRegionsAutoPanel,
                                       StarRegionsSemiManualPanel,
                                       StarRegionsManualPanel)
from gui.panels.distance_stars import (DistanceBetweenStarsPanel,
                                       StarsWithinDistanceSolPanel,
                                       StarsWithinDistanceStarPanel)

# ── Phase D panels ────────────────────────────────────────────────────────────
from gui.panels.nasa_exoplanet   import (NasaPlanetarySystemsPanel,
                                         NasaHwoExepPanel, NasaMissionExocatPanel)
from gui.panels.catalogs         import HwcPanel
from gui.panels.travel_time_stars import (TravelTimeStarsLyHrPanel,
                                          TravelTimeStarsTimesCPanel)
from gui.panels.brachistochrone  import (BrachistochroneAccelPanel,
                                         BrachistochroneAuPanel,
                                         BrachistochroneLmPanel)
from gui.panels.system_travel    import SystemTravelSolarPanel, SystemTravelThrustPanel
from gui.panels.csv_utility      import (CsvUtilityPanel, ExportStarSystemsPanel,
                                         ImportHwcPanel, ImportMissionExocatPanel,
                                         ImportMainSequencePanel, ImportSolarSystemPanel,
                                         ImportHonorversePanel)

# ── Phase E panels (lazy-loaded to break circular import) ─────────────────────
# gui/visualizations/*.py imports gui.panels.base, so direct imports here would
# create a circular dependency.  __getattr__ defers the import until first use,
# at which point gui.panels is already fully initialised.

_VIZ_PANEL_MODULES = {
    "StarMapPanel":        "gui.visualizations.star_map",
    "SystemOrbitsPanel":   "gui.visualizations.system_orbits",
    "HabZoneDiagramPanel": "gui.visualizations.hz_diagram",
}


def __getattr__(name: str):
    if name in _VIZ_PANEL_MODULES:
        import importlib
        mod = importlib.import_module(_VIZ_PANEL_MODULES[name])
        cls = getattr(mod, name)
        globals()[name] = cls   # cache so future accesses bypass __getattr__
        return cls
    raise AttributeError(f"module 'gui.panels' has no attribute {name!r}")
