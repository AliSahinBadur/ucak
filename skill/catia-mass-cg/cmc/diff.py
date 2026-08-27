"""Compare a run against the previous revision of the same vehicle+variant.

The useful output is not "the mass changed", it is "the rear axle gained
12.4 kg and here are the three parts that appeared".  Bucket deltas answer the
first question, component path deltas answer the second.
"""

from . import store

MASS_THRESHOLD_KG = 0.5
CG_THRESHOLD_MM = 5.0


def compare(run_id, vehicle, variant, mass_threshold=MASS_THRESHOLD_KG,
            cg_threshold=CG_THRESHOLD_MM):
    previous = store.previous_run(vehicle, variant, run_id)
    if not previous:
        return {"has_previous": False, "message_tr": "Karşılaştırılacak önceki revizyon yok."}

    current = store.get_measurement(run_id)
    cur_buckets = {b["name"]: b for b in store.buckets_of(run_id)}
    prev_buckets = {b["name"]: b for b in store.buckets_of(previous["run_id"])}

    rows, significant = [], 0
    for name in sorted(set(cur_buckets) | set(prev_buckets)):
        cur, prev = cur_buckets.get(name), prev_buckets.get(name)
        if cur and not prev:
            rows.append({"bucket": name, "change": "added", "mass_kg": cur["mass_kg"]})
            significant += 1
            continue
        if prev and not cur:
            rows.append({"bucket": name, "change": "removed", "mass_kg": prev["mass_kg"]})
            significant += 1
            continue

        d_mass = cur["mass_kg"] - prev["mass_kg"]
        d_cg = [cur["cg_x_mm"] - prev["cg_x_mm"],
                cur["cg_y_mm"] - prev["cg_y_mm"],
                cur["cg_z_mm"] - prev["cg_z_mm"]]
        flagged = abs(d_mass) > mass_threshold or max(abs(v) for v in d_cg) > cg_threshold
        if flagged:
            significant += 1
        rows.append({
            "bucket": name,
            "change": "significant" if flagged else "unchanged",
            "mass_kg": cur["mass_kg"],
            "previous_mass_kg": prev["mass_kg"],
            "delta_mass_kg": d_mass,
            "delta_cg_mm": d_cg,
        })

    cur_paths = store.component_paths(run_id)
    prev_paths = store.component_paths(previous["run_id"])
    added = sorted(set(cur_paths) - set(prev_paths))
    removed = sorted(set(prev_paths) - set(cur_paths))

    return {
        "has_previous": True,
        "previous": {
            "run_id": previous["run_id"],
            "revision": previous["revision"],
            "measured_at": previous["measured_at"],
            "total_mass_kg": previous["total_mass_kg"],
            "cg_mm": [previous["cg_x_mm"], previous["cg_y_mm"], previous["cg_z_mm"]],
        },
        "current": {
            "run_id": run_id,
            "revision": current["revision"],
            "total_mass_kg": current["total_mass_kg"],
            "cg_mm": [current["cg_x_mm"], current["cg_y_mm"], current["cg_z_mm"]],
        },
        "delta_total_mass_kg": current["total_mass_kg"] - previous["total_mass_kg"],
        "delta_total_cg_mm": [
            current["cg_x_mm"] - previous["cg_x_mm"],
            current["cg_y_mm"] - previous["cg_y_mm"],
            current["cg_z_mm"] - previous["cg_z_mm"],
        ],
        "buckets": rows,
        "significant_bucket_count": significant,
        "added_components": added[:50],
        "added_component_count": len(added),
        "removed_components": removed[:50],
        "removed_component_count": len(removed),
        "thresholds": {"mass_kg": mass_threshold, "cg_mm": cg_threshold},
    }
