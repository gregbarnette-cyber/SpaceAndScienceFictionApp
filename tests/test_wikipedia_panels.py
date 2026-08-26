"""Headless GUI tests for the Wikipedia tab (WikipediaView + open_or_focus_wiki_tab).

Offline: core.wikipedia.resolve_and_fetch / fetch_thumbnail are monkeypatched. Includes the
main-thread-delivery guard (completed_plans/WIKIPEDIA_TABS_PLAN.md §10 finding #9) — a real worker thread runs
the fetch, and delivery of the result must land back on the main thread.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QTabWidget
    from PySide6.QtCore import QThread
    _GUI_OK = True
except Exception:
    _GUI_OK = False

if _GUI_OK:
    import core.wikipedia as wiki
    import gui.panels.wikipedia_tab as wtab
    from gui.panels.wikipedia_tab import WikipediaView, open_or_focus_wiki_tab


def _found(title="Tau Ceti", thumb=None):
    return {
        "found": True, "title": title, "description": "star in the constellation Cetus",
        "extract_html": "<p>A single G-type star near the Sun.</p>",
        "summary_text": "A single G-type star near the Sun.",
        "url": "https://en.wikipedia.org/wiki/" + title.replace(" ", "_"),
        "thumbnail_url": thumb, "matched_on": "HD 10700", "query": title,
    }


@unittest.skipUnless(_GUI_OK, "PySide6 not available")
class WikipediaViewRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_found_renders_title_and_link(self):
        view = WikipediaView()
        view._on_article(_found())            # direct call — no thread, no network
        html = view._browser.toHtml()
        self.assertIn("Tau Ceti", html)
        self.assertIn("Read the full article", html)
        self.assertIn("G-type star", html)

    def test_not_found_state(self):
        view = WikipediaView()
        view._star_label = "Nowhere"
        view._on_article({"found": False, "tried": ["Nowhere", "HD 999999"]})
        text = view._browser.toPlainText()
        self.assertIn("No Wikipedia article", text)
        self.assertIn("Nowhere", text)

    def test_error_state(self):
        view = WikipediaView()
        view._on_article({"error": "Wikipedia request timed out. Try again."})
        text = view._browser.toPlainText()
        self.assertIn("timed out", text)

    def test_loading_state(self):
        view = WikipediaView()
        view._star_label = "Vega"
        self.assertIn("Loading", view._html_loading())
        self.assertIn("Vega", view._html_loading())

    def test_open_or_focus_adds_then_focuses(self):
        tabs = QTabWidget()
        with mock.patch.object(wiki, "resolve_and_fetch",
                               return_value={"found": False, "tried": []}):
            open_or_focus_wiki_tab(tabs, "Tau Ceti", name="Tau Ceti")
            self.assertEqual(tabs.count(), 1)
            self.assertEqual(tabs.tabText(0), "📖 Tau Ceti — Wikipedia")
            # Re-opening the same star focuses, does not add a second tab.
            open_or_focus_wiki_tab(tabs, "Tau Ceti", name="Tau Ceti")
            self.assertEqual(tabs.count(), 1)
        self.app.processEvents()


@unittest.skipUnless(_GUI_OK, "PySide6 not available")
class WikipediaViewThreadAffinityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_result_delivered_on_main_thread(self):
        """resolve_and_fetch runs on a worker thread; _on_article must fire on the main thread."""
        main_thread = self.app.thread()
        view = WikipediaView()
        captured = {}

        def spy(res):
            captured["thread"] = QThread.currentThread()

        view._on_article = spy   # set BEFORE load_for so it is the stashed callback

        # thumbnail_url=None so no second (network) fetch is triggered.
        with mock.patch.object(wiki, "resolve_and_fetch", return_value=_found(thumb=None)):
            view.load_for(name="Tau Ceti", star_label="Tau Ceti")
            for _ in range(400):
                if "thread" in captured:
                    break
                self.app.processEvents()
                QThread.msleep(3)

        self.assertIn("thread", captured, "result was never delivered")
        self.assertIs(captured["thread"], main_thread,
                      "background result delivered off the main thread")


_CANNED_SIMBAD = {
    "main_id": "Tau Ceti",
    "designations": {"MAIN_ID": "Tau Ceti", "NAME": "NAME Tau Ceti", "HD": "HD 10700"},
    "desig_str": "Tau Ceti, HD 10700", "sp_type": "G8V", "plx_value": 274.0,
    "parsecs": 3.65, "ly": 11.9, "teff": 5344.0, "vmag": 3.5, "ra": 26.0, "dec": -15.9,
}


@unittest.skipUnless(_GUI_OK, "PySide6 not available")
class PanelWiringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from gui.app import MainWindow
        cls.window = MainWindow()
        cls.window.resize(1400, 950)

    def _panel(self, cls_):
        self.window.show_panel(cls_)
        return self.window._panels[cls_]

    def _tab_titles(self, tabs):
        return [tabs.tabText(i) for i in range(tabs.count())]

    def test_simbad_button_enables_and_opens_tab(self):
        from gui.panels.simbad import SimbadPanel
        panel = self._panel(SimbadPanel)
        panel.render(dict(_CANNED_SIMBAD))
        self.app.processEvents()
        self.assertTrue(panel._wiki_btn.isEnabled())
        tabs = panel._wiki_ctx["tabs"]
        with mock.patch.object(wiki, "resolve_and_fetch",
                               return_value={"found": False, "tried": []}):
            panel._open_wikipedia()
            self.assertTrue(any("📖" in t and "Wikipedia" in t for t in self._tab_titles(tabs)))
            # A second open focuses, does not duplicate.
            n = tabs.count()
            panel._open_wikipedia()
            self.assertEqual(tabs.count(), n)
        self.app.processEvents()

    def test_simbad_error_disables_button(self):
        from gui.panels.simbad import SimbadPanel
        panel = self._panel(SimbadPanel)
        panel.render(dict(_CANNED_SIMBAD))
        self.assertTrue(panel._wiki_btn.isEnabled())
        panel.render({"error": "No results found"})
        self.assertFalse(panel._wiki_btn.isEnabled())

    def test_opt18_row_click_opens_wiki_and_charts_still_build(self):
        from gui.panels.distance_stars import StarsWithinDistanceSolPanel
        panel = self._panel(StarsWithinDistanceSolPanel)
        result = {"count": 2, "limit_ly": 15.0, "stars": [
            {"Star Name": "Tau Ceti", "Star Designations": "HD 10700",
             "Spectral Type": "G8V", "Light Years": 11.9, "x": 1.0, "y": 2.0, "z": 3.0},
            {"Star Name": "Vega", "Star Designations": "HD 172167",
             "Spectral Type": "A0V", "Light Years": 12.5, "x": 4.0, "y": 5.0, "z": 6.0},
        ]}
        panel._render(result)
        self.app.processEvents()
        # Restructure: a permanent "Results" tab holds the table.
        self.assertEqual(panel._results_tabs.tabText(0), "Results")
        # Regression guard: Show Diagrams still built the chart tabs.
        self.assertGreater(panel._viz_tabs_widget.count(), 0)
        # Row selection enables the button; clicking opens a closable Wikipedia tab.
        self.assertFalse(panel._wiki_btn.isEnabled())
        panel._results_table.selectRow(0)
        self.app.processEvents()
        self.assertTrue(panel._wiki_btn.isEnabled())
        with mock.patch.object(wiki, "resolve_and_fetch",
                               return_value={"found": False, "tried": []}):
            panel._wiki_btn.click()
            self.assertEqual(panel._results_tabs.count(), 2)
            self.assertIn("📖", panel._results_tabs.tabText(1))
        self.app.processEvents()

    def test_opt18_single_cell_selection_enables_wiki_button(self):
        # Review-fix #1: base.make_table defaults to SelectItems, under which selecting a single cell
        # leaves selectedRows() empty and the button never enables on a real click.
        # _wire_results_wiki_selection sets SelectRows, so selecting any cell selects the whole row →
        # the button enables (the single-click interaction the selectRow(0) test above masks).
        from gui.panels.distance_stars import StarsWithinDistanceSolPanel
        from PySide6.QtWidgets import QAbstractItemView
        panel = self._panel(StarsWithinDistanceSolPanel)
        result = {"count": 1, "limit_ly": 15.0, "stars": [
            {"Star Name": "Tau Ceti", "Star Designations": "HD 10700",
             "Spectral Type": "G8V", "Light Years": 11.9, "x": 1.0, "y": 2.0, "z": 3.0}]}
        panel._render(result)
        self.app.processEvents()
        view = panel._results_table
        self.assertEqual(view.selectionBehavior(), QAbstractItemView.SelectionBehavior.SelectRows)
        self.assertFalse(panel._wiki_btn.isEnabled())
        view.setCurrentIndex(view.model().index(0, 1))   # a single cell in a non-zero column
        self.app.processEvents()
        self.assertTrue(panel._wiki_btn.isEnabled())
        self.assertTrue(view.selectionModel().selectedRows())

    def test_g1_search_second_button_opens_detail_tab(self):
        from gui.panels.search import StarSystemsSearchPanel
        panel = self._panel(StarSystemsSearchPanel)
        panel._render({"stars": [{"star_name": "Tau Ceti", "designations": "HD 10700",
                                  "spectral_type": "G8V", "light_years": 11.9,
                                  "app_magnitude": 3.5}],
                       "capped": False, "cap": 500})
        self.app.processEvents()
        # The wiki button is hidden until a row is selected.
        self.assertFalse(panel._wiki_btn.isVisible())
        with mock.patch.object(wiki, "resolve_and_fetch",
                               return_value={"found": False, "tried": []}):
            panel._open_wiki_star({"star_name": "Tau Ceti"})
            self.assertTrue(any("📖 Tau Ceti — Wikipedia" == t
                                for t in self._tab_titles(panel._tabs)))
        self.app.processEvents()


@unittest.skipUnless(_GUI_OK, "PySide6 not available")
class ExternalLinkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_wsl_routes_to_windows_browser(self):
        calls = []
        with mock.patch.object(wtab, "_is_wsl", return_value=True), \
             mock.patch.object(wtab.subprocess, "Popen",
                               side_effect=lambda cmd, **kw: calls.append(cmd)):
            ok = wtab._open_url_external("https://en.wikipedia.org/wiki/Tau_Ceti")
        self.assertTrue(ok)
        self.assertEqual(len(calls), 1)                       # first opener that launches wins
        self.assertIn("https://en.wikipedia.org/wiki/Tau_Ceti", calls[0])

    def test_wsl_falls_through_to_next_opener(self):
        calls = []

        def popen(cmd, **kw):
            calls.append(cmd)
            if cmd[0] == "wslview":
                raise FileNotFoundError                       # not installed → try next
        with mock.patch.object(wtab, "_is_wsl", return_value=True), \
             mock.patch.object(wtab.subprocess, "Popen", side_effect=popen):
            wtab._open_url_external("https://x/y")
        self.assertEqual([c[0] for c in calls][:2], ["wslview", "powershell.exe"])

    def test_non_wsl_uses_qt_opener(self):
        with mock.patch.object(wtab, "_is_wsl", return_value=False), \
             mock.patch.object(wtab.QDesktopServices, "openUrl", return_value=True) as m:
            wtab._open_url_external("https://x/y")
        self.assertTrue(m.called)

    def test_on_link_resolves_relative_and_ignores_fragment(self):
        from PySide6.QtCore import QUrl
        view = WikipediaView()
        with mock.patch.object(wtab, "_open_url_external") as m:
            view._on_link(QUrl("/wiki/Cetus"))
            m.assert_called_once_with("https://en.wikipedia.org/wiki/Cetus")
            m.reset_mock()
            view._on_link(QUrl("#Distance"))                  # in-page fragment → ignored
            m.assert_not_called()


if __name__ == "__main__":
    unittest.main()
