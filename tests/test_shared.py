# tests/test_shared.py — offline unit coverage for core/shared.py helpers.
#
# Phase 6 seeds this file with the P6.1 Retry-After coverage; Phase 7 (P7.1) expands
# it with the designation/spectral/error-classification helpers. Pure offline, no Qt.

import unittest
from unittest import mock

import core.shared as shared

from tests._queryharness import save_main_sequence_cache, restore_main_sequence_cache


class _FakeResp:
    def __init__(self, headers):
        self.headers = headers


class _FakeHTTPError(Exception):
    """Mimics requests.HTTPError: carries a .response with a .headers dict."""
    def __init__(self, retry_after=None, has_response=True):
        super().__init__("fake http error")
        if has_response:
            hdrs = {} if retry_after is None else {"Retry-After": retry_after}
            self.response = _FakeResp(hdrs)
        else:
            self.response = None


class RetryAfterSecondsTest(unittest.TestCase):
    def test_integer_seconds(self):
        self.assertEqual(shared._retry_after_seconds(_FakeHTTPError("5")), 5.0)

    def test_capped_at_60(self):
        self.assertEqual(shared._retry_after_seconds(_FakeHTTPError("120")), 60.0)

    def test_no_header_returns_none(self):
        self.assertIsNone(shared._retry_after_seconds(_FakeHTTPError(None)))

    def test_no_response_returns_none(self):
        self.assertIsNone(shared._retry_after_seconds(_FakeHTTPError(has_response=False)))

    def test_plain_exception_returns_none(self):
        self.assertIsNone(shared._retry_after_seconds(ValueError("boom")))

    def test_http_date_form_not_honored(self):
        # The HTTP-date form is not parsed → falls back to backoff (None here).
        self.assertIsNone(shared._retry_after_seconds(_FakeHTTPError("Wed, 21 Oct 2015 07:28:00 GMT")))


class WithRetriesTest(unittest.TestCase):
    def test_success_first_try_no_sleep(self):
        with mock.patch.object(shared.time, "sleep") as slept:
            self.assertEqual(shared._with_retries(lambda: 42), 42)
            slept.assert_not_called()

    def test_retry_after_delay_used(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise _FakeHTTPError("5")
            return "ok"

        with mock.patch.object(shared.time, "sleep") as slept:
            self.assertEqual(shared._with_retries(flaky), "ok")
            slept.assert_called_once_with(5.0)   # Retry-After honored, no jitter

    def test_plain_exception_uses_backoff_not_retry_after(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise ValueError("transient")
            return "ok"

        with mock.patch.object(shared.time, "sleep") as slept:
            self.assertEqual(shared._with_retries(flaky), "ok")
            slept.assert_called_once()
            # exponential backoff: base_delay*2^0 + jitter ∈ [2.0, 2.5)
            (delay,), _ = slept.call_args
            self.assertGreaterEqual(delay, 2.0)
            self.assertLess(delay, 2.5)

    def test_exhaustion_reraises(self):
        def always():
            raise _FakeHTTPError("1")

        with mock.patch.object(shared.time, "sleep") as slept:
            with self.assertRaises(_FakeHTTPError):
                shared._with_retries(always, retries=3)
            self.assertEqual(slept.call_count, 2)  # retries-1 sleeps before the final raise


# ── P7.1: _parse_designations / _parse_designations_from_ids ─────────────────

class _FakeResult:
    """Minimal stand-in for the astroquery SIMBAD result table: carries `.colnames`
    and `result["main_id"][0]`, the only surface `_parse_designations` touches."""
    def __init__(self, main_id=None):
        if main_id is None:
            self.colnames = []
            self._data = {}
        else:
            self.colnames = ["main_id"]
            self._data = {"main_id": [main_id]}

    def __getitem__(self, key):
        return self._data[key]


def _ids(*id_strings):
    """Build an ids_result iterable of {'id': ...} rows, like Simbad.query_objectids()."""
    return [{"id": s} for s in id_strings]


class ParseDesignationsTest(unittest.TestCase):
    """_parse_designations(result, ids_result) — the table-driven SIMBAD parser."""

    def test_main_id_and_common_catalogs(self):
        d = shared._parse_designations(
            _FakeResult("* tau Cet"),
            _ids("HD 10700", "HIP 8102", "GJ 71", "* tau Cet"),
        )
        self.assertEqual(d["MAIN_ID"], "* tau Cet")
        self.assertEqual(d["HD"], "HD 10700")
        self.assertEqual(d["HIP"], "HIP 8102")
        self.assertEqual(d["GJ"], "GJ 71")

    def test_gaia_dr3_maps_into_edr3_slot(self):
        # SIMBAD now emits "Gaia DR3 <id>"; DR3 ≡ EDR3 source_ids → the EDR3 slot.
        d = shared._parse_designations(_FakeResult("x"), _ids("Gaia DR3 5853498713190525696"))
        self.assertEqual(d["Gaia EDR3"], "Gaia DR3 5853498713190525696")

    def test_gaia_edr3_prefix_still_captured(self):
        d = shared._parse_designations(_FakeResult("x"), _ids("Gaia EDR3 12345"))
        self.assertEqual(d["Gaia EDR3"], "Gaia EDR3 12345")

    def test_gaia_dr2_not_captured(self):
        # DR2 source_ids differ from EDR3/DR3 and must be excluded.
        d = shared._parse_designations(_FakeResult("x"), _ids("Gaia DR2 999"))
        self.assertIsNone(d["Gaia EDR3"])

    def test_first_prefix_wins_per_key(self):
        # Only the first matching id per key is kept.
        d = shared._parse_designations(_FakeResult("x"), _ids("HD 111", "HD 222"))
        self.assertEqual(d["HD"], "HD 111")

    def test_none_ids_result_returns_main_id_only(self):
        d = shared._parse_designations(_FakeResult("* alf Cen"), None)
        self.assertEqual(d["MAIN_ID"], "* alf Cen")
        self.assertIsNone(d["HD"])

    def test_result_without_main_id_column(self):
        d = shared._parse_designations(_FakeResult(None), _ids("HD 1"))
        self.assertIsNone(d["MAIN_ID"])
        self.assertEqual(d["HD"], "HD 1")


class ParseDesignationsFromIdsTest(unittest.TestCase):
    """_parse_designations_from_ids(ids_string, keys=None) — the pipe-string parser."""

    def test_empty_string(self):
        self.assertEqual(shared._parse_designations_from_ids(""), "")
        self.assertEqual(shared._parse_designations_from_ids(None), "")

    def test_ordering_follows_key_list(self):
        # Output order follows _CSV_DESIG_KEYS (NAME, GJ, HD, HIP, …), not input order.
        out = shared._parse_designations_from_ids("HIP 8102|GJ 71|HD 10700")
        self.assertEqual(out, "GJ 71, HD 10700, HIP 8102")

    def test_gaia_dr3_into_edr3_slot(self):
        out = shared._parse_designations_from_ids("Gaia DR3 42")
        self.assertEqual(out, "Gaia DR3 42")

    def test_gaia_dr2_excluded(self):
        self.assertEqual(shared._parse_designations_from_ids("Gaia DR2 42"), "")

    def test_custom_keys_subset(self):
        # databases passes its own NAME-less key set; the `key in desig` guard means
        # a prefix naming a key the caller omits is simply skipped.
        out = shared._parse_designations_from_ids("NAME Foo|HD 10700", keys=["HD"])
        self.assertEqual(out, "HD 10700")


# ── P7.1: _parse_spectral_class ──────────────────────────────────────────────

class ParseSpectralClassTest(unittest.TestCase):

    def test_basic_types(self):
        self.assertEqual(shared._parse_spectral_class("G2V"), ("G", 2.0))
        self.assertEqual(shared._parse_spectral_class("A1V"), ("A", 1.0))
        self.assertEqual(shared._parse_spectral_class("K0III"), ("K", 0.0))

    def test_fractional_subtype(self):
        self.assertEqual(shared._parse_spectral_class("M5.5Ve"), ("M", 5.5))
        self.assertEqual(shared._parse_spectral_class("G8.5V"), ("G", 8.5))

    def test_subdwarf_prefix_skipped(self):
        # `search` skips the lowercase 'sd' prefix and finds the real class.
        self.assertEqual(shared._parse_spectral_class("sdG5"), ("G", 5.0))

    def test_white_dwarf_rejected(self):
        # The negative lookbehind excludes an OBAFGKM letter preceded by an uppercase
        # letter, so DA/DZ white dwarfs yield no class.
        self.assertEqual(shared._parse_spectral_class("DA1.9"), (None, None))
        self.assertEqual(shared._parse_spectral_class("DZ"), (None, None))

    def test_empty_and_sentinels(self):
        for s in ("", "N/A", "None", None):
            self.assertEqual(shared._parse_spectral_class(s), (None, None))


# ── P7.1: _lookup_spectral_type (ceiling rule + cross-letter fallthrough) ─────

class LookupSpectralTypeTest(unittest.TestCase):
    """Reads the real propertiesOfMainSequenceStars.csv (classes present:
    A0/A2/A5/A7, F0/F2/F5/F7, G0/G2/G5/G8, M0/M2/M4/M6/M8, …). The save/restore
    guard clears shared._MAIN_SEQUENCE_DATA so a synthetic-seeding test elsewhere
    can't poison the CSV load here, and restores it afterward (P3.3 hygiene)."""

    def setUp(self):
        self._saved = save_main_sequence_cache()

    def tearDown(self):
        restore_main_sequence_cache(self._saved)

    def test_ceiling_rule_within_class(self):
        # smallest available subtype >= requested.
        self.assertEqual(shared._lookup_spectral_type("G1V")[1], "G2")
        self.assertEqual(shared._lookup_spectral_type("G6V")[1], "G8")
        self.assertEqual(shared._lookup_spectral_type("A4V")[1], "A5")

    def test_exact_subtype(self):
        self.assertEqual(shared._lookup_spectral_type("G0V")[1], "G0")

    def test_cross_letter_fallthrough(self):
        # F9 is cooler than the coolest F entry (F7) → next class's hottest = G0.
        self.assertEqual(shared._lookup_spectral_type("F9V")[1], "G0")

    def test_clamp_to_last_entry_of_final_class(self):
        # M9 exceeds the coolest M entry (M8) and there is no cooler letter → M8.
        self.assertEqual(shared._lookup_spectral_type("M9V")[1], "M8")

    def test_white_dwarf_returns_none(self):
        row, key = shared._lookup_spectral_type("DA1.9")
        self.assertIsNone(row)
        self.assertIsNone(key)

    def test_row_dict_carries_original_columns(self):
        row, key = shared._lookup_spectral_type("G2V")
        self.assertEqual(row["Spectral Class"].strip(), "G2")
        self.assertIn("Bolo. Corr. (BC)", row)


# ── P7.1: _network_error_msg classification matrix ───────────────────────────

class NetworkErrorMsgTest(unittest.TestCase):

    def test_requests_timeout(self):
        import requests
        msg = shared._network_error_msg(requests.exceptions.Timeout(), "NASA")
        self.assertEqual(msg, "NASA request timed out. Try again.")

    def test_requests_connection_error(self):
        import requests
        msg = shared._network_error_msg(requests.exceptions.ConnectionError(), "SIMBAD")
        self.assertEqual(msg, "Could not connect to SIMBAD. Check your network connection.")

    def test_urllib_urlerror_timeout(self):
        import urllib.error
        msg = shared._network_error_msg(urllib.error.URLError("connection timed out"), "GAVO")
        self.assertEqual(msg, "GAVO request timed out. Try again.")

    def test_urllib_urlerror_generic(self):
        import urllib.error
        msg = shared._network_error_msg(urllib.error.URLError("connection refused"), "GAVO")
        self.assertEqual(msg, "Could not connect to GAVO. Check your network connection.")

    def test_string_fallback_timeout(self):
        msg = shared._network_error_msg(RuntimeError("the socket timeout expired"), "Hypatia")
        self.assertEqual(msg, "Hypatia request timed out. Try again.")

    def test_string_fallback_connection(self):
        msg = shared._network_error_msg(RuntimeError("network is unreachable"), "Hypatia")
        self.assertEqual(msg, "Could not connect to Hypatia. Check your network connection.")

    def test_unclassified_returns_raw_str(self):
        msg = shared._network_error_msg(ValueError("something odd"), "NASA")
        self.assertEqual(msg, "something odd")


if __name__ == "__main__":
    unittest.main()
