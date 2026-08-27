"""Revision memory.

One SQLite file, no server, diff-able by date, copyable to a network share.
The point of storing components as well as buckets is traceability: six months
later somebody will ask why the rear axle gained 12 kg, and the answer has to
be a part name, not a shrug.

Inertia is stored on every run even when the current Adams flow only consumes
mass and CG.  Re-measuring an old revision is usually impossible because the
CATProduct has moved on.
"""

import json
import sqlite3

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS measurement (
    run_id           TEXT PRIMARY KEY,
    vehicle          TEXT NOT NULL,
    variant          TEXT NOT NULL,
    revision         TEXT NOT NULL,
    source           TEXT NOT NULL,
    source_document  TEXT,
    source_sha256    TEXT,
    catia_version    TEXT,
    work_mode        TEXT,
    units_profile    TEXT,
    measured_by      TEXT,
    measured_at      TEXT,
    total_mass_kg    REAL,
    cg_x_mm          REAL,
    cg_y_mm          REAL,
    cg_z_mm          REAL,
    inertia_complete INTEGER,
    leaf_count       INTEGER,
    warning_count    INTEGER
);

CREATE TABLE IF NOT EXISTS bucket (
    run_id   TEXT NOT NULL,
    name     TEXT NOT NULL,
    mass_kg  REAL, cg_x_mm REAL, cg_y_mm REAL, cg_z_mm REAL,
    ixx REAL, iyy REAL, izz REAL, ixy REAL, ixz REAL, iyz REAL,
    inertia_complete INTEGER,
    leaf_count INTEGER,
    PRIMARY KEY (run_id, name)
);

CREATE TABLE IF NOT EXISTS component (
    run_id          TEXT NOT NULL,
    occurrence_path TEXT NOT NULL,
    instance_name   TEXT,
    part_number     TEXT,
    bucket          TEXT,
    mass_kg         REAL,
    cg_x_mm REAL, cg_y_mm REAL, cg_z_mm REAL,
    ixx REAL, iyy REAL, izz REAL, ixy REAL, ixz REAL, iyz REAL,
    material        TEXT,
    density_kg_m3   REAL,
    flags           TEXT,
    PRIMARY KEY (run_id, occurrence_path)
);

CREATE INDEX IF NOT EXISTS idx_measurement_key
    ON measurement (vehicle, variant, measured_at);
"""


def connect():
    path = config.home() / "memory.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _tensor_cols(tensor):
    if not tensor:
        return (None,) * 6
    return (tensor["ixx"], tensor["iyy"], tensor["izz"],
            tensor["ixy"], tensor["ixz"], tensor["iyz"])


def save(meta, rolled, components):
    conn = connect()
    with conn:
        conn.execute("DELETE FROM measurement WHERE run_id = ?", (meta["run_id"],))
        conn.execute("DELETE FROM bucket WHERE run_id = ?", (meta["run_id"],))
        conn.execute("DELETE FROM component WHERE run_id = ?", (meta["run_id"],))

        totals = rolled["totals"]
        conn.execute(
            """INSERT INTO measurement VALUES
               (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                meta["run_id"], meta["vehicle"], meta["variant"], meta["revision"],
                meta.get("source", "catia"), meta.get("source_document"),
                meta.get("source_sha256"), json.dumps(meta.get("catia_version"), ensure_ascii=False),
                json.dumps(meta.get("work_mode"), ensure_ascii=False),
                json.dumps(meta.get("units_profile"), ensure_ascii=False),
                meta.get("measured_by"), meta.get("measured_at"),
                totals["mass_kg"], totals["cg_mm"][0], totals["cg_mm"][1], totals["cg_mm"][2],
                1 if totals["inertia_complete"] else 0,
                totals["leaf_count"], len(rolled["warnings"]),
            ),
        )

        for b in rolled["buckets"]:
            conn.execute(
                "INSERT INTO bucket VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (meta["run_id"], b["name"], b["mass_kg"],
                 b["cg_mm"][0], b["cg_mm"][1], b["cg_mm"][2],
                 *_tensor_cols(b["inertia_tensor_cg"]),
                 1 if b["inertia_complete"] else 0, b["leaf_count"]),
            )

        for c in components:
            conn.execute(
                "INSERT INTO component VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (meta["run_id"], c["occurrence_path"], c.get("instance_name"),
                 c.get("part_number"), c.get("bucket"), c["mass_kg"],
                 c["cg_mm"][0], c["cg_mm"][1], c["cg_mm"][2],
                 *_tensor_cols(c.get("inertia_tensor_cg_root_axes")),
                 c.get("material"), c.get("density_kg_m3"),
                 ",".join(c.get("flags", []))),
            )
    conn.close()


def get_measurement(run_id):
    conn = connect()
    row = conn.execute("SELECT * FROM measurement WHERE run_id = ?", (run_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def buckets_of(run_id):
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM bucket WHERE run_id = ? ORDER BY name", (run_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def component_paths(run_id):
    conn = connect()
    rows = conn.execute(
        "SELECT occurrence_path, mass_kg FROM component WHERE run_id = ?", (run_id,)
    ).fetchall()
    conn.close()
    return {r["occurrence_path"]: r["mass_kg"] for r in rows}


def previous_run(vehicle, variant, exclude_run_id):
    """Most recent earlier measurement of the same vehicle and variant."""
    conn = connect()
    row = conn.execute(
        """SELECT * FROM measurement
           WHERE vehicle = ? AND variant = ? AND run_id != ?
           ORDER BY measured_at DESC LIMIT 1""",
        (vehicle, variant, exclude_run_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def history(vehicle=None, variant=None, limit=20):
    conn = connect()
    sql = "SELECT * FROM measurement"
    params, where = [], []
    if vehicle:
        where.append("vehicle = ?")
        params.append(vehicle)
    if variant:
        where.append("variant = ?")
        params.append(variant)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY measured_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
