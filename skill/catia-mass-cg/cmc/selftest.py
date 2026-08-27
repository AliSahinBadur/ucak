"""Checks the maths against answers you can work out on paper.

These are not unit tests for their own sake.  Every one of them corresponds to
a way the pipeline could be silently wrong: a dropped transform, a flipped
inertia sign, a units factor solved in the wrong direction.  Run this after
any change, and on any new machine before trusting a number.
"""

from . import fake_source, geom, units, walk


def run():
    results = []
    for func in (
        _steiner_round_trip,
        _rotation_of_a_diagonal_tensor,
        _two_point_masses,
        _transform_chain,
        _mirror_is_not_a_rotation,
        _calibration_recovers_known_scales,
        _walk_reproduces_box_inertia,
        _fake_vehicle_invariants,
    ):
        try:
            detail = func()
            results.append({"name": func.__name__.lstrip("_"), "passed": True, "detail": detail})
        except AssertionError as exc:
            results.append({"name": func.__name__.lstrip("_"), "passed": False, "detail": str(exc)})
    return results


def _close(a, b, tol=1e-6, label=""):
    if abs(a - b) > tol:
        raise AssertionError(f"{label}: {a} != {b} (tol {tol})")


def _steiner_round_trip():
    td = {"ixx": 12.0, "iyy": 15.0, "izz": 18.0, "ixy": 1.0, "ixz": -2.0, "iyz": 0.5}
    m, r = 3.0, (10.0, -4.0, 7.0)
    back = geom.shift_to_cg(geom.shift_from_cg(td, m, r), m, r)
    for key in geom.TENSOR_KEYS:
        _close(back[key], td[key], 1e-9, f"steiner {key}")
    return "shift out and back is identity"


def _rotation_of_a_diagonal_tensor():
    td = {"ixx": 1.0, "iyy": 2.0, "izz": 3.0, "ixy": 0.0, "ixz": 0.0, "iyz": 0.0}
    rz90 = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    out = geom.rotate_tensor(td, rz90)
    _close(out["ixx"], 2.0, 1e-12, "ixx after z90")
    _close(out["iyy"], 1.0, 1e-12, "iyy after z90")
    _close(out["izz"], 3.0, 1e-12, "izz unchanged")
    return "90 deg about z swaps ixx and iyy"


def _two_point_masses():
    zero = geom.zero_tensor_dict()
    m, d = 2.0, 500.0
    mass, cg, tensor, complete = geom.combine([
        (m, (d, 0.0, 0.0), dict(zero)),
        (m, (-d, 0.0, 0.0), dict(zero)),
    ])
    _close(mass, 2 * m, 1e-12, "total mass")
    _close(cg[0], 0.0, 1e-12, "cg x")
    _close(tensor["izz"], 2 * m * d * d, 1e-9, "izz of a dumbbell")
    _close(tensor["ixx"], 0.0, 1e-9, "ixx about the axis")
    if not complete:
        raise AssertionError("combine reported incomplete inertia for full data")
    return "dumbbell izz = 2 m d^2"


def _transform_chain():
    rz90 = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    R1, T1 = rz90, (100.0, 0.0, 0.0)
    R2, T2 = geom.IDENTITY, (0.0, 50.0, 0.0)
    R, T = geom.compose(R1, T1, R2, T2)
    got = geom.apply(R, T, (10.0, 0.0, 0.0))
    # child point (10,0,0) -> +T2 -> (10,50,0) -> rotate z90 -> (-50,10,0) -> +T1
    for got_v, want_v, axis in zip(got, (50.0, 10.0, 0.0), "xyz"):
        _close(got_v, want_v, 1e-12, f"chained {axis}")
    return "compose then apply matches hand calculation"


def _mirror_is_not_a_rotation():
    mirror = ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    if geom.is_rotation(mirror):
        raise AssertionError("a mirror matrix was accepted as a rotation")
    if not geom.is_rotation(geom.IDENTITY):
        raise AssertionError("identity was rejected as a rotation")
    return "det = -1 is rejected"


def _calibration_recovers_known_scales():
    api = fake_source.FakeApi()
    block = fake_source.calibration_block(100.0, 200.0, 300.0, 7850.0)
    raw = api.analyze(block)
    expected = units.expected_block(100.0, 200.0, 300.0, 7850.0)
    profile, evidence = units.solve(raw, expected)

    _close(profile["mass_to_kg"], 1.0, 1e-12, "mass scale")
    _close(profile["length_to_mm"], 1.0, 1e-12, "length scale")
    _close(profile["volume_to_mm3"], 1e9, 1.0, "volume scale")
    _close(profile["inertia_to_kg_mm2"], 1e6, 1.0, "inertia scale")
    if profile["inertia_ref"] != "origin":
        raise AssertionError(f"inertia reference solved as {profile['inertia_ref']}, expected origin")
    if profile["inertia_product_sign"] != 1:
        raise AssertionError(f"product sign solved as {profile['inertia_product_sign']}, expected +1")
    return "solver recovers the fake source's mixed units exactly"


def _walk_reproduces_box_inertia():
    api = fake_source.FakeApi()
    l, w, h, rho = 100.0, 200.0, 300.0, 7850.0
    block = fake_source.calibration_block(l, w, h, rho)
    expected = units.expected_block(l, w, h, rho)
    profile, _ = units.solve(api.analyze(block), expected)

    leaves = list(walk.iter_leaves(api, block, profile))
    if len(leaves) != 1:
        raise AssertionError(f"expected one leaf, got {len(leaves)}")
    leaf = leaves[0]
    _close(leaf["mass_kg"], expected["mass_kg"], 1e-9, "leaf mass")
    for got_v, want_v, axis in zip(leaf["cg_mm"], expected["cg_mm"], "xyz"):
        _close(got_v, want_v, 1e-9, f"leaf cg {axis}")

    tensor = leaf["inertia_tensor_cg_root_axes"]
    if tensor is None:
        raise AssertionError("no inertia produced for the calibration block")
    for key, want in zip(("ixx", "iyy", "izz"), expected["diag_cg"]):
        _close(tensor[key], want, abs(want) * 1e-9 + 1e-9, f"leaf {key} about cg")
    for key in ("ixy", "ixz", "iyz"):
        _close(tensor[key], 0.0, 1e-6, f"leaf {key} should vanish for an axis aligned box")
    return "leaf inertia equals the textbook box formula about the CG"


def _fake_vehicle_invariants():
    from . import rollup as rollup_mod

    api = fake_source.FakeApi()
    profile = {
        "mass_to_kg": 1.0, "length_to_mm": 1.0, "volume_to_mm3": 1e9,
        "inertia_to_kg_mm2": 1e6, "inertia_ref": "origin", "inertia_product_sign": 1,
    }
    root = fake_source.vehicle()
    leaves = list(walk.iter_leaves(api, root, profile))
    totals = walk.root_totals(api, root, profile)

    buckets = {
        "Tekerlek Grubu": ["/Vehicle/*/Wheel_*"],
        "Ön Aks": ["/Vehicle/FrontAxle.1/**"],
        "Arka Aks": ["/Vehicle/RearAxle.1/**"],
        "Ön Süspansiyon": ["/Vehicle/FrontSuspension.1/**"],
        "Arka Süspansiyon": ["/Vehicle/RearSuspension.1/**"],
        "Direksiyon Kolon": ["/Vehicle/SteeringColumn.1/**"],
        "Direksiyon Bağlantı": ["/Vehicle/SteeringLinkage.1/**"],
        "Şase": ["/Vehicle/Chassis.1/**"],
    }
    rolled = rollup_mod.build(leaves, buckets, None, totals)

    _close(rolled["totals"]["mass_kg"], 2046.402, 1e-6, "fake vehicle total mass")
    wheels = next(b for b in rolled["buckets"] if b["name"] == "Tekerlek Grubu")
    _close(wheels["mass_kg"], 248.0, 1e-9, "wheel group mass")
    if wheels["leaf_count"] != 4:
        raise AssertionError(f"wheel group holds {wheels['leaf_count']} leaves, expected 4")
    front = next(b for b in rolled["buckets"] if b["name"] == "Ön Aks")
    _close(front["mass_kg"], 210.0, 1e-9, "front axle excludes its wheels")
    return "wheels land in exactly one bucket and the mass invariant holds"
