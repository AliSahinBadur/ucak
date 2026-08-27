"""CATIA -> Adams coordinate transform.

The convention is data, not code.  Vehicle programs disagree about where the
origin sits and which way X points, and hardcoding one shop's convention is
how a sign error ships.  So the transform lives in transform_profile.json and
is verified against landmarks whose coordinates are known independently in
both systems, typically the front and rear wheel centres.

    p_adams = R * p_catia + t

R must be a proper rotation (usually a signed permutation for these
conventions).  Inertia tensors transform as T' = R T R^T; they are not points
and do not take the translation.
"""

from .envelope import CmcError
from . import geom

LANDMARK_TOL_MM = 1.0


def load(profile):
    if not profile:
        raise CmcError(
            "E_NO_TRANSFORM",
            "CATIA-Adams dönüşüm profili tanımlı değil.",
            "assets/transform_profile.example.json dosyasını workspace'e "
            "transform_profile.json olarak kopyalayıp doldurun.",
        )
    R = profile.get("rotation")
    if not R or len(R) != 3 or any(len(row) != 3 for row in R):
        raise CmcError(
            "E_BAD_TRANSFORM",
            "Dönüşüm profilindeki rotation 3x3 değil.",
            "rotation alanı üç satır ve üç sütun içermeli.",
        )
    R = tuple(tuple(float(v) for v in row) for row in R)
    if not geom.is_rotation(R):
        raise CmcError(
            "E_BAD_TRANSFORM",
            "Dönüşüm matrisi geçerli bir rotasyon değil (R R^T = I ve det = +1 sağlanmıyor).",
            "İşaretli permütasyon matrisi kullanın; determinant -1 ise bir "
            "eksenin işareti yanlış, ayna dönüşümü koordinat sistemini bozar.",
            determinant=geom.det(R),
        )
    t = profile.get("translation_mm") or [0.0, 0.0, 0.0]
    if len(t) != 3:
        raise CmcError(
            "E_BAD_TRANSFORM",
            "translation_mm üç bileşen içermeli.",
            "Örnek: [0, 0, 0]",
        )
    return {
        "R": R,
        "t": tuple(float(v) for v in t),
        "name": profile.get("name", "unnamed"),
        "adams_product_of_inertia_sign": int(profile.get("adams_product_of_inertia_sign", 1)),
        "landmarks": profile.get("landmarks", []),
    }


def point(tp, p):
    return geom.apply(tp["R"], tp["t"], tuple(p))


def tensor(tp, td):
    return geom.rotate_tensor(td, tp["R"])


def verify_landmarks(tp, tolerance_mm=LANDMARK_TOL_MM):
    """Check the profile against points whose position is known in both
    systems.  Two landmarks far apart catch a wrong axis or a wrong origin;
    one landmark at the origin catches nothing, so require at least two."""
    landmarks = tp["landmarks"]
    if len(landmarks) < 2:
        raise CmcError(
            "E_NO_LANDMARKS",
            "Dönüşüm profili en az iki doğrulama noktası içermeli.",
            "Ön ve arka tekerlek merkezi gibi, koordinatı hem CATIA'da hem "
            "Adams'ta bilinen iki nokta ekleyin. Doğrulanmamış bir dönüşüm "
            "profili ile export yapmak sessiz işaret hatası üretir.",
        )
    rows, worst = [], 0.0
    for lm in landmarks:
        got = point(tp, lm["catia_mm"])
        expected = tuple(float(v) for v in lm["adams_mm"])
        err = [abs(a - b) for a, b in zip(got, expected)]
        worst = max(worst, max(err))
        rows.append({
            "name": lm.get("name", "?"),
            "mapped_mm": list(got),
            "expected_mm": list(expected),
            "max_abs_error_mm": max(err),
        })
    if worst > tolerance_mm:
        raise CmcError(
            "E_LANDMARK_MISMATCH",
            "Dönüşüm profili doğrulama noktalarını tutturamıyor.",
            "rotation işaretlerini ve translation_mm değerini gözden geçirin. "
            "İki nokta arasındaki mesafe her iki sistemde aynı çıkmıyorsa "
            "eksen eşlemesi yanlıştır.",
            landmarks=rows,
            max_abs_error_mm=worst,
            tolerance_mm=tolerance_mm,
        )
    return {"status": "ok", "landmarks": rows, "max_abs_error_mm": worst}


def to_adams_products(tp, td):
    """Adams' ixy/iyz/izx inputs use the product-of-inertia convention chosen
    in the profile; our canonical storage is the tensor off-diagonal."""
    sign = -1.0 if tp["adams_product_of_inertia_sign"] > 0 else 1.0
    return {
        "ixx": td["ixx"], "iyy": td["iyy"], "izz": td["izz"],
        "ixy": sign * td["ixy"], "ixz": sign * td["ixz"], "iyz": sign * td["iyz"],
    }
