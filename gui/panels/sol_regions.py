# gui/panels/sol_regions.py — Option 14: Sol Solar System Regions.

from PySide6.QtWidgets import QTabWidget, QWidget, QVBoxLayout

from gui.panels.base import ResultPanel
import core.regions
import core.equations


def _au_lm4(val: float) -> str:
    return f"{val:.4f} ({val * 8.3167:.3f} LM)"


def _au_lm3(val: float) -> str:
    return f"{val:.3f} ({val * 8.3167:.3f} LM)"


class SolRegionsPanel(ResultPanel):
    """Displays the Sol Solar System Regions output (option 14).

    Seven tab sections matching the CLI output:
        1. Star System Properties
        2. Stellar Properties
        3. Star Distance
        4. Earth Equivalent Orbit
        5. Solar System Regions
        6. Alternate HZ Regions
        7. Calculated Habitable Zone
    """

    def build_inputs(self):
        self._input_count = 0

    def build_results_area(self):
        d = core.regions.compute_sol_regions()

        tabs = QTabWidget()
        self._layout.addWidget(tabs)

        # ── Tab 1: Star System Properties ─────────────────────────────────────
        headers = ["Property", "Value"]
        rows = [
            ["Apparent Magnitude",          f"{d['vmag']:.3f}"],
            ["Absolute Magnitude",          f"{d['absMagnitude']:.3f}"],
            ["Bolometric Absolute Magnitude", f"{d['bcAbsMagnitude']:.3f}"],
            ["Bolometric Luminosity",        f"{d['bcLuminosity']:.6f}"],
            ["Luminosity from Mass",         f"{d['luminosityFromMass']:.5f}"],
            ["BC",                           f"{d['boloLum']:.1f}"],
            ["Star Temperature K",           f"{int(d['temp'])}"],
        ]
        view = self.make_table(headers, rows)
        view.setSortingEnabled(False)
        tabs.addTab(view, "Star System Properties")

        # ── Tab 2: Stellar Properties ─────────────────────────────────────────
        headers = ["Stellar Mass", "Stellar Radius", "Stellar Diameter (Sol)",
                   "Stellar Diameter (KM)", "Main Sequence Life Span"]
        rows = [[
            f"{d['stellarMass']:.4f}",
            f"{d['stellarRadius']:.5f}",
            f"{d['stellarDiameterSol']:.4f}",
            f"{d['stellarDiameterKM']:.5e}",
            f"{d['mainSeqLifeSpan']:.5e}",
        ]]
        tabs.addTab(self.make_table(headers, rows), "Stellar Properties")

        # ── Tab 3: Star Distance ──────────────────────────────────────────────
        headers = ["Parallax", "Trig Parallax", "Parsecs", "Light Years"]
        rows = [[
            f"{d['plx']:.2f}",
            f"{d['trigParallax']:.4f}",
            f"{d['parsecs']:.4f}",
            f"{d['lightYears']:.4f}",
        ]]
        tabs.addTab(self.make_table(headers, rows), "Star Distance")

        # ── Tab 4: Earth Equivalent Orbit ─────────────────────────────────────
        headers = ["Distance (AU)", "Distance (KM)", "Year",
                   "Temp (K)", "Temp (C)", "Temp (F)", "Size of Sun"]
        rows = [[
            f"{d['distAU']:.4f}",
            f"{d['distKM']:.5e}",
            f"{d['planetaryYear']:.4f}",
            f"{d['planetaryTemperature']:.2f}",
            f"{d['planetaryTemperatureC']:.2f}",
            f"{d['planetaryTemperatureF']:.2f}",
            d["sizeOfSun"],
        ]]
        tabs.addTab(self.make_table(headers, rows), "Earth Equiv. Orbit")

        # ── Tab 5: Solar System Regions ───────────────────────────────────────
        headers = ["Region", "AU"]
        rows = [
            ["System Inner Limit (Gravity)",              _au_lm4(d["sysilGrav"])],
            ["System Inner Limit (Sunlight)",             _au_lm4(d["sysilSunlight"])],
            ["Circumstellar HZ Inner Limit",              _au_lm4(d["hzil"])],
            ["Circumstellar HZ Outer Limit",              _au_lm4(d["hzol"])],
            ["Snow Line",                                 _au_lm4(d["snowLine"])],
            ["Liquid Hydrogen (LH2) Line",                _au_lm4(d["lh2Line"])],
            ["System Outer Limit",                        _au_lm4(d["sysol"])],
        ]
        view = self.make_table(headers, rows)
        view.setSortingEnabled(False)
        tabs.addTab(view, "System Regions")

        # ── Tab 6: Alternate HZ Regions ───────────────────────────────────────
        headers = ["Region", "AU"]
        rows = [
            ["Fluorosilicone-Fluorosilicone Inner Limit", _au_lm4(d["ffInner"])],
            ["Fluorocarbon-Sulfur Inner Limit",           _au_lm4(d["fsInner"])],
            ["Fluorosilicone-Fluorosilicone Outer Limit", _au_lm4(d["ffOuter"])],
            ["Fluorocarbon-Sulfur Outer Limit",           _au_lm4(d["fsOuter"])],
            ["Protein-Water Inner Limit",                 _au_lm4(d["prwInner"])],
            ["Protein-Water Outer Limit",                 _au_lm4(d["prwOuter"])],
            ["Protein-Ammonia Inner Limit",               _au_lm4(d["praInner"])],
            ["Protein-Ammonia Outer Limit",               _au_lm4(d["praOuter"])],
            ["Polylipid-Methane Inner Limit",             _au_lm4(d["pmInner"])],
            ["Polylipid-Methane Outer Limit",             _au_lm4(d["pmOuter"])],
            ["Polylipid-Hydrogen Inner Limit",            _au_lm4(d["phInner"])],
            ["Polylipid-Hydrogen Outer Limit",            _au_lm4(d["phOuter"])],
        ]
        view = self.make_table(headers, rows)
        view.setSortingEnabled(False)
        tabs.addTab(view, "Alternate HZ Regions")

        # ── Tab 7: Calculated Habitable Zone (3-luminosity columns) ───────────
        # Reuses compute_habitable_zone for Kopparapu zones; shows three
        # luminosity columns matching the CLI: Bolometric, from Mass, Calculated.
        from core.equations import compute_habitable_zone
        import math

        def _hz_row(zone_name, bc_lum, mass_lum, calc_lum, teff):
            from core.equations import _kopparapu_seff
            # determine zone key from name
            key_map = {
                "Recent Venus": "rv",
                "5 Earth Mass": "rg5",
                "Runaway Greenhouse - 0.1": "rg01",
                "Runaway Greenhouse)": "rg",
                "Maximum Greenhouse": "mg",
                "Early Mars": "em",
            }
            key = next((v for k, v in key_map.items() if k in zone_name), None)
            if key is None:
                return [zone_name, "?", "?", "?"]
            seff = _kopparapu_seff(teff, key)
            def fmt(lum):
                au = math.sqrt(lum / seff)
                return _au_lm3(au)
            return [zone_name, fmt(bc_lum), fmt(mass_lum), fmt(calc_lum)]

        zone_names = [
            "Optimistic Inner HZ (Recent Venus)",
            "Conservative Inner HZ (Runaway Greenhouse - 5 Earth Mass)",
            "Conservative Inner HZ (Runaway Greenhouse)",
            "Conservative Inner HZ (Runaway Greenhouse - 0.1 Earth Mass)",
            "Conservative Outer HZ (Maximum Greenhouse)",
            "Optimistic Outer HZ (Early Mars)",
        ]
        hz_headers = [
            "Zone",
            "Bolometric Luminosity (AU)",
            "Luminosity from Mass (AU)",
            "Calculated Luminosity (AU)",
        ]
        hz_rows = [
            _hz_row(
                name,
                d["bcLuminosity"],
                d["luminosityFromMass"],
                d["calculatedLuminosity"],
                d["temp"],
            )
            for name in zone_names
        ]
        hz_view = self.make_table(hz_headers, hz_rows)
        hz_view.setSortingEnabled(False)
        tabs.addTab(hz_view, "Calculated HZ")
