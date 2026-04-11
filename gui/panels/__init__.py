# gui/panels/__init__.py
# Panel classes are imported here so that gui/nav.py can resolve them by name
# via getattr(pkg, panel_name).

# ── Phase B panels ────────────────────────────────────────────────────────────
from gui.panels.science_tables      import SolarSystemPanel, MainSequencePanel
from gui.panels.sol_regions         import SolRegionsPanel
from gui.panels.honorverse          import HonorverseHyperPanel, HonorverseAccelPanel, HonorverseSpeedPanel
from gui.panels.velocity            import VelocityPanel
from gui.panels.distance            import DistancePanel
from gui.panels.travel_time         import TravelTimePanel
from gui.panels.orbit_calc          import OrbitPeriastronPanel, MoonDistance24Panel, MoonDistanceXPanel
from gui.panels.rotating_habitat    import GravityAccelPanel, GravityDistancePanel, GravityRpmPanel
from gui.panels.habitable_zone_calc import HabZonePanel, HabZoneSmaPanel
from gui.panels.luminosity          import LuminosityPanel

# ── Phase C will add ──────────────────────────────────────────────────────────
#   from gui.panels.simbad         import SimbadPanel
#   from gui.panels.star_regions   import StarRegionsPanel
#   from gui.panels.distance_stars import DistanceStarsPanel

# ── Phase D will add remaining panels.
# ── Phase E will add visualization panels.
