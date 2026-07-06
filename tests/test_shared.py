# tests/test_shared.py — offline unit coverage for core/shared.py helpers.
#
# Phase 6 seeds this file with the P6.1 Retry-After coverage; Phase 7 (P7.1) expands
# it with the designation/spectral/error-classification helpers. Pure offline, no Qt.

import unittest
from unittest import mock

import core.shared as shared


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


if __name__ == "__main__":
    unittest.main()
