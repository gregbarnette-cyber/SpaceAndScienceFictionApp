# tests/test_designation_display.py — Phase AN3: Bayer/Flamsteed display rendering.
#
# AN3 is RENDERING ONLY. Nothing here may change what is stored: the raw SIMBAD
# string ("*  18 Eri") stays the identifier and the pretty form ("18 Eridani") is
# built at a display site on demand. That is why AN3 cannot move the AN4.1 golden
# baseline — a golden diff during this part means something is wrong, and
# test_the_golden_baseline_cannot_move below states the reason in executable form.
#
# Two halves:
#
#   1. The renderer (core.shared.format_star_designation) — the Greek table built
#      here, the constellation genitive table INHERITED from Phase AO, and the
#      superscript numeral, which is on a live path: α Cen A/B are the only corpus
#      stars whose Bayer id survives D3's dedupe, and they survive it precisely
#      because they carry the "* alf01 Cen" form (PHASE_AN_PLAN.md §4b).
#
#   2. The stripper (core.shared.strip_star_prefix) — the D9 double-space fix. Three
#      display sites open-coded `name[len("* "):]` with no follow-up .strip(), so a
#      Flamsteed id rendered as " 18 Eri". That already misrendered 796 live
#      star_systems rows BEFORE this phase; the fix stands on its own merits.

import json
import pathlib
import unittest

import core.shared as shared

_CORPUS_PATH = pathlib.Path(__file__).resolve().parent / "fixtures" / "designation_ids.json"


def _corpus_star_ids():
    """Every `* `-family id in the committed fixture corpus (`** ` included)."""
    with open(_CORPUS_PATH, encoding="utf-8") as fh:
        stars = json.load(fh)["stars"]
    return [i for s in stars for i in s["ids"] if str(i).startswith("*")]


class GreekTableTest(unittest.TestCase):
    """The one table AN3 owns. AO owns the genitive table — see OwnershipTest."""

    def test_all_24_letters_are_present(self):
        self.assertEqual(
            len({v for k, v in shared._GREEK_ABBREVIATIONS.items() if len(k) == 3}), 24
        )

    def test_the_four_non_obvious_simbad_spellings(self):
        # These are why the table was verified against live SIMBAD rather than
        # transcribed: SIMBAD pads to three characters with a TRAILING PERIOD and
        # transliterates xi/theta/omicron. Getting any of them wrong silently
        # renders the raw token instead ("mu. Ceti"), with no error.
        self.assertEqual(shared.format_star_designation("* mu. Cet"), "μ Ceti")
        self.assertEqual(shared.format_star_designation("* ksi Boo"), "ξ Boötis")
        self.assertEqual(shared.format_star_designation("* tet Ori"), "θ Orionis")
        self.assertEqual(shared.format_star_designation("* omi Cet"), "ο Ceti")

    def test_bayer_extension_letters_pass_through_verbatim(self):
        # Bayer designations are not exclusively Greek — gouldDesignations.csv
        # carries 300+ single-Latin-letter ones. They are already display form, so
        # an unmapped token must survive rather than be dropped or flagged.
        self.assertEqual(shared.format_star_designation("* b Vel"), "b Velorum")
        self.assertEqual(shared.format_star_designation("* h Per"), "h Persei")

    def test_a_latin_letter_cannot_collide_with_a_greek_key(self):
        # The reason case-folding the lookup is safe: every Greek key is 2-3 chars
        # and every extension letter is exactly one.
        self.assertTrue(all(len(k) >= 2 for k in shared._GREEK_ABBREVIATIONS))


class RendererTest(unittest.TestCase):

    def test_flamsteed_is_the_common_case(self):
        # On a `* `-main_id star the Bayer pick equals MAIN_ID and D3 eats it, so
        # the id this phase actually surfaces is the Flamsteed one — never a main
        # id. These four are the ones named in PHASE_AN_PLAN.md §5.
        self.assertEqual(shared.format_star_designation("*  10 CMi"), "10 Canis Minoris")
        self.assertEqual(shared.format_star_designation("*   9 CMa"), "9 Canis Majoris")
        self.assertEqual(shared.format_star_designation("*   3 Lyr"), "3 Lyrae")
        self.assertEqual(shared.format_star_designation("*  24 PsA"), "24 Piscis Austrini")

    def test_bayer(self):
        self.assertEqual(shared.format_star_designation("* alf CMi"), "α Canis Minoris")
        self.assertEqual(shared.format_star_designation("* eps Eri"), "ε Eridani")

    def test_the_superscript_numeral_is_on_a_live_path(self):
        # α Cen A/B are the corpus stars whose Bayer id survives D3 (§4b), so this
        # shape is not hypothetical — it is the only Bayer rendering most users
        # will ever see on a real star.
        self.assertEqual(shared.format_star_designation("* alf01 Cen"), "α¹ Centauri")
        self.assertEqual(shared.format_star_designation("* alf02 Cen"), "α² Centauri")
        self.assertEqual(shared.format_star_designation("* omi02 Eri B"), "ο² Eridani B")

    def test_component_letters_survive_on_both_systems(self):
        self.assertEqual(shared.format_star_designation("* alf CMi A"), "α Canis Minoris A")
        self.assertEqual(shared.format_star_designation("*  40 Eri B"), "40 Eridani B")

    def test_a_double_system_id_renders_nothing(self):
        # `** ` names a double SYSTEM, not this star (D2). Returning a confident
        # display name for the wrong object is worse than returning none.
        self.assertIsNone(shared.format_star_designation("** LDS 6248A"))
        self.assertIsNone(shared.format_star_designation("** SHB    1A"))

    def test_non_star_family_ids_render_nothing(self):
        for i in ("NAME Ran", "HD 61421", "GJ 280", "", None):
            self.assertIsNone(shared.format_star_designation(i))

    def test_it_degrades_rather_than_invents(self):
        # Mirrors constellation_genitive's own contract: an unknown code keeps its
        # raw abbreviation, never a made-up name.
        self.assertEqual(shared.format_star_designation("* alf Xyz"), "α Xyz")
        self.assertEqual(shared.format_star_designation("*  10 Xyz"), "10 Xyz")
        self.assertEqual(shared.format_star_designation("* alf"), "α")

    def test_a_variable_id_renders_too(self):
        # Same shape, costs nothing, and means promoting "Variable" to a key later
        # (D2 says one line) needs no display work either.
        self.assertEqual(shared.format_star_designation("V* eps Eri"), "ε Eridani")

    def test_every_corpus_star_id_renders_cleanly(self):
        # Corpus-wide sweep: no leading/trailing space, no leftover prefix, and no
        # raw 3-letter Greek token surviving into a display name.
        for i in _corpus_star_ids():
            out = shared.format_star_designation(i)
            if out is None:
                self.assertTrue(i.startswith("** "), i)
                continue
            self.assertEqual(out, out.strip(), i)
            self.assertFalse(out.startswith("*"), i)
            first = out.split()[0]
            self.assertNotIn(first.lower(), shared._GREEK_ABBREVIATIONS, i)


class StripperTest(unittest.TestCase):
    """D9's double space — the pre-existing display bug AN3 fixes."""

    def test_the_flamsteed_double_space_does_not_leak(self):
        # The exact regression: `name[len("* "):]` returns " 18 Eri" here.
        self.assertEqual(shared.strip_star_prefix("*  18 Eri"), "18 Eri")
        self.assertEqual(shared.strip_star_prefix("*   9 CMa"), "9 CMa")

    def test_the_other_prefixes(self):
        self.assertEqual(shared.strip_star_prefix("* alf CMi"), "alf CMi")
        self.assertEqual(shared.strip_star_prefix("V* eps Eri"), "eps Eri")
        self.assertEqual(shared.strip_star_prefix("NAME Ran"), "Ran")

    def test_a_double_system_prefix_is_left_alone(self):
        # Deliberate: `** ` names a different object, so stripping it would label
        # this star with the system's id. Also cannot be stripped by accident —
        # "** X" does not satisfy startswith("* ") (plan [A4]).
        self.assertEqual(shared.strip_star_prefix("** LDS 6248A"), "** LDS 6248A")
        self.assertFalse("** LDS 6248A".startswith("* "))

    def test_it_is_safe_on_anything(self):
        for raw, want in (("HD 61421", "HD 61421"), ("", ""), (None, "")):
            self.assertEqual(shared.strip_star_prefix(raw), want)

    def test_no_display_site_open_codes_the_slice_any_more(self):
        # The three sites the AN3 sweep found broken (two identical plot_helpers
        # label loops + generate_star_map_html.short_name). Pinned by source
        # inspection because none of the three has any other test coverage — the
        # sweep confirmed that too.
        root = pathlib.Path(__file__).resolve().parent.parent
        for rel in ("gui/visualizations/plot_helpers.py", "generate_star_map_html.py"):
            src = (root / rel).read_text(encoding="utf-8")
            self.assertNotIn('for prefix in ("NAME ", "* ", "V* ")', src, rel)
            self.assertIn("strip_star_prefix", src, rel)


class DictEntryPointTest(unittest.TestCase):

    def test_it_returns_bayer_then_flamsteed(self):
        self.assertEqual(
            shared.format_designation_names({"Bayer": "* alf CMi", "Flamsteed": "*  10 CMi"}),
            [("Bayer", "α Canis Minoris"), ("Flamsteed", "10 Canis Minoris")],
        )

    def test_it_is_empty_for_the_normal_star(self):
        # Most stars carry neither key, and NO narrow-key-set caller ever does
        # (D7: opts 17/19/20/21 + the seven route planners). The GUI helper is a
        # no-op in both cases, which is what makes it safe to call unconditionally.
        self.assertEqual(shared.format_designation_names({}), [])
        self.assertEqual(shared.format_designation_names(None), [])
        self.assertEqual(
            shared.format_designation_names(dict.fromkeys(shared._NARROW_DESIG_KEYS)), []
        )

    def test_a_key_present_but_none_is_skipped(self):
        self.assertEqual(
            shared.format_designation_names({"Bayer": None, "Flamsteed": "*  18 Eri"}),
            [("Flamsteed", "18 Eridani")],
        )


class OwnershipTest(unittest.TestCase):
    """AN3 builds the Greek table and CONSUMES AO's genitive table (§7)."""

    def test_the_genitive_table_is_not_rebuilt(self):
        # If AN3 had rebuilt it, the two copies could drift and "Centauri" would
        # come from whichever the renderer happened to import.
        root = pathlib.Path(__file__).resolve().parent.parent
        src = (root / "core" / "shared.py").read_text(encoding="utf-8")
        self.assertEqual(src.count("_CONSTELLATION_GENITIVES = {"), 1)
        self.assertEqual(len(shared._CONSTELLATION_GENITIVES), 88)

    def test_the_renderer_reads_that_table(self):
        # Not a tautology: it asserts the renderer goes through the shared
        # accessor, so an unknown code degrades by AO's rule rather than AN3's.
        self.assertEqual(shared.constellation_genitive("CMi"), "Canis Minoris")
        self.assertIsNone(shared.constellation_genitive("Xyz"))


class ScopeGuardTest(unittest.TestCase):

    def test_the_golden_baseline_cannot_move(self):
        """Rendering is never stored, so no producer output can change (§7a).

        Stated executably because it is AN3's whole acceptance criterion: the
        renderer is absent from every path that builds a designation dict or a
        desig_str. If a future edit calls it from `_match_designations` or
        `_join_designations`, the pretty form starts reaching
        star_systems.designations and the query.py contract — and the golden diff
        that follows would look like a harness failure rather than a scope breach.
        """
        for fn in (shared._match_designations, shared._join_designations,
                   shared._parse_designations, shared._parse_designations_from_ids):
            src = __import__("inspect").getsource(fn)
            self.assertNotIn("format_star_designation", src, fn.__name__)
            self.assertNotIn("format_designation_names", src, fn.__name__)

    def test_the_raw_id_is_still_the_identifier(self):
        # Round-trip: what AN2 stores is untouched by AN3 existing.
        desig = shared._match_designations(
            ["* alf CMi", "*  10 CMi", "NAME Procyon"], shared._CSV_DESIG_KEYS
        )
        self.assertEqual(desig["Bayer"], "* alf CMi")
        self.assertEqual(desig["Flamsteed"], "*  10 CMi")


if __name__ == "__main__":
    unittest.main()
