"""Leaves -> subassembly buckets, with the checks that make the answer usable.

Double counting is not solved by remembering to check for it.  It is solved by
making the bucket map a *partition* of the leaf occurrences: every leaf belongs
to exactly one bucket, and the code refuses to produce a total until that is
true.  The wheels then simply cannot be counted both inside the axle and again
inside the wheel group, because a leaf has one bucket or the run fails.

Three invariants are enforced before any total is written:

  1. every leaf is assigned to exactly one bucket
  2. the sum of the bucket masses equals CATIA's own mass for the whole
     assembly
  3. the CG recombined from the buckets equals CATIA's own CG

Numbers 2 and 3 are independent of our traversal, which is what makes them
worth having: they catch a missed transform, a skipped branch, a unit error.
"""

import re

from .envelope import CmcError
from . import geom

MASS_REL_TOL = 1e-6
CG_ABS_TOL_MM = 1e-3


def compile_patterns(bucket_map):
    """Compile bucket patterns, most specific first.

    `*`  matches within one path segment
    `**` matches across segments
    Specificity is the length of the literal prefix before the first wildcard,
    so /Vehicle/FrontAxle.1/Wheel_* beats /Vehicle/FrontAxle.1/**.
    """
    compiled = []
    for order, (bucket, patterns) in enumerate(bucket_map.items()):
        for pattern in patterns:
            compiled.append({
                "bucket": bucket,
                "pattern": pattern,
                "regex": re.compile(_to_regex(pattern)),
                # 1. a pattern that does not cross segments (no **) is more
                #    specific than one that swallows a whole subtree
                # 2. then: more literal characters
                # 3. then: earlier declaration in the map
                "specificity": (-pattern.count("**"), _literal_len(pattern), -order),
            })
    compiled.sort(key=lambda c: c["specificity"], reverse=True)
    return compiled


def _to_regex(pattern):
    out, i = ["^"], 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if pattern[i:i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    out.append("$")
    return "".join(out)


def _literal_len(pattern):
    return sum(1 for ch in pattern if ch not in "*?")


def assign(components, compiled):
    """Assign each leaf to exactly one bucket, and record where a leaf could
    have gone to more than one.

    Those conflicts are the double counting question in visible form: a wheel
    matching both the axle subtree and the wheel group is not an error, it is a
    decision, and the human reviewing the run should be able to see which way
    it went and why.
    """
    assigned, unmapped, conflicts = [], [], []
    for comp in components:
        matches = [e for e in compiled if e["regex"].match(comp["occurrence_path"])]
        if not matches:
            unmapped.append(comp["occurrence_path"])
            continue
        winner = matches[0]
        buckets = {e["bucket"] for e in matches}
        if len(buckets) > 1:
            conflicts.append({
                "path": comp["occurrence_path"],
                "winner": winner["bucket"],
                "winning_pattern": winner["pattern"],
                "also_matched": sorted(buckets - {winner["bucket"]}),
            })
        item = dict(comp)
        item["bucket"] = winner["bucket"]
        item["matched_pattern"] = winner["pattern"]
        assigned.append(item)
    return assigned, unmapped, conflicts


def check_duplicate_paths(components):
    seen, dupes = set(), []
    for comp in components:
        path = comp["occurrence_path"]
        if path in seen:
            dupes.append(path)
        seen.add(path)
    return dupes


def build(components, bucket_map, groups, root_totals):
    dupes = check_duplicate_paths(components)
    if dupes:
        raise CmcError(
            "E_DUPLICATE_PATH",
            f"{len(dupes)} occurrence yolu iki kez geçiyor, tarama bozuk.",
            "Aynı örnek adının iki kez üretildiği anlamına gelir; montajdaki "
            "yinelenen instance adlarını kontrol edin.",
            duplicates=dupes[:20],
        )

    compiled = compile_patterns(bucket_map)
    assigned, unmapped, conflicts = assign(components, compiled)
    if unmapped:
        raise CmcError(
            "E_UNMAPPED",
            f"{len(unmapped)} parça hiçbir alt yapıya atanmadı, toplam hesaplanamaz.",
            "subassembly_map.json dosyasına bu yollar için desen ekleyin. "
            "Bir parça atanmadan toplam kütle güvenilir değildir.",
            unmapped=unmapped[:20],
            unmapped_total=len(unmapped),
        )

    by_bucket = {}
    for item in assigned:
        by_bucket.setdefault(item["bucket"], []).append(item)

    buckets = []
    for name in bucket_map:
        items = by_bucket.get(name, [])
        buckets.append(_summarise(name, items))

    total_items = [
        (b["mass_kg"], tuple(b["cg_mm"]), b["inertia_tensor_cg"]) for b in buckets
    ]
    mass, cg, tensor, complete = geom.combine(total_items)
    totals = {
        "mass_kg": mass,
        "cg_mm": list(cg),
        "inertia_tensor_cg": tensor,
        "inertia_complete": complete,
        "leaf_count": len(assigned),
    }

    checks = _verify(totals, root_totals)

    group_rows = []
    for group_name, members in (groups or {}).items():
        missing = [m for m in members if m not in by_bucket and m not in bucket_map]
        if missing:
            raise CmcError(
                "E_BAD_GROUP",
                f"'{group_name}' grubu tanımsız alt yapı içeriyor: {', '.join(missing)}",
                "subassembly_map.json içindeki groups bölümünü düzeltin.",
            )
        member_rows = [b for b in buckets if b["name"] in members]
        g_items = [(b["mass_kg"], tuple(b["cg_mm"]), b["inertia_tensor_cg"]) for b in member_rows]
        g_mass, g_cg, g_tensor, g_complete = geom.combine(g_items)
        group_rows.append({
            "name": group_name,
            "members": members,
            "mass_kg": g_mass,
            "cg_mm": list(g_cg),
            "inertia_tensor_cg": g_tensor,
            "inertia_complete": g_complete,
        })

    warnings = _collect_warnings(assigned)
    return {
        "buckets": buckets,
        "groups": group_rows,
        "totals": totals,
        "checks": checks,
        "warnings": warnings,
        "bucket_conflicts": conflicts[:50],
        "bucket_conflict_count": len(conflicts),
    }


def _summarise(name, items):
    combined = geom.combine(
        [(i["mass_kg"], tuple(i["cg_mm"]), i["inertia_tensor_cg_root_axes"]) for i in items]
    )
    mass, cg, tensor, complete = combined
    return {
        "name": name,
        "mass_kg": mass,
        "cg_mm": list(cg),
        "inertia_tensor_cg": tensor if complete else None,
        "inertia_complete": complete,
        "leaf_count": len(items),
        "zero_mass_count": sum(1 for i in items if "zero_mass" in i["flags"]),
        "no_material_count": sum(1 for i in items if "no_material" in i["flags"]),
    }


def _verify(totals, root_totals):
    checks = {"mass": None, "cg": None, "source": "catia_root_analyze"}
    if not root_totals or not root_totals.get("mass_kg"):
        checks["mass"] = {"status": "skipped", "reason": "root_mass_unavailable"}
        checks["cg"] = {"status": "skipped", "reason": "root_cg_unavailable"}
        return checks

    root_mass = root_totals["mass_kg"]
    rel = abs(totals["mass_kg"] - root_mass) / root_mass
    checks["mass"] = {
        "status": "ok" if rel <= MASS_REL_TOL else "failed",
        "sum_of_buckets_kg": totals["mass_kg"],
        "catia_root_kg": root_mass,
        "relative_error": rel,
        "tolerance": MASS_REL_TOL,
    }
    if rel > MASS_REL_TOL:
        raise CmcError(
            "E_INVARIANT_MASS",
            "Alt yapı toplamı CATIA'nın montaj kütlesiyle uyuşmuyor.",
            "Bir dal taranmamış veya bir parça iki kez sayılmış olabilir. "
            "Bu hata giderilmeden hiçbir çıktı kullanılamaz.",
            sum_of_buckets_kg=totals["mass_kg"],
            catia_root_kg=root_mass,
            difference_kg=totals["mass_kg"] - root_mass,
        )

    if root_totals.get("cg_mm"):
        errs = [abs(a - b) for a, b in zip(totals["cg_mm"], root_totals["cg_mm"])]
        worst = max(errs)
        checks["cg"] = {
            "status": "ok" if worst <= CG_ABS_TOL_MM else "failed",
            "recombined_cg_mm": totals["cg_mm"],
            "catia_root_cg_mm": root_totals["cg_mm"],
            "max_abs_error_mm": worst,
            "tolerance_mm": CG_ABS_TOL_MM,
        }
        if worst > CG_ABS_TOL_MM:
            raise CmcError(
                "E_INVARIANT_CG",
                "Alt yapılardan hesaplanan CG, CATIA'nın montaj CG'siyle uyuşmuyor.",
                "Genellikle occurrence dönüşüm zincirinin eksik uygulandığını "
                "gösterir. Çıktı kullanılmamalı.",
                recombined_cg_mm=totals["cg_mm"],
                catia_root_cg_mm=root_totals["cg_mm"],
                max_abs_error_mm=worst,
            )
    else:
        checks["cg"] = {"status": "skipped", "reason": "root_cg_unavailable"}
    return checks


def _collect_warnings(assigned):
    out = []
    for item in assigned:
        if "zero_mass" in item["flags"] or "no_mass_value" in item["flags"]:
            out.append({
                "kind": "zero_mass",
                "path": item["occurrence_path"],
                "bucket": item["bucket"],
                "message_tr": f"{item['bucket']}: {item['instance_name']} sıfır kütle raporluyor.",
            })
        elif "no_material" in item["flags"] or "no_density" in item["flags"]:
            out.append({
                "kind": "no_material",
                "path": item["occurrence_path"],
                "bucket": item["bucket"],
                "message_tr": f"{item['bucket']}: {item['instance_name']} malzeme/yoğunluk tanımsız.",
            })
    out.sort(key=lambda w: (w["kind"] != "zero_mass", w["path"]))
    return out
