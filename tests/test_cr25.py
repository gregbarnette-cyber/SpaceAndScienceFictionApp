# tests/test_cr25.py — CR-25 exclusion wind-wiring fix ("2a").
#
# Offline, in-process (no socket: the SIMBAD otype-list seam `core.databases._simbad_otypes_tap` and
# the exclusion resolvers are mocked; the catalog cache is disabled or pointed at a tmp dir). Covers:
#   CR-25.1 — `wind_state` is a full 4-value bin override on any MS star (manual > otype > colour).
#   CR-25.2 — the full-otype-list active auto-detect ({BY*, Er*, Fl*, RS*, UV*}, exact codes, K/M only)
#             + the bounded one-query SIMBAD fetch (`databases.fetch_star_otypes`) + its degrade.
#   CR-25.3 — `wind_class_provenance` / `wind_otype` / `wind_class_note` / `wind_otype_source`.
#   CR-25.4 — exclusion-system coverage (system --wind-state, per-component otype threading).
# The live anchors (EV Lac 13.42, GJ 65 via G 272-61A, …) run in tests/test_cr25_live.py.

import os
import tempfile
import time
import types
import unittest
from unittest import mock

from core import databases
from core import exclusion_wall as ew

# ── live-probe otype lists (SIMBAD TAP, 2026-09-24 — the independent authority) ──────────────────
_LISTS = {
    "EV Lac":    ["*", "**", "Er*", "IR", "MIR", "NIR", "PM*", "Rad", "UV", "V*", "X"],
    "Proxima":   ["*", "**", "Er*", "IR", "MIR", "NIR", "PM*", "Ro*", "UV", "V*", "X"],
    "AU Mic":    ["*", "**", "BY*", "Er*", "IR", "LM*", "MIR", "NIR", "PM*", "UV", "V*", "X"],
    "Wolf 359":  ["*", "Er*", "MIR", "NIR", "PM*", "UV", "V*", "X"],
    "AD Leo":    ["*", "**", "Er*", "IR", "MIR", "NIR", "PM*", "Rad", "UV", "V*", "X"],
    "Barnard":   ["*", "**", "BY*", "IR", "MIR", "NIR", "PM*", "V*", "X"],
    "eps Eri":   ["*", "**", "BY*", "IR", "NIR", "PM*", "Ro*", "UV", "V*", "X"],
    "tau Cet":   ["*", "**", "IR", "NIR", "PM*", "Ro*", "UV", "X"],
    "Kapteyn":   ["*", "IR", "NIR", "PM*", "Ro*", "V*"],
    "GJ 65 head": ["*", "**", "IR", "MIR", "NIR", "PM*", "UV", "V*", "X"],
    "G 272-61A": ["*", "**", "Er*", "PM*", "V*"],
    "G 272-61B": ["*", "**", "Em*", "Er*", "PM*", "V*"],
    "kap01 Cet": ["*", "**", "BY*", "IR", "MIR", "NIR", "PM*", "Ro*", "UV", "V*", "X"],
    "EK Dra":    ["*", "**", "BY*", "Er*", "NIR", "Opt", "Ro*", "SB*", "UV", "V*", "X"],
    "alf Cen B": ["*", "**", "PM*"],
}


class _Cr25EnvMixin:
    """Disable the catalog cache + clear the CR-25 env knobs around each test (never write fake lists
    into the real data/catalog_cache, and never let a warm cache mask a missing mock)."""

    def setUp(self):
        self._env = dict(os.environ)
        os.environ["SPACE_APP_CATALOG_CACHE"] = "0"
        os.environ.pop("SPACE_APP_SIMBAD_TIMEOUT", None)
        os.environ.pop("SPACE_APP_SIMBAD_OTYPES_FORCE_UNREACHABLE", None)
        databases.reset_simbad_otypes_circuit()

    def tearDown(self):
        databases.reset_simbad_otypes_circuit()
        os.environ.clear()
        os.environ.update(self._env)


# ═════════════════════════════════ 1. the active-otype matcher ═══════════════════════════════════
class Cr25MatcherTest(unittest.TestCase):

    def test_each_active_code_hits(self):
        for code in ("BY*", "Er*", "Fl*", "RS*", "UV*"):
            self.assertEqual(ew.active_otype_matches(otypes=["PM*", code]), [code], code)

    def test_traps_never_hit(self):
        # bare UV = a UV-source flag; Ro* / V* over-broad; Em* / PM* / ** unrelated
        self.assertEqual(ew.active_otype_matches(otypes=["UV", "Ro*", "V*", "PM*", "**", "Em*", "*"]), [])

    def test_case_insensitive_whole_code(self):
        self.assertEqual(ew.active_otype_matches(otypes=["er*", "by*"]), ["BY*", "Er*"])
        self.assertEqual(ew.active_otype_matches(otypes=["Er"]), [])          # not a partial match

    def test_legacy_long_names(self):
        self.assertEqual(ew.active_otype_matches(otype="Flare Star"), ["Fl*"])
        self.assertEqual(ew.active_otype_matches(otype="UV Cet type"), ["UV*"])
        self.assertEqual(ew.active_otype_matches(otype="high proper-motion Star"), [])

    def test_pipe_list_form_and_sorted_output(self):
        self.assertEqual(ew.active_otype_matches(otype="Er*|BY*"), ["BY*", "Er*"])
        self.assertEqual(ew.active_otype_matches(otype=" Er* | PM* "), ["Er*"])

    def test_otypes_list_wins_over_primary(self):
        # the fetched full list is authoritative; the primary is only the degrade fallback
        self.assertEqual(ew.active_otype_matches(otype="BY*", otypes=["PM*"]), [])
        self.assertEqual(ew.active_otype_matches(otype="PM*", otypes=[]), [])

    def test_live_lists(self):
        want = {"EV Lac": ["Er*"], "Proxima": ["Er*"], "AU Mic": ["BY*", "Er*"], "Wolf 359": ["Er*"],
                "AD Leo": ["Er*"], "Barnard": ["BY*"], "eps Eri": ["BY*"], "tau Cet": [],
                "Kapteyn": [], "GJ 65 head": [], "G 272-61A": ["Er*"], "G 272-61B": ["Er*"],
                "kap01 Cet": ["BY*"], "EK Dra": ["BY*", "Er*"], "alf Cen B": []}
        for star, codes in want.items():
            self.assertEqual(ew.active_otype_matches(otypes=_LISTS[star]), codes, star)

    def test_superset_of_the_pre_cr25_flare_matcher(self):
        # every otype the old _is_flare_otype accepted still matches; only BY*/Er*/RS* are new
        for ot in ("Flare Star", "UV Cet", "fl*", "UV*", "Fl*"):
            self.assertTrue(_old_is_flare_otype(ot) and ew.active_otype_matches(otype=ot), ot)
        for ot in ("Er*", "BY*", "RS*"):
            self.assertTrue(not _old_is_flare_otype(ot) and ew.active_otype_matches(otype=ot), ot)
        for ot in (None, "", "star", "PM*", "UV", "Ro*", "V*"):
            self.assertEqual(ew.active_otype_matches(otype=ot), [], ot)

    def test_wr_agb_on_pipe_form_any_code(self):
        self.assertEqual(ew.classify_domain_wind(sp_type="M5", otype="C*|BY*")[:2],
                         (ew.EVOLVED, "agb_overwindy"))
        self.assertEqual(ew.classify_domain_wind(otype="PM*|WR*")[:2], (ew.EVOLVED, "wr_overwindy"))
        # a plain primary otype is unchanged
        self.assertEqual(ew.classify_domain_wind(otype="Wolf-Rayet")[:2], (ew.EVOLVED, "wr_overwindy"))


# ═════════════════════════════════ 2. bin precedence ═════════════════════════════════════════════
class Cr25PrecedenceTest(unittest.TestCase):

    def _w(self, **k):
        return ew.classify_wind(**k)

    def test_otype_auto_on_km(self):
        r = self._w(sp_type="M4.0Ve", otype="PM*", otypes=_LISTS["EV Lac"])
        self.assertEqual((r["wind_class"], r["wind_class_provenance"], r["wind_otype"]),
                         ("active", "otype_auto", ["Er*"]))
        self.assertIsNone(r["wind_class_note"])

    def test_manual_beats_otype_and_keeps_wind_otype(self):
        r = self._w(sp_type="M4.0Ve", otypes=_LISTS["EV Lac"], wind_state="quiet")
        self.assertEqual((r["wind_class"], r["wind_class_provenance"], r["wind_otype"]),
                         ("quiet", "manual", ["Er*"]))           # Q5: the overridden signal stays visible

    def test_manual_on_any_colour(self):
        r = self._w(sp_type="G8V", otypes=_LISTS["tau Cet"], wind_state="active")
        self.assertEqual((r["wind_class"], r["wind_class_provenance"], r["wind_otype"]),
                         ("active", "manual", None))
        for ws, wc in (("quiet", "quiet"), ("solar", "solar"), ("active", "active"), ("hot", "o_hot")):
            self.assertEqual(self._w(sp_type="M4V", wind_state=ws)["wind_class"], wc, ws)
            self.assertEqual(self._w(sp_type="G2V", wind_state=ws)["wind_class"], wc, ws)

    def test_colour_default_no_hit(self):
        r = self._w(sp_type="M1VIp", otypes=_LISTS["Kapteyn"])
        self.assertEqual((r["wind_class"], r["wind_class_provenance"], r["wind_otype"]),
                         ("quiet", "class_default", None))

    def test_q1_gate_g_stars_not_flipped(self):
        for star, sp in (("kap01 Cet", "G5V"), ("EK Dra", "G5VFe-0.7CH-1(k)")):
            r = self._w(sp_type=sp, otypes=_LISTS[star])
            self.assertEqual((r["wind_class"], r["wind_class_provenance"], r["wind_otype"]),
                             ("solar", "class_default", None), star)

    def test_q1_gate_no_hot_demotion(self):
        for sp, wc in (("O9V", "o_hot"), ("B2V", "b_hot"), ("A0V", "a_dwarf"), ("F5V", "f_dwarf")):
            r = self._w(sp_type=sp, otypes=["Er*", "BY*"])
            self.assertEqual((r["wind_class"], r["wind_class_provenance"]), (wc, "class_default"), sp)

    def test_cool_subdwarf_prefix(self):
        # sdM1 takes the sd-prefix MS branch (colour M) — the otype auto-detect applies
        r = self._w(sp_type="sdM1", otypes=["Er*"])
        self.assertEqual((r["domain"], r["wind_class"], r["class_note"]),
                         (ew.MAIN_SEQUENCE, "active", "cool subdwarf"))

    def test_lum_vi_colourless_subdwarf_defaults_to_k(self):
        with mock.patch("core.detection._host_class", lambda sp: "subdwarf"), \
                mock.patch("core.detection._sp_letter", lambda sp: None):
            r = self._w(sp_type="VI", otypes=["BY*"])
        self.assertEqual((r["wind_class"], r["wind_class_provenance"]), ("active", "otype_auto"))

    def test_primary_otype_used_when_no_list(self):
        r = self._w(sp_type="M4V", otype="BY*")                   # the degrade path: primary only
        self.assertEqual((r["wind_class"], r["wind_class_provenance"]), ("active", "otype_auto"))


# ═════════════════════════════════ 3. Q8 domain-consistency notes ════════════════════════════════
class Cr25Q8NoteTest(unittest.TestCase):

    def test_hot_on_cool_colours(self):
        for c, art in (("F", "an"), ("G", "a"), ("K", "a"), ("M", "an")):
            r = ew.classify_wind(sp_type=f"{c}5V", wind_state="hot")
            self.assertEqual(r["wind_class"], "o_hot")
            self.assertEqual(
                r["wind_class_note"],
                f"explicit wind_state 'hot' → o_hot (a line-driven hot-star wind) on {art} {c}-type "
                "main-sequence star — physically inconsistent; honored as an explicit override")

    def test_cool_bins_on_hot_colours(self):
        for c, art in (("O", "an"), ("B", "a")):
            for ws in ("quiet", "solar", "active"):
                r = ew.classify_wind(sp_type=f"{c}5V", wind_state=ws)
                self.assertEqual(r["wind_class"], ws)
                self.assertEqual(
                    r["wind_class_note"],
                    f"explicit wind_state '{ws}' → {ws} (a cool-star wind bin) on {art} {c}-type "
                    "main-sequence star — physically inconsistent; honored as an explicit override")

    def test_no_note_otherwise(self):
        self.assertIsNone(ew.classify_wind(sp_type="A0V", wind_state="hot")["wind_class_note"])
        self.assertIsNone(ew.classify_wind(sp_type="A0V", wind_state="quiet")["wind_class_note"])
        self.assertIsNone(ew.classify_wind(sp_type="O9V", wind_state="hot")["wind_class_note"])
        self.assertIsNone(ew.classify_wind(sp_type="M4V", wind_state="active")["wind_class_note"])
        self.assertIsNone(ew.classify_wind(wind_state="hot")["wind_class_note"])      # colourless bare


# ═════════════════════════════════ 4. Q3a + superseded notes ═════════════════════════════════════
class Cr25IgnoredAndSupersededNoteTest(unittest.TestCase):

    def test_q3a_non_ms_hosts(self):
        cases = (("K0III", ew.EVOLVED, "giant_overwindy", "class_default", "an evolved"),
                 ("DA2", ew.WINDLESS, None, None, "a windless (free-harbor)"),
                 ("sdB1", ew.UNMODELED, None, None, "an unmodeled"))
        for sp, dom, wc, prov, host in cases:
            base = ew.classify_wind(sp_type=sp)
            r = ew.classify_wind(sp_type=sp, wind_state="active")
            self.assertEqual((r["domain"], r["wind_class"], r["wind_class_provenance"]), (dom, wc, prov), sp)
            self.assertEqual((base["domain"], base["wind_class"]), (dom, wc), sp)   # class unchanged
            self.assertEqual(r["wind_class_note"],
                             f"wind_state 'active' does not set the wind bin of {host} host — the "
                             "identity-derived wind class stands")
            self.assertIsNone(base["wind_class_note"])

    def test_explicit_wind_class_supersedes_without_q8_leak(self):
        r = ew.classify_wind(class_tag="M4V", wind_class="solar", wind_state="hot")
        self.assertEqual((r["wind_class"], r["wind_class_provenance"]), ("solar", "manual"))
        self.assertEqual(r["wind_class_note"],
                         "wind_state 'hot' does not set the wind bin — superseded by the explicit wind_class "
                         "'solar'")

    def test_explicit_wind_class_over_windless_no_q3a(self):
        r = ew.classify_wind(sp_type="DA2", wind_class="solar")
        self.assertEqual((r["domain"], r["wind_class"], r["wind_class_provenance"], r["wind_class_note"]),
                         (ew.MAIN_SEQUENCE, "solar", "manual", None))

    def test_object_preset_shape(self):
        # the --object m-dwarf path passes wind_class="active" (the caller relabels it object_preset)
        r = ew.classify_wind(object_name="m-dwarf", wind_class="active", wind_state="quiet")
        self.assertEqual((r["domain"], r["wind_class"]), (ew.MAIN_SEQUENCE, "active"))
        self.assertEqual(r["wind_class_note"],
                         "wind_state 'quiet' does not set the wind bin — superseded by the explicit "
                         "wind_class 'active'")


# ═════════════════════════════════ 5. provenance table (plan §3) ═════════════════════════════════
class Cr25ProvenanceTableTest(unittest.TestCase):

    def _p(self, **k):
        r = ew.classify_wind(**k)
        return r["wind_class"], r["wind_class_provenance"], r["wind_otype"]

    def test_rows(self):
        self.assertEqual(self._p(sp_type="M4V", otypes=["Er*"]), ("active", "otype_auto", ["Er*"]))
        self.assertEqual(self._p(sp_type="M4V", otypes=["PM*"]), ("quiet", "class_default", None))
        self.assertEqual(self._p(sp_type="G2V", wind_state="active"), ("active", "manual", None))
        self.assertEqual(self._p(sp_type="G2V"), ("solar", "class_default", None))
        self.assertEqual(self._p(sp_type="K0III"), ("giant_overwindy", "class_default", None))
        self.assertEqual(self._p(otype="Wolf-Rayet"), ("wr_overwindy", "class_default", None))
        self.assertEqual(self._p(sp_type="DA2"), (None, None, None))
        self.assertEqual(self._p(sp_type="sdB1"), (None, None, None))
        self.assertEqual(self._p(), (None, None, None))                          # bare mass
        self.assertEqual(self._p(wind_state="solar"), ("solar", "manual", None))  # bare mass + flag
        self.assertEqual(self._p(object_name="brown-dwarf"), (None, None, None))
        self.assertEqual(self._p(class_tag="M4V", wind_class="active"), ("active", "manual", None))
        self.assertEqual(self._p(class_tag="M4V", wind_state="solar"), ("solar", "manual", None))
        self.assertEqual(self._p(class_tag="M4V", otype="Er*"), ("active", "otype_auto", ["Er*"]))
        self.assertEqual(self._p(class_tag="M4V", otype="BY*|Er*"),
                         ("active", "otype_auto", ["BY*", "Er*"]))


# ═════════════════════════════════ 6. back-compat / byte identity ════════════════════════════════
def _old_ms_wind_class(colour, wind_state=None, otype=None):          # pre-CR-25, verbatim
    if colour == "O":
        return "o_hot"
    if colour == "B":
        return "b_hot"
    if colour == "A":
        return "a_dwarf"
    if colour == "F":
        return "f_dwarf"
    if colour == "G":
        return "solar"
    if colour in ("K", "M"):
        active = (wind_state or "").strip().lower() == "active" or _old_is_flare_otype(otype)
        return "active" if active else "quiet"
    return ew._WIND_STATE_CLASS.get((wind_state or "").strip().lower())


def _old_is_flare_otype(otype):                                           # pre-CR-25, verbatim
    ot = (otype or "").strip().lower()
    return "flare" in ot or "uv cet" in ot or ot in ("fl*", "uv*")


def _old_classify_domain_wind(sp_type=None, otype=None, class_tag=None, wind_class=None,
                              object_name=None, wind_state=None):         # pre-CR-25, verbatim
    dom, wc, note = _old_classify_identity(sp_type, otype, class_tag, object_name, wind_state)
    if wind_class:
        w = str(wind_class).strip().lower()
        if w in ew.EMITTED_WIND_CLASSES:
            if dom is None or dom in (ew.WINDLESS, ew.UNMODELED):
                return ew._domain_for_wind_class(w), w, (note if dom is None else None)
            return dom, w, note
    if dom is None:
        return ew.MAIN_SEQUENCE, _old_ms_wind_class(None, wind_state, otype), None
    return dom, wc, note


def _old_classify_identity(sp_type, otype, class_tag, object_name, wind_state):   # pre-CR-25, verbatim
    from core import detection, shared
    obj = (object_name or "").strip().lower()
    if obj in ("brown-dwarf", "brown_dwarf", "rogue-planet", "rogue_planet", "rogue"):
        return ew.WINDLESS, None, ew._CLASS_NOTES[ew.WINDLESS]
    if class_tag:
        t = str(class_tag).strip().lower()
        if t in ew._WINDLESS_TAGS:
            return ew.WINDLESS, None, ew._CLASS_NOTES[ew.WINDLESS]
        if t in ew._EVOLVED_TAGS:
            return ew.EVOLVED, ew._EVOLVED_TAGS[t], None
        if t in ew._MS_TAGS:
            return ew.MAIN_SEQUENCE, _old_ms_wind_class(detection._sp_letter(sp_type), wind_state, otype), None
        sp_type = sp_type or class_tag
    if ew._is_wr_otype(otype):
        return ew.EVOLVED, "wr_overwindy", "Wolf-Rayet"
    if ew._is_agb_otype(otype):
        return ew.EVOLVED, "agb_overwindy", "AGB / Mira / carbon star"
    sp = (sp_type or "").strip()
    if not sp:
        return None, None, None
    lead = shared.spectral_leading_class(sp, letters=shared._SP_DISPLAY_LETTERS)
    if lead == "W":
        return ew.EVOLVED, "wr_overwindy", "Wolf-Rayet"
    if lead == "C":
        return ew.EVOLVED, "agb_overwindy", "carbon star"
    host = detection._host_class(sp)
    colour = detection._sp_letter(sp)
    if host in ("white_dwarf", "brown_dwarf"):
        return ew.WINDLESS, None, ew._CLASS_NOTES[ew.WINDLESS]
    if host == "subdwarf":
        if colour in ("O", "B"):
            return ew.UNMODELED, None, ew._CLASS_NOTES[ew.UNMODELED]
        return ew.MAIN_SEQUENCE, _old_ms_wind_class(colour or "K", wind_state, otype), "cool subdwarf"
    if host == "subgiant":
        if colour == "O":
            return ew.EVOLVED, "o_hot", "O subgiant"
        if colour == "B":
            return ew.EVOLVED, "b_hot", "B subgiant"
        return ew.EVOLVED, "subgiant_mild", "subgiant"
    if host == "giant":
        m = detection._LUM_CLASS_RE.search(sp)
        lc = m.group(1) if m else "III"
        if lc == "I":
            wc = "rsg_overwindy" if colour in ("K", "M") else "bsg_overwindy"
            return ew.EVOLVED, wc, "supergiant"
        if colour == "O":
            return ew.EVOLVED, "o_hot", "hot giant"
        if colour == "B":
            return ew.EVOLVED, "b_hot", "hot giant"
        if colour in ("K", "M"):
            return ew.EVOLVED, "giant_overwindy", ("M giant" if colour == "M" else "K giant")
        return ew.EVOLVED, "giant_mild", "giant"
    ms_note = "cool subdwarf" if (sp[:3] in ("esd", "usd") or sp[:2] == "sd") else None
    return ew.MAIN_SEQUENCE, _old_ms_wind_class(colour, wind_state, otype), ms_note


class Cr25ByteIdentityOracleTest(unittest.TestCase):
    """The new classifier == the verbatim pre-CR-25 one on every cell with no wind_state (and no new
    active code), across every _classify_identity branch; the only drift is the intended one — a
    wind_state on a COLOURED main-sequence star now sets the bin (CR-25.1)."""

    _SP = [None, "", "G2V", "K5V", "K1V", "M4V", "M4.0Ve", "dM6", "sdM1", "esdK7", "M1VIp", "K0III",
           "M2Iab", "G8IV", "B2IV", "O9IV", "O9V", "B2V", "A0V", "A0mA1Va", "F5V", "DA2", "L5", "T6",
           "sdB1", "sdO5", "WN6", "C5,4", "M7", "kA5hF0mF2", "M5.5V+M6V"]
    _TAGS = [None, "dwarf", "main-sequence", "giant", "wd", "brown-dwarf", "subgiant", "M4V", "G2V"]
    _OTYPES = [None, "star", "PM*", "Flare Star", "UV*", "UV Cet type", "fl*", "Wolf-Rayet", "Mira",
               "Ro*", "V*", "UV", "high proper-motion Star"]
    _OBJ = [None, "brown-dwarf", "rogue-planet", "m-dwarf"]
    _WC = [None, "solar", "o_hot", "giant_overwindy", "nonsense"]
    _WS = [None, "quiet", "solar", "active", "hot", "loud"]

    def test_oracle_sweep(self):
        bad = []
        n = 0
        for sp in self._SP:
            for tag in self._TAGS:
                for ot in self._OTYPES:
                    for obj in self._OBJ:
                        for wc in self._WC:
                            for ws in self._WS:
                                n += 1
                                k = dict(sp_type=sp, otype=ot, class_tag=tag, wind_class=wc,
                                         object_name=obj, wind_state=ws)
                                old = _old_classify_domain_wind(**k)
                                new = ew.classify_domain_wind(**k)
                                explicit = bool(wc) and str(wc).strip().lower() in ew.EMITTED_WIND_CLASSES
                                vws = ew._norm_wind_state(ws)
                                colour = ew._classify_identity(sp, ot, tag, obj)[3]
                                if vws and not explicit and new[0] == ew.MAIN_SEQUENCE and colour:
                                    # the intended CR-25.1 change: the bin follows the wind_state
                                    if new != (old[0], ew._WIND_STATE_CLASS[vws], old[2]):
                                        bad.append((k, old, new))
                                elif new != old:
                                    bad.append((k, old, new))
        self.assertGreater(n, 50000)
        self.assertEqual(bad[:5], [], f"{len(bad)} drifting cells")

    def test_three_tuple_shape(self):
        r = ew.classify_domain_wind(sp_type="M4V", wind_state="active")
        self.assertIsInstance(r, tuple)
        self.assertEqual(len(r), 3)

    def test_component_domain_unchanged(self):
        import core.exclusion_system as es
        self.assertEqual(es._component_domain(sp_type="M7", otype="Mira")[0], "evolved")
        self.assertEqual(es._component_domain(sp_type="M7")[0], "main_sequence")


# ═════════════════════════════════ 7. the SIMBAD otype-list fetch ════════════════════════════════
def _rows(mapping, qids=None):
    """{main_id: [codes]} (+ optional {main_id: [matched idents]}, default = the main_id itself) → the
    seam's [(main_id, matched_ident, otype)] rows (one per ident × code, like the TAP join)."""
    qids = qids or {}
    return [(mid, q, c) for mid, codes in mapping.items() for q in qids.get(mid, [mid]) for c in codes]


class Cr25FetchTest(_Cr25EnvMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self._backoff = mock.patch("core.databases._SIMBAD_RETRY_BACKOFF", 0.0)
        self._backoff.start()
        self._warn = mock.patch("core.databases._simbad_warn")
        self.warn = self._warn.start()

    def tearDown(self):
        self._backoff.stop()
        self._warn.stop()
        super().tearDown()

    def _seam(self, result=None, exc=None, calls=None):
        def f(adql):
            if calls is not None:
                calls.append(adql)
            if exc is not None:
                raise exc
            return result
        return mock.patch("core.databases._simbad_otypes_tap", f)

    def test_distinct_a_candidate(self):
        calls = []
        rows = _rows({"G 272-61": _LISTS["GJ 65 head"], "G 272-61A": _LISTS["G 272-61A"]})
        with self._seam(rows, calls=calls):
            r = databases.fetch_star_otypes("G 272-61", "PM*")
        self.assertEqual(r, {"codes": sorted(_LISTS["G 272-61A"]), "source_main_id": "G 272-61A",
                             "source_is_self": False, "status": None, "fallback_to_head": False,
                             "candidate": "G 272-61 A"})
        self.assertIn("i.id = 'G 272-61'", calls[0])
        self.assertIn("i.id = 'G 272-61 A'", calls[0])
        self.assertEqual(len(calls), 1)                                    # ONE TAP call

    def test_candidate_unresolved_is_a_fallback(self):
        with self._seam(_rows({"V* EV Lac": _LISTS["EV Lac"]})):
            r = databases.fetch_star_otypes("V* EV Lac", "PM*")
        self.assertEqual((r["codes"], r["source_main_id"], r["source_is_self"], r["fallback_to_head"]),
                         (sorted(_LISTS["EV Lac"]), "V* EV Lac", True, True))

    def test_candidate_resolving_to_the_head_itself_is_not_a_fallback(self):
        # Sirius: '* alf CMa A' is an identifier OF '* alf CMa' (live-verified) → not a fallback
        rows = _rows({"* alf CMa": ["*", "SB*"]}, qids={"* alf CMa": ["* alf CMa", "* alf CMa A"]})
        with self._seam(rows):
            r = databases.fetch_star_otypes("* alf CMa", "SB*")
        self.assertEqual((r["source_is_self"], r["fallback_to_head"], r["status"]), (True, False, None))

    def test_component_letter_main_ids_have_no_candidate(self):
        for mid in ("* alf Cen B", "G 272-61B", "BD+19  5116A", "*  61 Cyg A"):
            calls = []
            with self._seam(_rows({mid: ["PM*"]}), calls=calls):
                r = databases.fetch_star_otypes(mid, "PM*")
            self.assertEqual(calls[0].count("i.id ="), 1, mid)           # never inherits A's list
            self.assertEqual((r["source_is_self"], r["fallback_to_head"]), (True, False), mid)

    def test_component_rule_false(self):
        calls = []
        with self._seam(_rows({"G 272-61B": _LISTS["G 272-61B"]}), calls=calls):
            r = databases.fetch_star_otypes("G 272-61B", "PM*", component_rule=False)
        self.assertEqual(calls[0].count("i.id ="), 1)
        self.assertEqual((r["codes"], r["fallback_to_head"]), (sorted(_LISTS["G 272-61B"]), False))

    def test_apostrophe_escaped_and_main_id_stripped(self):
        calls = []
        with self._seam(_rows({"NAME Barnard's star": _LISTS["Barnard"]}), calls=calls):
            r = databases.fetch_star_otypes("  NAME Barnard's star ", "BY*")
        self.assertIn("i.id = 'NAME Barnard''s star'", calls[0])
        self.assertIn("i.id = 'NAME Barnard''s star A'", calls[0])
        self.assertEqual(r["status"], None)

    def test_raw_main_id_lone_object_is_self(self):
        rows = _rows({"V* EV Lac": _LISTS["EV Lac"]}, qids={"V* EV Lac": ["EV Lac"]})
        with self._seam(rows):
            r = databases.fetch_star_otypes("EV Lac", "PM*")               # a raw/masked main_id string
        self.assertEqual((r["source_main_id"], r["source_is_self"], r["status"]), ("V* EV Lac", True, None))

    def test_raw_main_id_head_alias_plus_candidate_object(self):
        rows = _rows({"G 272-61": _LISTS["GJ 65 head"], "G 272-61A": _LISTS["G 272-61A"]},
                     qids={"G 272-61": ["GJ 65"], "G 272-61A": ["GJ 65 A"]})
        with self._seam(rows):
            r = databases.fetch_star_otypes("GJ 65", "PM*")
        self.assertEqual((r["source_main_id"], r["source_is_self"], r["status"]), ("G 272-61A", False, None))

    def test_raw_main_id_only_candidate_resolved(self):
        rows = _rows({"G 272-61A": _LISTS["G 272-61A"]}, qids={"G 272-61A": ["G 272-61A"]})
        with self._seam(rows):
            r = databases.fetch_star_otypes("G 272-61", "PM*")
        self.assertEqual((r["source_main_id"], r["source_is_self"]), ("G 272-61A", False))

    def test_zero_rows_is_error_never_retried(self):
        calls = []
        with self._seam([], calls=calls):
            r = databases.fetch_star_otypes("V* EV Lac", "PM*")
        self.assertEqual(r, {"codes": ["PM*"], "source_main_id": None, "source_is_self": True,
                             "status": "error", "fallback_to_head": False, "candidate": "V* EV Lac A"})
        self.assertEqual(len(calls), 1)
        self.warn.assert_called()

    def test_ambiguous_many_objects_is_error(self):
        with self._seam(_rows({"X": ["PM*"], "X A": ["Er*"], "Y": ["BY*"]})):
            r = databases.fetch_star_otypes("X", "PM*")
        self.assertEqual(r["status"], "error")

    def test_watchdog_timeout_trips_the_breaker(self):
        os.environ["SPACE_APP_SIMBAD_TIMEOUT"] = "0.1"

        def slow(adql):
            time.sleep(0.5)
            return _rows({"V* EV Lac": _LISTS["EV Lac"]})
        with mock.patch("core.databases._simbad_otypes_tap", slow):
            r = databases.fetch_star_otypes("V* EV Lac", "BY*")
        self.assertEqual((r["status"], r["codes"], r["fallback_to_head"]), ("timeout", ["BY*"], False))
        # the breaker is open: the next fetch short-circuits without touching the seam
        calls = []
        with self._seam(_rows({"* alf Cen B": ["PM*"]}), calls=calls):
            r2 = databases.fetch_star_otypes("* alf Cen B", "PM*")
        self.assertEqual((calls, r2["status"]), ([], "timeout"))
        databases.reset_simbad_otypes_circuit()
        with self._seam(_rows({"* alf Cen B": ["PM*"]}), calls=calls):
            r3 = databases.fetch_star_otypes("* alf Cen B", "PM*")
        self.assertEqual((len(calls), r3["status"]), (1, None))

    def test_breaker_open_still_serves_a_cached_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SPACE_APP_CATALOG_CACHE"] = "1"
            import pathlib
            with mock.patch("core.catalog_cache._CACHE_DIR", pathlib.Path(tmp)):
                with self._seam(_rows({"V* EV Lac": _LISTS["EV Lac"]})):
                    first = databases.fetch_star_otypes("V* EV Lac", "PM*")
                with mock.patch("core.databases._simbad_otypes_down", ("timeout", time.monotonic())):
                    with self._seam(exc=AssertionError("seam hit")):
                        again = databases.fetch_star_otypes("V* EV Lac", "PM*")
        self.assertEqual(again, first)

    def test_breaker_rearms_after_cooldown(self):
        with mock.patch("core.databases._simbad_otypes_down", ("timeout", time.monotonic() - 999)):
            self.assertFalse(databases._simbad_otypes_circuit_open())

    def test_real_pyvo_exceptions_are_unreachable(self):
        import requests
        from pyvo.dal import DALServiceError, DALFormatError
        for exc in (DALServiceError("Unable to access the capabilities endpoint at: … Connection failed"),
                    DALFormatError(requests.exceptions.ConnectionError("boom")),
                    requests.exceptions.ConnectionError("boom"), OSError("net down")):
            with self._seam(exc=exc):
                r = databases.fetch_star_otypes("V* EV Lac", "PM*")
            self.assertEqual(r["status"], "unreachable", repr(exc))

    def test_retry_once_then_success(self):
        n = {"i": 0}

        def flaky(adql):
            n["i"] += 1
            if n["i"] == 1:
                raise OSError("transient")
            return _rows({"V* EV Lac": _LISTS["EV Lac"]})
        with mock.patch("core.databases._simbad_otypes_tap", flaky):
            r = databases.fetch_star_otypes("V* EV Lac", "PM*")
        self.assertEqual((n["i"], r["status"]), (2, None))

    def test_hook_short_circuits_before_cache_and_seam(self):
        os.environ["SPACE_APP_SIMBAD_OTYPES_FORCE_UNREACHABLE"] = "1"
        calls = []
        with self._seam(_rows({"V* EV Lac": _LISTS["EV Lac"]}), calls=calls), \
                mock.patch("core.catalog_cache.cache_get", side_effect=AssertionError("cache read")):
            r = databases.fetch_star_otypes("V* EV Lac", "PM*")
        self.assertEqual((calls, r["status"], r["codes"]), ([], "unreachable", ["PM*"]))

    def test_timeout_env(self):
        os.environ["SPACE_APP_SIMBAD_TIMEOUT"] = "0"
        self.assertIsNone(databases._simbad_otype_timeout())
        os.environ["SPACE_APP_SIMBAD_TIMEOUT"] = "-3"
        self.assertIsNone(databases._simbad_otype_timeout())
        os.environ["SPACE_APP_SIMBAD_TIMEOUT"] = "abc"
        self.assertEqual(databases._simbad_otype_timeout(), 30.0)
        os.environ["SPACE_APP_SIMBAD_TIMEOUT"] = "12.5"
        self.assertEqual(databases._simbad_otype_timeout(), 12.5)
        os.environ.pop("SPACE_APP_SIMBAD_TIMEOUT")
        self.assertEqual(databases._simbad_otype_timeout(), 30.0)

    def test_unbounded_passes_none_timeout(self):
        os.environ["SPACE_APP_SIMBAD_TIMEOUT"] = "0"
        seen = {}

        def fake_bounded(fn, *, timeout, retries, backoff, fatal=()):
            seen.update(timeout=timeout, retries=retries)
            return fn()
        with self._seam(_rows({"V* EV Lac": _LISTS["EV Lac"]})), \
                mock.patch("core.databases._bounded_call", fake_bounded):
            r = databases.fetch_star_otypes("V* EV Lac", "PM*")
        self.assertEqual((seen, r["status"]), ({"timeout": None, "retries": 2}, None))

    def test_falsy_main_id_no_call(self):
        calls = []
        with self._seam([], calls=calls):
            self.assertIsNone(databases.fetch_star_otypes("", "PM*"))
            self.assertIsNone(databases.fetch_star_otypes("   ", "PM*"))
            self.assertIsNone(databases.fetch_star_otypes(None, "PM*"))
        self.assertEqual(calls, [])

    def test_cache_discipline(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SPACE_APP_CATALOG_CACHE"] = "1"
            import pathlib
            with mock.patch("core.catalog_cache._CACHE_DIR", pathlib.Path(tmp)):
                # a failed fetch and an empty result never reach the cache
                with self._seam(exc=OSError("down")):
                    self.assertEqual(databases.fetch_star_otypes("V* EV Lac", "PM*")["status"], "unreachable")
                with self._seam([]):
                    self.assertEqual(databases.fetch_star_otypes("V* EV Lac", "PM*")["status"], "error")
                self.assertEqual(list(pathlib.Path(tmp).glob("*.json")), [])
                # a success is cached; the next call does not touch the seam
                with self._seam(_rows({"V* EV Lac": _LISTS["EV Lac"]})):
                    first = databases.fetch_star_otypes("V* EV Lac", "PM*")
                self.assertEqual(len(list(pathlib.Path(tmp).glob("*.json"))), 1)
                calls = []
                with self._seam(exc=AssertionError("seam hit"), calls=calls):
                    second = databases.fetch_star_otypes("V* EV Lac", "PM*")
                self.assertEqual((calls, second), ([], first))

    def test_seam_uses_a_fresh_pyvo_service_per_call(self):
        from astropy.table import Table
        made = []

        class _Svc:
            def __init__(self, baseurl):
                made.append(baseurl)

            def run_sync(self, adql):
                t = Table({"main_id": ["V* EV Lac", "V* EV Lac"], "qid": ["V* EV Lac"] * 2,
                           "otype": ["Er*", "PM*"]})
                return types.SimpleNamespace(to_table=lambda: t)
        with mock.patch("pyvo.dal.TAPService", _Svc):
            a = databases._simbad_otypes_tap("SELECT 1")
            databases._simbad_otypes_tap("SELECT 1")
        self.assertEqual(a, [("V* EV Lac", "V* EV Lac", "Er*"), ("V* EV Lac", "V* EV Lac", "PM*")])
        self.assertEqual(len(made), 2)
        self.assertTrue(made[0].endswith("/simbad/sim-tap"))


# ═════════════════════════════════ 8. the fetch-relevance gate ═══════════════════════════════════
def _relevant(**k):
    return ew.classify_wind(**k)["otype_list_relevant"]


class Cr25RelevanceGateTest(unittest.TestCase):

    def test_km_main_sequence_only(self):
        for sp in ("M4V", "M4.0Ve", "K2V", "dM6", "sdM1", "M5.5V+M6V"):
            self.assertTrue(_relevant(sp_type=sp), sp)
        for sp in ("G2V", "G8V", "F5V", "A0V", "B2V", "O9V", "K0III", "M2Iab", "DA2", "L5", "sdB1",
                   "WN6", "", None):
            self.assertFalse(_relevant(sp_type=sp), sp)
        self.assertFalse(_relevant(sp_type="M7", otype="Mira"))     # AGB by otype
        self.assertTrue(_relevant(class_tag="M4V"))
        self.assertFalse(_relevant(class_tag="wd"))


if __name__ == "__main__":
    unittest.main()


# ═════════════════════════════════ 9. exclusion-boundary wiring (query.py) ═══════════════════════
import argparse                                                    # noqa: E402

_WALL_ACTIVE = 6.0 * 5 ** 0.5                                        # √(Ẇ/Ẇ☉)·6 AU, Ẇ = 1e-13
_WALL_QUIET = 6.0 * 0.005 ** 0.5                                     # Ẇ = 1e-16 (the floor)
_EVLAC_BCLUM = 0.0127                                                # a fixture L (inversion mass)

_SIMBAD = {
    "EV Lac": {"main_id": "V* EV Lac", "sp_type": "M4.0Ve", "otype": "PM*", "designations": {}},
    "GJ 65": {"main_id": "G 272-61", "sp_type": "M5.5V+M6V", "otype": "**", "designations": {}},
    "tau Cet": {"main_id": "* tau Cet", "sp_type": "G8V", "otype": "PM*", "designations": {}},
    "Barnard": {"main_id": "NAME Barnard's star", "sp_type": "M4V", "otype": "BY*", "designations": {}},
    "Sirius B": {"main_id": "* alf CMa B", "sp_type": "DA2", "otype": "WD*", "designations": {}},
    "Feige": {"main_id": "HD 900001", "sp_type": "sdB1", "otype": "sdB*", "designations": {}},
    "Arcturus": {"main_id": "* alf Boo", "sp_type": "K1.5III", "otype": "RG*", "designations": {}},
    "Nameless": {"main_id": "", "sp_type": "M4V", "otype": "PM*", "designations": {}},
}


def _run_boundary(**overrides):
    import query
    args = argparse.Namespace(
        mass_msun=None, object=None, star=None, spectral_type=None, luminosity_lsun=None,
        mass_loss_msun_yr=None, wind_state=None, wind_speed=None, v_ism=None, c_ms=None,
        b_field=None, n_cloud=None, cloud_temp=None, wind_phase_yr=None, f_shock=None,
        m_shock_min=None, mass_loss_source=None, dial=None, calibration_au=47.5,
        alpha=1.0 / 3.0, beta=0.0, gamma=0.0, scan_alpha=False, star_mass_catalog=None,
        gaia_timeout=None)
    for k, v in overrides.items():
        setattr(args, k, v)
    cap = {}
    with mock.patch("query._out", lambda r: cap.__setitem__("r", r)):
        query.cmd_exclusion_boundary(args)
    return cap["r"]


def _star_mocks(seam_rows=None, seam=None):
    """compute_simbad_lookup / regions / FLAME mocked; the otype fetch runs for real over a mocked
    network seam (so the wiring + fetch + classifier chain is exercised end-to-end, offline)."""
    rows = seam_rows or {}

    def _tap(adql):
        for mid, lst in rows.items():
            if f"i.id = '{mid.replace(chr(39), chr(39) * 2)}'" in adql:
                return _rows({mid: lst})
        return []
    return [
        mock.patch("core.databases.compute_simbad_lookup",
                   lambda name: dict(_SIMBAD[name]) if name in _SIMBAD else {"error": "nope"}),
        mock.patch("core.regions.compute_star_system_regions_from_simbad",
                   lambda sl: {"bcLuminosity": _EVLAC_BCLUM}),
        mock.patch("core.binary.gaia_source_id_from_designations", lambda d: None),   # FLAME miss
        mock.patch("core.catalog.gaia_astrophysical", lambda **k: {"parameters": {"mass_flame": None}}),
        mock.patch("core.databases._simbad_otypes_tap", seam or _tap),
        mock.patch("core.databases._simbad_warn"),
    ]


class Cr25BoundaryWiringTest(_Cr25EnvMixin, unittest.TestCase):

    def _star(self, name, rows=None, seam=None, **kw):
        ps = _star_mocks(rows, seam)
        for p in ps:
            p.start()
        try:
            return _run_boundary(star=name, **kw)
        finally:
            for p in reversed(ps):
                p.stop()

    def _rex(self, alpha=1.0 / 3.0):
        return 47.5 * (_EVLAC_BCLUM ** 0.2632) ** alpha             # the FLAME-miss inversion standoff

    def test_spectral_type_wind_state_now_honored(self):
        r = _run_boundary(spectral_type="M4V", wind_state="active")
        self.assertEqual((r["wind_class"], r["wind_class_provenance"], r["wind_otype"]),
                         ("active", "manual", None))
        self.assertAlmostEqual(r["wall_au"], _WALL_ACTIVE, places=9)
        self.assertEqual(r["mass_loss_msun_yr"], 1e-13)
        d = _run_boundary(spectral_type="M4V")
        self.assertEqual((d["wind_class"], d["wind_class_provenance"]), ("quiet", "class_default"))
        self.assertAlmostEqual(d["wall_au"], _WALL_QUIET, places=9)
        self.assertEqual(r["r_ex_au"], d["r_ex_au"])                      # standoff unmoved (γ=0)

    def test_star_ev_lac_otype_auto(self):
        r = self._star("EV Lac", {"V* EV Lac": _LISTS["EV Lac"]})
        self.assertEqual((r["wind_class"], r["wind_class_provenance"], r["wind_otype"],
                          r["wind_otype_source"], r["wind_class_note"]),
                         ("active", "otype_auto", ["Er*"], None, None))
        self.assertAlmostEqual(r["wall_au"], _WALL_ACTIVE, places=9)
        self.assertEqual(r["wall_route"], "wind_term")
        self.assertAlmostEqual(r["r_ex_au"], self._rex(), places=9)
        self.assertNotIn("otype_status", r)
        self.assertEqual(r["mass_loss_provenance"], "class_default")

    def test_star_ev_lac_overrides(self):
        q = self._star("EV Lac", {"V* EV Lac": _LISTS["EV Lac"]}, wind_state="quiet")
        self.assertEqual((q["wind_class"], q["wind_class_provenance"], q["wind_otype"]),
                         ("quiet", "manual", ["Er*"]))
        self.assertAlmostEqual(q["wall_au"], _WALL_QUIET, places=9)
        a = self._star("EV Lac", {"V* EV Lac": _LISTS["EV Lac"]}, wind_state="active")
        self.assertEqual((a["wind_class"], a["wind_class_provenance"]), ("active", "manual"))
        self.assertEqual(q["r_ex_au"], a["r_ex_au"])

    def test_rate_axis_keeps_the_identity_label(self):              # E1
        r = self._star("EV Lac", {"V* EV Lac": _LISTS["EV Lac"]}, mass_loss_msun_yr=1e-13)
        self.assertEqual((r["wind_class"], r["wind_class_provenance"], r["mass_loss_provenance"]),
                         ("active", "otype_auto", "supplied"))
        self.assertAlmostEqual(r["wall_au"], _WALL_ACTIVE, places=9)

    def test_gj65_list_from_the_a_component(self):
        rows = {"G 272-61": _LISTS["GJ 65 head"]}

        def seam(adql):                                               # one query, both ids
            assert "i.id = 'G 272-61'" in adql and "i.id = 'G 272-61 A'" in adql
            return (_rows({"G 272-61": _LISTS["GJ 65 head"]})
                    + _rows({"G 272-61A": _LISTS["G 272-61A"]}))
        r = self._star("GJ 65", rows, seam=seam)
        self.assertEqual((r["wind_class"], r["wind_class_provenance"], r["wind_otype"],
                          r["wind_otype_source"]), ("active", "otype_auto", ["Er*"], "G 272-61A"))

    def test_no_fetch_for_a_g_star(self):
        def boom(adql):
            raise AssertionError("fetched for a G star")
        r = self._star("tau Cet", seam=boom)
        self.assertEqual((r["wind_class"], r["wind_class_provenance"], r["wind_otype"]),
                         ("solar", "class_default", None))
        self.assertAlmostEqual(r["wall_au"], 6.0, places=9)
        a = self._star("tau Cet", seam=boom, wind_state="active")
        self.assertEqual((a["wind_class"], a["wind_class_provenance"]), ("active", "manual"))

    def test_degrade_hook(self):
        os.environ["SPACE_APP_SIMBAD_OTYPES_FORCE_UNREACHABLE"] = "1"
        r = self._star("EV Lac", {"V* EV Lac": _LISTS["EV Lac"]})
        self.assertEqual((r["wind_class"], r["otype_status"], r["wind_otype_source"]),
                         ("quiet", "unreachable", None))
        b = self._star("Barnard", {"NAME Barnard's star": _LISTS["Barnard"]})
        self.assertEqual((b["wind_class"], b["wind_class_provenance"], b["otype_status"]),
                         ("active", "otype_auto", "unreachable"))   # primary BY* still auto-detects

    def test_q3a_notes_on_non_ms_spectral_types(self):
        for sp, dom in (("DA2", ew.WINDLESS), ("K0III", ew.EVOLVED), ("sdB1", ew.UNMODELED)):
            r = _run_boundary(spectral_type=sp, wind_state="active")
            self.assertEqual(r["domain"], dom, sp)
            self.assertIn("does not set the wind bin", r["wind_class_note"], sp)
            self.assertIn("wind_class_provenance", r, sp)
            self.assertIn("wind_otype_source", r, sp)

    def test_object_presets(self):
        r = _run_boundary(object="m-dwarf", wind_state="quiet")
        self.assertEqual((r["wind_class"], r["wind_class_provenance"]), ("active", "object_preset"))
        self.assertEqual(r["wind_class_note"],
                         "wind_state 'quiet' does not set the wind bin — the --object preset's wind_class "
                         "'active' is fixed")
        s = _run_boundary(object="sun")
        self.assertEqual((s["wind_class"], s["wind_class_provenance"], s["wind_class_note"], s["r_ex_au"]),
                         ("solar", "object_preset", None, 47.5))
        self.assertAlmostEqual(s["wall_au"], 6.0, places=9)
        bd = _run_boundary(object="brown-dwarf")
        self.assertEqual((bd["wind_class"], bd["wind_class_provenance"]), (None, None))

    def test_bare_mass(self):
        r = _run_boundary(mass_msun=0.3)
        self.assertEqual((r["wind_class"], r["wind_class_provenance"]), (None, None))
        m = _run_boundary(mass_msun=0.3, wind_state="solar")
        self.assertEqual((m["wind_class"], m["wind_class_provenance"]), ("solar", "manual"))

    def test_q7_gamma_standoff_untouched(self):
        rows = {"V* EV Lac": _LISTS["EV Lac"]}
        e = self._star("EV Lac", rows, alpha=0.4, gamma=0.2)
        self.assertIn("wind exponent set without", e["error"])       # otype_auto never feeds the standoff
        q = self._star("EV Lac", rows, alpha=0.4, gamma=0.2, wind_state="quiet")
        a = self._star("EV Lac", rows, alpha=0.4, gamma=0.2, wind_state="active")
        base = self._rex(0.4)
        self.assertAlmostEqual(q["r_ex_au"], base * (1e-16 / 2e-14) ** 0.2, places=9)
        self.assertAlmostEqual(a["r_ex_au"], base * (1e-13 / 2e-14) ** 0.2, places=9)
        self.assertAlmostEqual(a["wall_au"], _WALL_ACTIVE, places=9)   # the wall now follows the flag
        self.assertAlmostEqual(q["wall_au"], _WALL_QUIET, places=9)

    def test_star_non_ms_branches_carry_the_fields_by_value(self):
        def boom(adql):
            raise AssertionError("fetched for a non-MS host")
        cases = (("Sirius B", ew.WINDLESS, None, None, "a windless (free-harbor)"),
                 ("Feige", ew.UNMODELED, None, None, "an unmodeled"),
                 ("Arcturus", ew.EVOLVED, "giant_overwindy", "class_default", "an evolved"))
        for name, dom, wc, prov, host in cases:
            d = self._star(name, seam=boom)
            self.assertEqual((d["domain"], d["wind_class"], d["wind_class_provenance"], d["wind_otype"],
                              d["wind_otype_source"], d["wind_class_note"]), (dom, wc, prov, None, None, None),
                             name)
            f = self._star(name, seam=boom, wind_state="active")
            self.assertEqual(f["wind_class_note"],
                             f"wind_state 'active' does not set the wind bin of {host} host — the "
                             "identity-derived wind class stands", name)
            self.assertEqual(f["wind_class"], wc, name)

    def test_falsy_main_id_skips_the_fetch(self):
        def boom(adql):
            raise AssertionError("fetched with no main_id")
        r = self._star("Nameless", seam=boom)
        self.assertEqual((r["wind_class"], r["wind_class_provenance"]), ("quiet", "class_default"))
        self.assertNotIn("otype_status", r)

    def test_evolved_gamma_note_says_the_standoff_still_uses_it(self):
        from core import exclusion_boundary as xb
        r = xb.compute_two_layer_boundary(mass_msun=1.5, sp_type="K0III", wind_state="active",
                                          alpha=0.4, gamma=0.2)
        self.assertTrue(r["wind_class_note"].endswith(
            "; at γ>0 the regulated standoff's Ẇ term still uses it (pre-existing, unchanged)"))
        self.assertAlmostEqual(r["r_ex_au"], 47.5 * 1.5 ** 0.4 * (1e-13 / 2e-14) ** 0.2, places=9)
        g0 = xb.compute_two_layer_boundary(mass_msun=1.5, sp_type="K0III", wind_state="active", alpha=0.4)
        self.assertNotIn("γ>0", g0["wind_class_note"])
        self.assertEqual(g0["r_ex_au"], 47.5 * 1.5 ** 0.4)


# ═════════════════════════════════ 10. exclusion-system coverage (CR-25.4) ═══════════════════════
import core.exclusion_system as es                                   # noqa: E402

_EQPEG_CAT = {"stars": [
    {"main_id": "BD+19  5116 A", "aliases": [], "mass_solar": 0.39, "citation": "t"},
    {"main_id": "BD+19  5116 B", "aliases": [], "mass_solar": 0.25, "citation": "t"},
]}
_EQPEG_SOLS = [{"companion": {"mass_ratio_q": 0.64}, "period_d": 300000.0, "eccentricity": 0.3,
                "source": "sb9", "grade": "b"}]
_SYS_SIMBAD = {
    "EV Lac": {"main_id": "V* EV Lac", "sp_type": "M4.0Ve", "otype": "PM*", "designations": {}},
    "EQ Peg": {"main_id": "BD+19  5116", "sp_type": "M3.5V", "otype": "Er*", "designations": {}},
    "BD+19  5116 B": {"main_id": "BD+19  5116B", "sp_type": "M4.5V", "otype": "PM*", "designations": {}},
    "Wolf 9999": {"main_id": "GJ 9999", "sp_type": "M4V", "otype": "star", "designations": {}},
    "Mira X": {"main_id": "V* Mira X", "sp_type": "M5e", "otype": "Mi*", "designations": {}},
}


class Cr25SystemWiringTest(_Cr25EnvMixin, unittest.TestCase):

    def _sys(self, seam=None, solutions=None, bclum=_EVLAC_BCLUM, **kw):
        ps = [mock.patch("core.databases.compute_simbad_lookup",
                         lambda name: dict(_SYS_SIMBAD[name]) if name in _SYS_SIMBAD else {"error": "nope"}),
              mock.patch("core.binary.binary_orbit", lambda **k: {"solutions": solutions or []}),
              mock.patch("core.binary.gaia_source_id_from_designations", lambda d: None),
              mock.patch("core.databases._simbad_warn")]
        if bclum is not None:
            ps.append(mock.patch("core.regions.compute_star_system_regions_from_simbad",
                                 lambda sl: {"bcLuminosity": bclum}))
        if seam is not None:
            ps.append(mock.patch("core.databases._simbad_otypes_tap", seam))
        for p in ps:
            p.start()
        try:
            return es.compute_exclusion_system(**kw)
        finally:
            for p in reversed(ps):
                p.stop()

    @staticmethod
    def _comps(r):
        return {c["id"]: c for z in r["zones"] for c in z["components"]}

    def _evlac_seam(self, adql):
        return _rows({"V* EV Lac": _LISTS["EV Lac"]})

    def test_star_ev_lac(self):
        r = self._sys(self._evlac_seam, star="EV Lac", alpha=0.4)
        c = self._comps(r)["V* EV Lac"]
        self.assertEqual((c["wind_class"], c["wind_class_provenance"], c["wind_otype"], c["wind_otype_source"]),
                         ("active", "otype_auto", ["Er*"], None))
        self.assertEqual(c["mass_loss_msun_yr"], 1e-13)
        self.assertAlmostEqual(c["wall_au"], _WALL_ACTIVE, places=9)
        self.assertAlmostEqual(c["r_ex_au"], 47.5 * (_EVLAC_BCLUM ** 0.2632) ** 0.4, places=9)
        self.assertNotIn("otype_status", r)
        q = self._comps(self._sys(self._evlac_seam, star="EV Lac", alpha=0.4, wind_state="quiet"))["V* EV Lac"]
        self.assertEqual((q["wind_class"], q["wind_class_provenance"], q["wind_otype"]), ("quiet", "manual", ["Er*"]))
        self.assertAlmostEqual(q["wall_au"], _WALL_QUIET, places=9)
        self.assertEqual(q["r_ex_au"], c["r_ex_au"])

    def test_star_single_body_degrade(self):
        os.environ["SPACE_APP_SIMBAD_OTYPES_FORCE_UNREACHABLE"] = "1"
        r = self._sys(self._evlac_seam, star="EV Lac", alpha=0.4)
        self.assertEqual(r["otype_status"], "unreachable")
        self.assertEqual(self._comps(r)["V* EV Lac"]["wind_class"], "quiet")

    def test_component_overrides_fixed_not_broken(self):              # E6: the discriminating pair
        cases = (("class=G2V,mass=1.0,wind_state=active", "active", 6.0, _WALL_ACTIVE),
                 ("class=M4V,mass=0.2,wind_state=solar", "solar", _WALL_QUIET, 6.0),
                 ("class=M4V,mass=0.2,wind_state=active", "active", _WALL_ACTIVE, _WALL_ACTIVE),
                 ("class=G2V,mass=1.0,wind_state=solar", "solar", 6.0, 6.0))
        for spec, wc, old_wall, new_wall in cases:
            c = list(self._comps(es.compute_exclusion_system(component_specs=[spec])).values())[0]
            self.assertEqual((c["wind_class"], c["wind_class_provenance"]), (wc, "manual"), spec)
            self.assertAlmostEqual(c["wall_au"], new_wall, places=9, msg=spec)
        # the pre-CR-25 classifier gave the OLD walls for the first two (the bug) — pinned via the oracle
        self.assertEqual(_old_classify_domain_wind(class_tag="G2V", wind_state="active")[1], "solar")
        self.assertEqual(_old_classify_domain_wind(class_tag="M4V", wind_state="solar")[1], "quiet")

    def test_component_otype_pipe_list(self):
        c = list(self._comps(es.compute_exclusion_system(
            component_specs=["class=M4V,mass=0.2,otype=BY*|Er*"])).values())[0]
        self.assertEqual((c["wind_class"], c["wind_class_provenance"], c["wind_otype"], c["wind_otype_source"]),
                         ("active", "otype_auto", ["BY*", "Er*"], None))

    def test_system_wind_state_rules(self):
        specs = ["id=A,class=G2V,mass=1.0,pair=AB,sma=900,ecc=0",
                 "id=B,class=M4V,mass=0.3,wind_state=quiet,pair=AB,sma=900,ecc=0",
                 "id=C,class=M4V,mass=0.3,wind_class=solar,pair=AC,sma=5000,ecc=0",
                 "id=W,class=wd,mass=0.6,pair=AW,sma=8000,ecc=0",
                 "id=G,class=K0III,mass=1.5,pair=AG,sma=20000,ecc=0"]
        r = es.compute_exclusion_system(component_specs=specs, wind_state="active")
        c = self._comps(r)
        self.assertEqual((c["A"]["wind_class"], c["A"]["wind_class_provenance"], c["A"]["wind_class_note"]),
                         ("active", "manual", None))                            # MS, injected
        self.assertEqual((c["B"]["wind_class"], c["B"]["wind_class_note"]), ("quiet", None))  # own wins
        self.assertEqual(c["C"]["wind_class"], "solar")
        self.assertEqual(c["C"]["wind_class_note"],
                         "system --wind-state 'active' does not set the wind bin — superseded by the explicit "
                         "wind_class 'solar'")
        self.assertEqual((c["W"]["domain"], c["W"]["wind_class"]), (ew.WINDLESS, None))
        self.assertEqual(c["W"]["wind_class_note"],
                         "system --wind-state 'active' not applied: a windless (free-harbor) host — the "
                         "identity-derived wind class stands")
        self.assertEqual((c["G"]["domain"], c["G"]["wind_class"]), (ew.EVOLVED, "giant_overwindy"))
        self.assertIn("an evolved host", c["G"]["wind_class_note"])

    def test_system_wind_state_not_fed_to_an_evolved_gamma_standoff(self):     # E4
        spec = ["id=G,class=K0III,mass=1.5"]
        r = es.compute_exclusion_system(component_specs=spec, wind_state="active", gamma=0.2)
        self.assertIn("wind exponent set without", r["error"])                  # as before (not injected)
        own = es.compute_exclusion_system(component_specs=["id=G,class=K0III,mass=1.5,wind_state=active"],
                                          gamma=0.2)
        g = self._comps(own)["G"]
        self.assertAlmostEqual(g["r_ex_au"], 47.5 * 1.5 ** 0.4 * 5 ** 0.2, places=9)
        self.assertTrue(g["wind_class_note"].endswith("still uses it (pre-existing, unchanged)"))

    def _eqpeg_seam(self, a_rows, b_rows=None, b_exc=None):
        def seam(adql):
            if "BD+19  5116B" in adql:
                if b_exc is not None:
                    raise b_exc
                return b_rows
            return a_rows
        return seam

    def test_binary_attribution_never_unions(self):
        a_rows = (_rows({"BD+19  5116": ["*", "**", "Er*", "PM*"]})
                  + _rows({"BD+19  5116A": ["*", "PM*", "V*"]}))         # the A object itself: quiet
        b_rows = _rows({"BD+19  5116B": ["*", "Er*", "PM*"]})
        r = self._sys(self._eqpeg_seam(a_rows, b_rows), solutions=_EQPEG_SOLS, bclum=None,
                      star="EQ Peg", star_mass_catalog=None, alpha=0.4)
        self.assertNotIn("error", r, r)
        c = self._comps(r)
        a, b = c["BD+19  5116"], c["BD+19  5116 B"]
        self.assertEqual((a["wind_class"], a["wind_otype"], a["wind_otype_source"]),
                         ("quiet", None, "BD+19  5116A"))               # head's Er* is NOT A's
        self.assertEqual((b["wind_class"], b["wind_class_provenance"], b["wind_otype"], b["wind_otype_source"]),
                         ("active", "otype_auto", ["Er*"], None))
        self.assertFalse(any("otype list taken from the system head" in n for n in r.get("resolution_notes", [])))

    def test_binary_unresolved_candidate_note_and_degrade_b(self):
        import requests
        a_rows = _rows({"BD+19  5116": ["*", "**", "Er*", "PM*"]})       # candidate did not resolve
        r = self._sys(self._eqpeg_seam(a_rows, b_exc=requests.exceptions.ConnectionError("down")),
                      solutions=_EQPEG_SOLS, bclum=None, star="EQ Peg", alpha=0.4)
        c = self._comps(r)
        self.assertEqual((c["BD+19  5116"]["wind_class"], c["BD+19  5116"]["wind_otype_source"]),
                         ("active", None))
        self.assertIn("component A otype list taken from the system head 'BD+19  5116' (no distinct "
                      "'BD+19  5116 A' SIMBAD object)", r["resolution_notes"])
        self.assertEqual(r["otype_status_b"], "unreachable")
        self.assertNotIn("otype_status_a", r)
        self.assertEqual(c["BD+19  5116 B"]["wind_class"], "quiet")     # degraded to its primary PM*

    def test_mass_error_path_never_fetches(self):
        def boom(adql):
            raise AssertionError("fetched before the mass resolved")
        with mock.patch("core.regions.compute_star_system_regions_from_simbad",
                        lambda sl: {"error": "no V"}):
            r = self._sys(boom, bclum=None, star="Wolf 9999")
        self.assertIn("could not resolve a mass", r["error"])

    def test_r3_primary_otype_threaded_into_compose(self):
        def boom(adql):
            raise AssertionError("fetched for an evolved host")
        r = self._sys(boom, bclum=None, star="Mira X", alpha=0.4)
        self.assertNotIn("error", r, r)
        c = self._comps(r)["V* Mira X"]
        self.assertEqual((c["domain"], c["wind_class"], c["wind_class_provenance"]),
                         (ew.EVOLVED, "agb_overwindy", "class_default"))

    def test_merged_alpha_cen_byte_identical_but_for_the_new_keys(self):
        from tests.test_exclusion_system import _CR13_CAT
        sols = [{"companion": {"mass_ratio_q": 0.84}, "period_d": 29174.0, "eccentricity": 0.524,
                 "source": "sb9", "grade": "b"}]
        m = {"alpha Centauri": {"main_id": "* alf Cen", "sp_type": "G2V", "otype": "SB*",
                                "designations": {"HD": "HD 128620"}},
             "* alf Cen B": {"main_id": "* alf Cen B", "sp_type": "K1V", "otype": "PM*",
                             "designations": {"HD": "HD 128621"}}}
        new_keys = {"wind_class_provenance", "wind_otype", "wind_otype_source", "wind_class_note",
                    "mass_loss_msun_yr"}

        def run(fetch):
            ps = [mock.patch("core.databases.compute_simbad_lookup",
                             lambda name: dict(m[name]) if name in m else {"error": "nope"}),
                  mock.patch("core.binary.binary_orbit", lambda **k: {"solutions": sols}),
                  mock.patch("core.databases.fetch_star_otypes", fetch)]
            for p in ps:
                p.start()
            try:
                comps, notes, _meta = es._resolve_system_from_star("alpha Centauri", _CR13_CAT)
                return es.compose_exclusion_system(comps, alpha=0.4)
            finally:
                for p in reversed(ps):
                    p.stop()
        with_list = run(lambda mid, primary_otype=None, component_rule=True: {
            "codes": _LISTS["alf Cen B"], "source_main_id": mid, "source_is_self": True, "status": None,
            "fallback_to_head": False})
        no_list = run(lambda mid, primary_otype=None, component_rule=True: None)   # the pre-CR-25 path

        def strip(r):
            return {**r, "zones": [{**z, "components": [{k: v for k, v in c.items() if k not in new_keys}
                                                        for c in z["components"]]} for z in r["zones"]]}
        self.assertEqual(strip(with_list), strip(no_list))
        c = {x["id"]: x for z in with_list["zones"] for x in z["components"]}
        self.assertAlmostEqual(c["* alf Cen"]["r_ex_au"], 47.5 * 1.079 ** 0.4, places=9)
        self.assertAlmostEqual(c["* alf Cen B"]["r_ex_au"], 47.5 * 0.909 ** 0.4, places=9)
        self.assertEqual((c["* alf Cen B"]["wind_class"], c["* alf Cen B"]["wind_otype"]), ("quiet", None))


class Cr25Cp3RegressionTest(_Cr25EnvMixin, unittest.TestCase):
    """CP3 review fixes: γ caveat only with a standoff; bin-scoped notes; the γ>0 withheld-flag error;
    per-component mass_loss_provenance; arg checks before network; binary A never takes the head otype."""

    def test_no_gamma_caveat_without_a_standoff(self):
        r = _run_boundary(spectral_type="K0III", wind_state="active", gamma=0.2)
        self.assertIsNone(r["standoff_au"])
        self.assertNotIn("γ>0", r["wind_class_note"])

    def test_own_wind_state_superseded_by_wind_class_but_feeds_the_gamma_standoff(self):
        r = es.compute_exclusion_system(
            component_specs=["id=A,class=G2V,mass=1.0,wind_state=active,wind_class=solar"], gamma=0.3)
        c = r["zones"][0]["components"][0]
        self.assertEqual(c["wind_class"], "solar")
        self.assertAlmostEqual(c["r_ex_au"], 47.5 * 5 ** 0.3, places=9)
        self.assertEqual(c["wind_class_note"],
                         "wind_state 'active' does not set the wind bin — superseded by the explicit "
                         "wind_class 'solar'; at γ>0 the regulated standoff's Ẇ term still uses it "
                         "(pre-existing, unchanged)")

    def test_system_wind_state_on_explicit_wind_class_ms(self):
        r = es.compute_exclusion_system(component_specs=["id=A,class=G2V,mass=1.0,wind_class=solar"],
                                        wind_state="active", gamma=0.3)
        c = r["zones"][0]["components"][0]
        self.assertEqual(c["wind_class"], "solar")
        self.assertAlmostEqual(c["r_ex_au"], 47.5 * 5 ** 0.3, places=9)    # MS: the standoff takes it
        self.assertTrue(c["wind_class_note"].startswith("system --wind-state 'active' does not set the wind bin"))
        self.assertTrue(c["wind_class_note"].endswith("(pre-existing, unchanged)"))

    def test_withheld_system_flag_error_explains_itself(self):
        r = es.compute_exclusion_system(component_specs=["id=G,class=K0III,mass=1.5"],
                                        wind_state="active", gamma=0.2)
        self.assertIn("the system --wind-state reaches main-sequence components only", r["error"])
        plain = es.compute_exclusion_system(component_specs=["id=G,class=K0III,mass=1.5"], gamma=0.2)
        self.assertNotIn("system --wind-state", plain["error"])

    def test_per_component_mass_loss_provenance(self):
        r = es.compute_exclusion_system(component_specs=[
            "id=A,class=M4V,mass=0.3,pair=AB,sma=9000,ecc=0",
            "id=B,class=M4V,mass=0.3,mass_loss_msun_yr=3e-14,pair=AB,sma=9000,ecc=0",
            "id=W,class=wd,mass=0.6,pair=AW,sma=20000,ecc=0"])
        c = {x["id"]: x for z in r["zones"] for x in z["components"]}
        self.assertEqual((c["A"]["mass_loss_msun_yr"], c["A"]["mass_loss_provenance"]), (1e-16, "class_default"))
        self.assertEqual((c["B"]["mass_loss_msun_yr"], c["B"]["mass_loss_provenance"]), (3e-14, "supplied"))
        self.assertEqual((c["W"]["mass_loss_msun_yr"], c["W"]["mass_loss_provenance"]), (None, None))

    def test_bad_alpha_or_phase_costs_no_network(self):
        with mock.patch("core.databases.compute_simbad_lookup", side_effect=AssertionError("network")):
            self.assertIn("--alpha", es.compute_exclusion_system(star="EV Lac", alpha=0.9)["error"])
            self.assertIn("--phase", es.compute_exclusion_system(star="EV Lac", phase="sideways")["error"])

    def test_binary_a_degrade_never_takes_the_head_primary(self):
        # EQ Peg-style: the head's PRIMARY otype is Er*; A's fetch degrades → A must not read it
        import requests
        t = Cr25SystemWiringTest()
        def seam(adql):
            if "BD+19  5116B" in adql:
                return _rows({"BD+19  5116B": ["*", "PM*"]})
            raise requests.exceptions.ConnectionError("A down")
        r = t._sys(seam, solutions=_EQPEG_SOLS, bclum=None, star="EQ Peg", alpha=0.4)
        c = {x["id"]: x for z in r["zones"] for x in z["components"]}
        a = c["BD+19  5116"]
        self.assertEqual((a["wind_class"], a["wind_class_provenance"], a["wind_otype"]),
                         ("quiet", "class_default", None))
        self.assertEqual(r["otype_status_a"], "unreachable")


class Cr25Cp4RegressionTest(_Cr25EnvMixin, unittest.TestCase):
    """CP4 review fixes: deterministic query failures → `error` (never retried); a mixed-case own
    wind_state reaches the FROZEN standoff normalized; the cache key carries the queried candidate."""

    def test_seam_maps_query_errors_and_bad_columns_to_result_errors(self):
        from pyvo.dal import DALQueryError
        from astropy.table import Table

        class _Bad:
            def __init__(self, baseurl):
                pass

            def run_sync(self, adql):
                raise DALQueryError("Unknown column 'qid'")

        class _Renamed:
            def __init__(self, baseurl):
                pass

            def run_sync(self, adql):
                t = Table({"main_id": ["X"], "otype_code": ["Er*"]})
                return types.SimpleNamespace(to_table=lambda: t)
        for svc in (_Bad, _Renamed):
            with mock.patch("pyvo.dal.TAPService", svc):
                with self.assertRaises(databases._OtypeResultError):
                    databases._simbad_otypes_tap("SELECT 1")

    def test_deterministic_error_is_not_retried(self):
        calls = []

        def seam(adql):
            calls.append(adql)
            raise databases._OtypeResultError("SIMBAD TAP query error")
        with mock.patch("core.databases._simbad_otypes_tap", seam), \
                mock.patch("core.databases._simbad_warn"), \
                mock.patch("core.databases._SIMBAD_RETRY_BACKOFF", 0.0):
            r = databases.fetch_star_otypes("V* EV Lac", "PM*")
        self.assertEqual((r["status"], len(calls)), ("error", 1))

    def test_bounded_call_fatal_types_skip_the_retry(self):
        from core.shared import _bounded_call
        n = {"i": 0}

        def f():
            n["i"] += 1
            raise KeyError("x")
        with self.assertRaises(KeyError):
            _bounded_call(f, timeout=1, retries=2, backoff=0.0, fatal=(KeyError,))
        self.assertEqual(n["i"], 1)
        n["i"] = 0
        with self.assertRaises(KeyError):
            _bounded_call(f, timeout=1, retries=2, backoff=0.0)          # default: retried
        self.assertEqual(n["i"], 2)

    def test_mixed_case_own_wind_state(self):
        for gamma in (0.0, 0.3):
            r = es.compute_exclusion_system(component_specs=["class=M4V,mass=0.2,wind_state=Active"],
                                            gamma=gamma)
            self.assertNotIn("error", r, (gamma, r))
            c = r["zones"][0]["components"][0]
            self.assertEqual((c["wind_class"], c["wind_class_provenance"]), ("active", "manual"))
        bad = es.compute_exclusion_system(component_specs=["class=M4V,mass=0.2,wind_state=loud"])
        self.assertIn("Unknown --wind-state 'loud'", bad["error"])          # unrecognized: curated error

    def test_cache_key_carries_the_candidate(self):
        seen = {}

        def fake_cached(service, params, producer, ttl_s=None):
            seen.update(service=service, params=params)
            return _rows({"G 272-61": _LISTS["GJ 65 head"]})
        with mock.patch("core.catalog_cache.cached", fake_cached):
            databases.fetch_star_otypes("G 272-61", "PM*")
        self.assertEqual(seen["params"], {"main_id": "G 272-61", "component_rule": True,
                                          "candidate": "G 272-61 A"})
