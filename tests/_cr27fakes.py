"""CR-27 offline SIMBAD fakes: a multi-row ``query_object`` table and the patch context that drives the REAL
``databases.compute_simbad_lookup`` body without a network (shared by ``test_cr27_simbad.py`` and the fixture capture).

``rows`` is a list of per-row dicts (``None`` = masked / empty cell). Per-object columns repeat on every row, as SIMBAD's
``mesfe_h`` LEFT JOIN multiplies only the measurement columns."""
from contextlib import ExitStack
from unittest import mock

from core import databases

BASE_COLS = ["main_id", "ra", "dec", "sp_type", "plx_value", "V", "mesfe_h.teff", "mesfe_h.fe_h", "otype"]
NO_V_COLS = [c for c in BASE_COLS if c != "V"]


class FakeRow:
    def __init__(self, values):
        self._values = values

    def __getitem__(self, col):
        v = self._values.get(col)
        return "" if v is None else v


class FakeTable:
    def __init__(self, colnames, rows):
        self.colnames = list(colnames)
        self._rows = [FakeRow({k: r.get(k) for k in self.colnames}) for r in rows]

    def __len__(self):
        return len(self._rows)

    def __getitem__(self, idx):
        return self._rows[idx]


class FakeIdRow:
    def __init__(self, id_str):
        self._id = id_str

    def __getitem__(self, key):
        if key == "id":
            return self._id
        raise KeyError(key)


class FakeSimbad:
    """``_make_simbad`` stand-in: answers by the requested field set (with ``V`` → the flux-joined query)."""

    def __init__(self, fields, script):
        self.fields = fields
        self.script = script

    def query_object(self, name, *a, **k):
        with_v = "V" in self.fields
        self.script["calls"].append("query_object" + ("" if with_v else "_noV"))
        out = self.script["with_v" if with_v else "no_v"]
        if isinstance(out, Exception):
            raise out
        return out


def patched_lookup(with_v_rows, no_v_rows=None, ids=("NAME X",), ids_raise=None, no_v_raise=None):
    """Context manager → ``script`` dict (``calls`` logs every SIMBAD call). ``with_v_rows`` / ``no_v_rows`` are row
    lists (``[]`` = SIMBAD answered zero rows)."""
    import astroquery.simbad as _aq
    script = {"calls": [],
              "with_v": FakeTable(BASE_COLS, with_v_rows),
              "no_v": (no_v_raise if no_v_raise is not None else FakeTable(NO_V_COLS, no_v_rows or []))}

    def _ids(*a, **k):
        script["calls"].append("query_objectids")
        if ids_raise is not None:
            raise ids_raise
        return [FakeIdRow(i) for i in ids]

    stack = ExitStack()
    stack.enter_context(mock.patch.object(databases, "_make_simbad",
                                          lambda *f, **k: FakeSimbad(f, script)))
    stack.enter_context(mock.patch.object(_aq.Simbad, "query_objectids", staticmethod(_ids)))
    stack.enter_context(mock.patch.object(databases, "_simbad_gcns_block", lambda d: None))
    stack.enter_context(mock.patch.object(databases, "_simbad_gould_block", lambda d: None))
    stack.enter_context(mock.patch("time.sleep", lambda *_a: None))       # no real retry backoff
    stack.script = script
    return stack


def row(main_id="* alf Lyr", ra=279.23, dec=38.78, sp="A0Va", plx=130.23, v=0.03, teff=None, feh=None, ot="dS*"):
    return {"main_id": main_id, "ra": ra, "dec": dec, "sp_type": sp, "plx_value": plx, "V": v,
            "mesfe_h.teff": teff, "mesfe_h.fe_h": feh, "otype": ot}


# The pre-change byte-identity cases (T1.2): every one resolves on the FIRST query and has a non-empty row 0 for each
# measurement field it carries, so its CR-27 output must equal the unchanged code's output (fixture).
PRECHANGE_CASES = {
    "single_row_full": [row(teff=9600.0, feh=-0.5)],
    "multi_row_row0_full": [row(teff=4450.0, feh=-0.2), row(teff=4100.0, feh=-0.4), row(teff=None, feh=0.1)],
    "no_v_row_kept": [row(main_id="* rho CrB", v=None, teff=5800.0, feh=-0.2)],
    "all_measurements_empty_single_row": [row(main_id="BL Cet", sp="M5.5V", v=None, teff=None, feh=None,
                                              ot="Er*")],
    "row0_full_later_rows_empty": [row(teff=3200.0, feh=0.05), row(teff=None, feh=None)],
}
