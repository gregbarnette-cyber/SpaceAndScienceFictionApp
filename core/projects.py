# core/projects.py — Phase S: project workspaces (campaign / novel manager).
#
# A "project" is a named, curated set of star systems — real ones (looked up via
# SIMBAD) and procedurally-generated ones (Phase R) — each with a freeform note,
# exported as one multi-system dossier. This module is the pure, self-validating
# CRUD layer over two additive tables (core/db.py: projects, project_members); no
# Qt, no network. Mutations live here (GUI-only at the surface); query.py exposes
# only the read-only list/get readers.
#
# A GENERATED member stores its generate_system PARAMS (generated_spec JSON), not a
# frozen body — so it re-creates byte-identically on reopen/export (the R1/R2/R3
# determinism contract). generated_seed is a denormalised display convenience.
# See completed_plans/PHASE_S_PLAN.md and docs/research-priors-contract.md's sibling, the Phase S
# section of docs/gui-architecture.md.

import datetime
import json

from core.db import get_conn

_SOURCES = {"looked_up", "generated"}


def _err(msg):
    return {"error": msg}


def _today():
    return datetime.date.today().isoformat()


def _project_row(conn, name):
    return conn.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()


def create_project(name, description=""):
    """Create a new named project. Blank or duplicate name → curated error."""
    name = (name or "").strip()
    if not name:
        return _err("Project name must not be blank.")
    conn = get_conn()
    if _project_row(conn, name):
        return _err(f"A project named {name!r} already exists.")
    created = _today()
    cur = conn.execute(
        "INSERT INTO projects (name, description, created_date) VALUES (?, ?, ?)",
        (name, description or "", created))
    conn.commit()
    return {"project_id": cur.lastrowid, "name": name,
            "description": description or "", "created_date": created, "member_count": 0}


def list_projects():
    """All projects (with member counts), sorted by name (case-insensitive)."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT p.project_id, p.name, p.description, p.created_date,
               (SELECT COUNT(*) FROM project_members m WHERE m.project_id = p.project_id)
                   AS member_count
        FROM projects p
        ORDER BY p.name COLLATE NOCASE
    """).fetchall()
    return [dict(r) for r in rows]


def get_project(name):
    """A project + its members (generated_spec echoed parsed). Unknown → error."""
    conn = get_conn()
    p = _project_row(conn, (name or "").strip())
    if not p:
        return _err(f"No project named {name!r}.")
    members = conn.execute("""
        SELECT star_name, note, source, generated_seed, generated_spec, added_date
        FROM project_members WHERE project_id = ?
        ORDER BY added_date, star_name
    """, (p["project_id"],)).fetchall()
    out = []
    for m in members:
        d = dict(m)
        if d.get("generated_spec"):
            try:
                d["generated_spec"] = json.loads(d["generated_spec"])
            except (TypeError, ValueError):
                pass   # leave the raw string if it somehow isn't JSON
        out.append(d)
    return {"project": dict(p), "members": out}


def add_member(name, star_name, note="", source="looked_up", seed=None, spec=None):
    """Add (or idempotently update) a member of a project.

    Re-adding the SAME logical member (same star_name + source, and for generated
    the same seed) updates its note/spec in place. A DIFFERENT member colliding on
    star_name (e.g. a second generated 'Gen-88' with a different seed) gets a
    ``" (N)"`` suffix (D2). The final star_name is returned.
    """
    star_name = (star_name or "").strip()
    if not star_name:
        return _err("Star name must not be blank.")
    if source not in _SOURCES:
        return _err(f"source must be one of {sorted(_SOURCES)}.")
    conn = get_conn()
    p = _project_row(conn, (name or "").strip())
    if not p:
        return _err(f"No project named {name!r}.")
    pid = p["project_id"]

    rows = conn.execute(
        "SELECT star_name, source, generated_seed FROM project_members WHERE project_id = ?",
        (pid,)).fetchall()
    by_name = {r["star_name"]: r for r in rows}

    final = star_name
    if star_name in by_name:
        ex = by_name[star_name]
        same_logical = (ex["source"] == source
                        and (source != "generated" or ex["generated_seed"] == seed))
        if not same_logical:
            n = 2
            while f"{star_name} ({n})" in by_name:
                n += 1
            final = f"{star_name} ({n})"

    conn.execute("""
        INSERT OR REPLACE INTO project_members
            (project_id, star_name, note, source, generated_seed, generated_spec, added_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (pid, final, note or "", source, seed,
          json.dumps(spec) if spec is not None else None, _today()))
    conn.commit()
    return {"name": p["name"], "star_name": final, "source": source,
            "generated_seed": seed}


def update_note(name, star_name, note):
    """Set a member's note. Unknown project/member → curated error."""
    conn = get_conn()
    p = _project_row(conn, (name or "").strip())
    if not p:
        return _err(f"No project named {name!r}.")
    cur = conn.execute(
        "UPDATE project_members SET note = ? WHERE project_id = ? AND star_name = ?",
        (note or "", p["project_id"], (star_name or "").strip()))
    conn.commit()
    if cur.rowcount == 0:
        return _err(f"{star_name!r} is not a member of {name!r}.")
    return {"name": p["name"], "star_name": star_name, "note": note or ""}


def remove_member(name, star_name):
    """Remove a member (idempotent — absent member is a no-op). Unknown project → error."""
    conn = get_conn()
    p = _project_row(conn, (name or "").strip())
    if not p:
        return _err(f"No project named {name!r}.")
    cur = conn.execute(
        "DELETE FROM project_members WHERE project_id = ? AND star_name = ?",
        (p["project_id"], (star_name or "").strip()))
    conn.commit()
    return {"name": p["name"], "star_name": star_name, "removed": cur.rowcount > 0}


def rename_project(old, new):
    """Rename a project. Blank/duplicate new name or unknown old → curated error."""
    new = (new or "").strip()
    if not new:
        return _err("New project name must not be blank.")
    conn = get_conn()
    p = _project_row(conn, (old or "").strip())
    if not p:
        return _err(f"No project named {old!r}.")
    if new != p["name"] and _project_row(conn, new):
        return _err(f"A project named {new!r} already exists.")
    conn.execute("UPDATE projects SET name = ? WHERE project_id = ?", (new, p["project_id"]))
    conn.commit()
    return {"project_id": p["project_id"], "name": new}


def delete_project(name):
    """Delete a project and cascade its members (one transaction). Unknown → error."""
    conn = get_conn()
    p = _project_row(conn, (name or "").strip())
    if not p:
        return _err(f"No project named {name!r}.")
    pid = p["project_id"]
    try:
        conn.execute("DELETE FROM project_members WHERE project_id = ?", (pid,))
        conn.execute("DELETE FROM projects WHERE project_id = ?", (pid,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"name": p["name"], "deleted": True}
