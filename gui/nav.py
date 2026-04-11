# gui/nav.py — Left-panel QTreeWidget navigation.

from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

# Each entry: (display label, panel class name string)
# Panel class names are resolved at click time via getattr(gui.panels, name).
# Entries whose panel class does not yet exist are silently ignored.
NAVIGATION = [
    ("Star Databases", [
        ("SIMBAD Lookup",              "SimbadPanel"),
        ("NASA Exoplanet: All Tables", "NasaExoplanetPanel"),
        ("NASA Exoplanet: Planetary Systems", "NasaExoplanetPanel"),
        ("NASA Exoplanet: HWO ExEP",   "NasaExoplanetPanel"),
        ("NASA Exoplanet: Mission Exocat", "NasaExoplanetPanel"),
        ("Habitable Worlds Catalog",   "CatalogsPanel"),
        ("Open Exoplanet Catalogue",   "CatalogsPanel"),
        ("Exoplanet EU Encyclopaedia", "CatalogsPanel"),
    ]),
    ("Star System Regions", [
        ("Auto (SIMBAD)",  "StarRegionsPanel"),
        ("Semi-Manual",    "StarRegionsPanel"),
        ("Manual",         "StarRegionsPanel"),
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
    ]),
    ("Calculators", [
        ("Velocity Converter",           "VelocityPanel"),
        ("Distance Traveled",            "DistancePanel"),
        ("Travel Time (light years)",    "TravelTimePanel"),
        ("Distance Between 2 Stars",     "DistanceStarsPanel"),
        ("Stars Within Distance of Sol", "DistanceStarsPanel"),
        ("Stars Within Distance of Star","DistanceStarsPanel"),
        ("Travel Time Between Stars (LY/HR)", "TravelTimeStarsPanel"),
        ("Travel Time Between Stars (×c)",    "TravelTimeStarsPanel"),
        ("Brachistochrone: Accel → Distance", "BrachistochronePanel"),
        ("Brachistochrone: Distance in AU",   "BrachistochronePanel"),
        ("Brachistochrone: Distance in LM",   "BrachistochronePanel"),
        ("System Travel: Planet/Moon/Asteroid","SystemTravelPanel"),
        ("System Travel: Custom Thrust",       "SystemTravelPanel"),
    ]),
    ("Planetary Equations", [
        ("Orbit Periastron & Apastron", "OrbitPeriastronPanel"),
        ("Moon Orbital Distance (24h)", "MoonDistance24Panel"),
        ("Moon Orbital Distance (Xh)",  "MoonDistanceXPanel"),
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
    ("Visualizations", [
        ("Star Map",               "StarMapPanel"),
        ("Planetary System Orbits","SystemOrbitsPanel"),
        ("Habitable Zone Diagram", "HabZoneDiagramPanel"),
    ]),
    ("Utilities", [
        ("Star Systems Database Query", "CsvUtilityPanel"),
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
