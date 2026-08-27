"""Units profile: measured, never assumed.

CATIA V5 automation is not unit-consistent in a way you can memorise.  Some
Analyze members follow the MKS internal representation, others follow the
session units, and which is which has moved between releases.  Guessing here
produces an answer that is wrong by a factor of 1000 and looks perfectly
plausible on a spreadsheet.

So cmc measures a part whose answer is known by hand and solves for the
scales.  The same run also settles two things the API documentation does not:
whether GetInertia reports the tensor about the part origin or about its
centre of gravity, and whether the off-diagonal terms carry the product
integral sign or the tensor sign.

Calibration artefact (build once, keep in the project folder):

    A rectangular block L x W x H mm, edges along x/y/z, with ONE CORNER AT
    THE PART ORIGIN, single uniform material of known density.

The corner-at-origin placement matters: it puts the CG away from the origin,
which is what makes the origin-vs-CG question answerable at all.
"""

from .envelope import CmcError

#: Identity profile, used to read a session before it has been calibrated.
RAW_UNITS = {
    "mass_to_kg": 1.0,
    "length_to_mm": 1.0,
    "volume_to_mm3": 1.0,
    "inertia_to_kg_mm2": 1.0,
    "inertia_ref": None,
    "inertia_product_sign": None,
}

SCALE_CANDIDATES = (1e-9, 1e-6, 1e-3, 1e-2, 1e-1, 1.0, 1e1, 1e2, 1e3, 1e6, 1e9, 1e12)
SNAP_TOLERANCE = 0.01      # 1 % from a clean power of ten
CONSISTENCY_TOLERANCE = 0.02


def load(profile):
    """Validate a stored profile before anything depends on it."""
    if not profile:
        raise CmcError(
            "E_NO_PROFILE",
            "Bu makinede birim kalibrasyonu yapılmamış.",
            "Kalibrasyon parçasını CATIA'da açın ve `cmc calibrate` çalıştırın.",
        )
    for key in ("mass_to_kg", "length_to_mm", "volume_to_mm3", "inertia_to_kg_mm2"):
        value = profile.get(key)
        if not isinstance(value, (int, float)) or value <= 0:
            raise CmcError(
                "E_BAD_PROFILE",
                f"Birim profili bozuk: {key} geçersiz.",
                "`cmc calibrate` komutunu tekrar çalıştırın.",
            )
    return profile


def snap(ratio):
    """Pull a measured ratio onto a clean power of ten, or refuse to."""
    if ratio is None or ratio <= 0:
        return None, False, None
    best, best_err = None, None
    for candidate in SCALE_CANDIDATES:
        err = abs(ratio / candidate - 1.0)
        if best_err is None or err < best_err:
            best, best_err = candidate, err
    if best_err <= SNAP_TOLERANCE:
        return best, True, best_err
    return ratio, False, best_err


def expected_block(length, width, height, density_kg_m3):
    """Hand-computable truth for the calibration block, in kg / mm."""
    volume_mm3 = length * width * height
    mass = volume_mm3 * density_kg_m3 / 1e9
    cg = (length / 2.0, width / 2.0, height / 2.0)

    ixx_cg = mass * (width ** 2 + height ** 2) / 12.0
    iyy_cg = mass * (length ** 2 + height ** 2) / 12.0
    izz_cg = mass * (length ** 2 + width ** 2) / 12.0

    # parallel axis out to the corner at the origin
    ixx_o = mass * (width ** 2 + height ** 2) / 3.0
    iyy_o = mass * (length ** 2 + height ** 2) / 3.0
    izz_o = mass * (length ** 2 + width ** 2) / 3.0

    return {
        "mass_kg": mass,
        "volume_mm3": volume_mm3,
        "cg_mm": cg,
        "diag_cg": (ixx_cg, iyy_cg, izz_cg),
        "diag_origin": (ixx_o, iyy_o, izz_o),
        # product integral about the origin: integral(x*y dm) = m*L*W/4
        "product_integral_origin": (
            mass * length * width / 4.0,
            mass * length * height / 4.0,
            mass * width * height / 4.0,
        ),
    }


def solve(raw, expected):
    """Turn one raw Analyze reading of the calibration block into a profile."""
    evidence = {"raw": _jsonable(raw), "expected": _jsonable(expected)}
    notes = []

    if not raw.get("mass_raw"):
        raise CmcError(
            "E_CALIB_NO_MASS",
            "Kalibrasyon parçası sıfır kütle raporluyor.",
            "Parçaya malzeme atanmış mı ve Design mode aktif mi kontrol edin.",
        )

    mass_scale, mass_clean, mass_err = snap(expected["mass_kg"] / raw["mass_raw"])
    if not mass_clean:
        notes.append("mass_scale_not_a_clean_power_of_ten")

    volume_scale, volume_clean = 1.0, True
    if raw.get("volume_raw"):
        volume_scale, volume_clean, _ = snap(expected["volume_mm3"] / raw["volume_raw"])
        if not volume_clean:
            notes.append("volume_scale_not_a_clean_power_of_ten")

    if not raw.get("cg_raw"):
        raise CmcError(
            "E_CALIB_NO_CG",
            "Kalibrasyon parçasından ağırlık merkezi okunamadı.",
            "Parçanın Design mode'da ve tek gövdeli olduğundan emin olun.",
        )
    raw_norm = _norm(raw["cg_raw"])
    if raw_norm <= 0:
        raise CmcError(
            "E_CALIB_CG_AT_ORIGIN",
            "Kalibrasyon parçasının CG'si orijinde, uzunluk ölçeği çözülemez.",
            "Bloğun bir köşesi parça orijininde olacak şekilde modellenmeli.",
        )
    length_scale, length_clean, _ = snap(_norm(expected["cg_mm"]) / raw_norm)
    if not length_clean:
        notes.append("length_scale_not_a_clean_power_of_ten")

    profile = {
        "mass_to_kg": mass_scale,
        "length_to_mm": length_scale,
        "volume_to_mm3": volume_scale,
        "inertia_to_kg_mm2": 1.0,
        "inertia_ref": None,
        "inertia_product_sign": None,
    }

    inertia = _solve_inertia(raw.get("inertia_raw"), expected, evidence, notes)
    profile.update(inertia)

    # cross-check: the scaled CG must reproduce the expected CG componentwise,
    # which also catches an axis permutation in the calibration part itself
    scaled_cg = [v * length_scale for v in raw["cg_raw"]]
    cg_err = max(abs(a - b) for a, b in zip(scaled_cg, expected["cg_mm"]))
    evidence["cg_check"] = {"scaled_cg_mm": scaled_cg, "max_abs_error_mm": cg_err}
    if cg_err > 0.5:
        raise CmcError(
            "E_CALIB_CG_MISMATCH",
            "Ölçeklenen CG beklenen değerle uyuşmuyor.",
            "Blok ölçülerini (L/W/H) ve bloğun bir köşesinin parça orijininde "
            "olduğunu kontrol edin. Eksen sırası farklı olabilir.",
            scaled_cg_mm=scaled_cg,
            expected_cg_mm=list(expected["cg_mm"]),
        )

    evidence["notes"] = notes
    return profile, evidence


def _solve_inertia(raw9, expected, evidence, notes):
    """Settle three unknowns: the scale, the reference point, and the sign.

    The diagonal terms alone CANNOT tell origin from CG for this artefact.  For
    a box with one corner at the origin,  I_origin = 4 * I_cg  on every axis,
    so both hypotheses fit the diagonal perfectly and only differ by a constant
    factor that the unknown unit scale would happily absorb.  That degeneracy
    is exactly how a factor-of-four inertia error ships unnoticed.

    The off-diagonal terms are not degenerate.  About the CG of an axis-aligned
    box they vanish; about the corner they do not.  The ratio
    off-diagonal / diagonal is dimensionless, so it answers the reference-point
    question without knowing the scale, and its sign answers the convention
    question at the same time.
    """
    if not raw9:
        notes.append("inertia_not_reported")
        return {"inertia_ref": None, "inertia_product_sign": None, "inertia_to_kg_mm2": 1.0}

    raw_diag = (raw9[0], raw9[4], raw9[8])
    if min(abs(v) for v in raw_diag) <= 0:
        notes.append("inertia_diagonal_non_positive")
        return {"inertia_ref": None, "inertia_product_sign": None, "inertia_to_kg_mm2": 1.0}

    measured_ratio = raw9[1] / raw_diag[0]
    origin_ratio = expected["product_integral_origin"][0] / expected["diag_origin"][0]
    evidence["inertia_reference_test"] = {
        "measured_offdiag_over_diag": measured_ratio,
        "expected_if_origin": origin_ratio,
        "expected_if_cg": 0.0,
    }

    if abs(measured_ratio) < 0.05 * abs(origin_ratio):
        # products vanished: CATIA is reporting about the centre of gravity
        ref, sign = "cg", None
        notes.append("inertia_product_sign_undetermined")
    elif abs(abs(measured_ratio) - abs(origin_ratio)) <= CONSISTENCY_TOLERANCE * abs(origin_ratio):
        ref = "origin"
        sign = 1 if measured_ratio > 0 else -1
    else:
        notes.append("inertia_reference_ambiguous")
        return {"inertia_ref": None, "inertia_product_sign": None, "inertia_to_kg_mm2": 1.0}

    key = "diag_origin" if ref == "origin" else "diag_cg"
    scales = [expected[key][i] / raw_diag[i] for i in range(3)]
    mean = sum(scales) / 3.0
    spread = max(abs(s / mean - 1.0) for s in scales)
    evidence["inertia_scale_test"] = {"scales": scales, "mean": mean, "spread": spread}
    if spread > CONSISTENCY_TOLERANCE:
        notes.append("inertia_axes_inconsistent")
        return {"inertia_ref": None, "inertia_product_sign": None, "inertia_to_kg_mm2": 1.0}

    scale, clean, _ = snap(mean)
    if not clean:
        notes.append("inertia_scale_not_a_clean_power_of_ten")

    return {"inertia_ref": ref, "inertia_product_sign": sign, "inertia_to_kg_mm2": scale}


def inertia_ready(profile):
    """Inertia may only be exported when both unknowns were actually settled."""
    return bool(profile.get("inertia_ref")) and profile.get("inertia_product_sign") in (1, -1)


def _norm(v):
    return sum(x * x for x in v) ** 0.5


def _jsonable(value):
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value
