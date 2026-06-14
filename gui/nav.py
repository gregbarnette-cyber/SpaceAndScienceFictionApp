# gui/nav.py — Left-panel QTreeWidget navigation.

from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

# Each entry: (display label, panel class name string)
# Panel class names are resolved at click time via getattr(gui.panels, name).
# Entries whose panel class does not yet exist are silently ignored.
NAVIGATION = [
    ("Star Databases", [
        ("SIMBAD Lookup",              "SimbadPanel"),
        ("NASA Exoplanet: Planetary Systems", "NasaPlanetarySystemsPanel"),
        ("NASA Planetary Systems Map",        "NasaPlanetarySystemsMapPanel"),
        ("NASA Exoplanet: HWO ExEP",          "NasaHwoExepPanel"),
        ("NASA Exoplanet: Mission Exocat",    "NasaMissionExocatPanel"),
        ("Habitable Worlds Catalog",          "HwcPanel"),
    ]),
    ("Search & Filter", [
        ("Star Systems Search",        "StarSystemsSearchPanel"),
        ("HWC Planet Search",          "HwcSearchPanel"),
        ("NASA Exoplanet Quick Search","NasaExoplanetSearchPanel"),
    ]),
    ("GCNS", [
        ("GCNS Census Browser",         "GcnsCensusBrowserPanel"),
        ("GCNS Source Lookup",          "GcnsSourceLookupPanel"),
        ("Resolved System Viewer",      "GcnsSystemViewerPanel"),
        ("GCNS Distance Between 2 Stars","GcnsDistancePanel"),
        ("GCNS Travel Time",            "GcnsTravelTimePanel"),
        ("GCNS Stars Within a Star",    "GcnsStarsWithinStarPanel"),
    ]),
    ("Star System Regions", [
        ("Auto (SIMBAD)",  "StarRegionsAutoPanel"),
        ("Semi-Manual",    "StarRegionsSemiManualPanel"),
        ("Manual",         "StarRegionsManualPanel"),
    ]),
    ("Science", [
        ("Solar System Bodies",  "SolarSystemPanel"),
        ("Main Sequence Stars",  "MainSequencePanel"),
        ("Sol System Regions",   "SolRegionsPanel"),
    ]),
    ("Science Fiction", [
        ("Honorverse Hyper Limits",       "HonorverseHyperPanel"),
        ("Honorverse Acceleration Table", "HonorverseAccelPanel"),
        ("Honorverse Effective Speed",    "HonorverseSpeedPanel"),
        ("Honorverse Hyper Translation Time", "HonorverseHyperTimePanel"),
        ("Honorverse Impeller Wedge",     "HonorverseImpellerPanel"),
        ("Honorverse Missile Intercept",  "HonorverseMissilePanel"),
    ]),
    ("Calculators", [
        ("Distance Between 2 Stars",           "DistanceBetweenStarsPanel"),    # 17
        ("Stars Within Distance of Sol",       "StarsWithinDistanceSolPanel"),  # 18
        ("Stars Within Distance of a Star",    "StarsWithinDistanceStarPanel"), # 19
        ("Travel Time Between Stars (LY/HR)",  "TravelTimeStarsLyHrPanel"),     # 20
        ("Travel Time Between Stars (×c)",     "TravelTimeStarsTimesCPanel"),   # 21
        ("System Travel: Planet/Moon/Asteroid","SystemTravelSolarPanel"),       # 22
        ("System Travel: Custom Thrust",       "SystemTravelThrustPanel"),      # 23
        ("Brachistochrone: Accel → Distance",  "BrachistochroneAccelPanel"),    # 24
        ("Distance Traveled at LY/HR",         "DistanceLyHrPanel"),            # 25
        ("Distance Traveled at ×c",            "DistanceTimesCPanel"),          # 26
        ("Travel Time at LY/HR",               "TravelTimeLyHrPanel"),          # 27
        ("Travel Time at ×c",                  "TravelTimeTimesCPanel"),        # 28
        ("Brachistochrone: Distance in AU",    "BrachistochroneAuPanel"),       # 29
        ("Brachistochrone: Distance in LM",    "BrachistochroneLmPanel"),       # 30
        ("Velocity: LY/HR → ×c",              "VelocityLyHrPanel"),            # 31
        ("Velocity: ×c → LY/HR",              "VelocityTimesCPanel"),          # 32
    ]),
    ("Route Planning", [
        ("Multi-Stop Journey",        "MultiStopJourneyPanel"),
        ("Optimal Tour",              "OptimalTourPanel"),
        ("Nearest-Neighbor Chain",    "NearestNeighborPanel"),
        ("Farthest-First Coverage",   "FarthestFirstPanel"),
        ("Jump-Range Pathfinding",    "JumpRoutePanel"),
        ("Jump Network / Reachability", "JumpNetworkPanel"),
        ("Trade-Route Network",       "TradeRoutePlannerPanel"),
    ]),
    ("Planetary Equations", [
        ("Orbit Periastron & Apastron", "OrbitPeriastronPanel"),
        ("Moon Orbital Distance (24h)", "MoonDistance24Panel"),
        ("Moon Orbital Distance (Xh)",  "MoonDistanceXPanel"),
    ]),
    ("Worldbuilding", [
        ("Roche Limit",              "RocheLimitPanel"),
        ("Tidal Locking Timescale",  "TidalLockingPanel"),
        ("Hill Sphere",              "HillSpherePanel"),
        ("Binary Orbit Stability",   "BinaryOrbitPanel"),
        ("Atmosphere Retention",     "AtmosphereRetentionPanel"),
    ]),
    ("Rotating Habitat", [
        ("Gravity Acceleration",   "GravityAccelPanel"),
        ("Distance from Center",   "GravityDistancePanel"),
        ("Rotation Rate (rpm)",    "GravityRpmPanel"),
    ]),
    ("Misc. Equations", [
        ("Habitable Zone Calculator",       "HabZonePanel"),
        ("Habitable Zone Calculator w/SMA", "HabZoneSmaPanel"),
        ("Star Luminosity",                 "LuminosityPanel"),
    ]),
    ("Utilities", [
        ("Star Systems Database Query",    "CsvUtilityPanel"),
        ("Export Star Systems to CSV",     "ExportStarSystemsPanel"),
        ("Import HWC Data",                "ImportHwcPanel"),
        ("Import Mission Exocat Data",     "ImportMissionExocatPanel"),
        ("Import Main Sequence Star Props","ImportMainSequencePanel"),
        ("Import Solar System Data",       "ImportSolarSystemPanel"),
        ("Import Honorverse Hyper Limits", "ImportHonorversePanel"),
        ("Import GCNS Data",               "ImportGcnsPanel"),
        ("Database Table Status",          "DbStatusPanel"),
    ]),
]


def populate_nav(tree: QTreeWidget, window) -> None:
    """Build the navigation tree and wire item clicks to window.show_panel()."""
    tree.itemClicked.connect(lambda item, _col: _on_item_clicked(item, window))

    for category, entries in NAVIGATION:
        cat_item = QTreeWidgetItem([category])
        # Make category rows non-selectable so only leaf items trigger panel switches.
        from PySide6.QtCore import Qt
        cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        tree.addTopLevelItem(cat_item)
        for label, panel_name in entries:
            child = QTreeWidgetItem([label])
            child.setData(0, 256, panel_name)   # Qt.UserRole = 256
            cat_item.addChild(child)

    tree.expandAll()


def _on_item_clicked(item: QTreeWidgetItem, window) -> None:
    panel_name = item.data(0, 256)
    if not panel_name:
        return
    import gui.panels as panels_pkg
    panel_class = getattr(panels_pkg, panel_name, None)
    if panel_class is not None:
        window.show_panel(panel_class)
