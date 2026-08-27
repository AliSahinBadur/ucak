"""3x3 linear algebra and inertia bookkeeping, pure Python.

No numpy: this has to run on a locked-down engineering laptop where the only
thing you can count on is CPython plus pywin32.

INERTIA CONVENTION (canonical, used everywhere inside cmc)
----------------------------------------------------------
Everything is stored as the *inertia tensor*:

    T = [[ Ixx, Ixy, Ixz ],
         [ Ixy, Iyy, Iyz ],
         [ Ixz, Iyz, Izz ]]      with  Ixy = -integral(x*y dm)

That is the object that rotates as  T' = R T R^T  and obeys the parallel-axis
theorem in its usual form.  CATIA's raw output and Adams' input may each use
the opposite sign for the off-diagonal terms; both are converted at the
boundary using an explicitly calibrated / configured sign, never assumed.

Units inside cmc: mass kg, length mm, inertia kg*mm^2.
"""

IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
ZERO_T = (0.0, 0.0, 0.0)

TENSOR_KEYS = ("ixx", "iyy", "izz", "ixy", "ixz", "iyz")


# --------------------------------------------------------------------------
# basic matrix ops
# --------------------------------------------------------------------------

def mat_vec(R, v):
    return tuple(R[i][0] * v[0] + R[i][1] * v[1] + R[i][2] * v[2] for i in range(3))


def mat_mul(A, B):
    return tuple(
        tuple(sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3))
        for i in range(3)
    )


def transpose(A):
    return tuple(tuple(A[j][i] for j in range(3)) for i in range(3))


def vec_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vec_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vec_scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def compose(R_parent, T_parent, R_child, T_child):
    """Chain two rigid transforms: parent o child."""
    return mat_mul(R_parent, R_child), vec_add(mat_vec(R_parent, T_child), T_parent)


def apply(R, T, p):
    return vec_add(mat_vec(R, p), T)


def is_rotation(R, tol=1e-6):
    """R R^T == I and det == +1.  Guards against a bad transform profile."""
    P = mat_mul(R, transpose(R))
    for i in range(3):
        for j in range(3):
            if abs(P[i][j] - (1.0 if i == j else 0.0)) > tol:
                return False
    return abs(det(R) - 1.0) <= tol


def det(R):
    return (
        R[0][0] * (R[1][1] * R[2][2] - R[1][2] * R[2][1])
        - R[0][1] * (R[1][0] * R[2][2] - R[1][2] * R[2][0])
        + R[0][2] * (R[1][0] * R[2][1] - R[1][1] * R[2][0])
    )


# --------------------------------------------------------------------------
# inertia
# --------------------------------------------------------------------------

def tensor_from_dict(d):
    return (
        (d["ixx"], d["ixy"], d["ixz"]),
        (d["ixy"], d["iyy"], d["iyz"]),
        (d["ixz"], d["iyz"], d["izz"]),
    )


def dict_from_tensor(T):
    return {
        "ixx": T[0][0], "iyy": T[1][1], "izz": T[2][2],
        "ixy": T[0][1], "ixz": T[0][2], "iyz": T[1][2],
    }


def zero_tensor_dict():
    return {k: 0.0 for k in TENSOR_KEYS}


def raw9_to_tensor_dict(vals9, product_sign):
    """CATIA GetInertia returns 9 row-major doubles.

    `product_sign` is calibrated, not guessed:
      +1 -> CATIA reports products as integral(x*y dm)  -> tensor off-diag = -raw
      -1 -> CATIA already reports tensor off-diagonals  -> tensor off-diag = +raw
    """
    ixx, ixy_raw, ixz_raw, _, iyy, iyz_raw, _, _, izz = vals9
    s = -1.0 if product_sign > 0 else 1.0
    return {
        "ixx": ixx, "iyy": iyy, "izz": izz,
        "ixy": s * ixy_raw, "ixz": s * ixz_raw, "iyz": s * iyz_raw,
    }


def shift_to_cg(tensor_dict, mass, r):
    """Parallel axis, inward: tensor about a point at offset r from the CG,
    converted to the tensor about the CG.   T_G = T_O - m(|r|^2 I - r r^T)."""
    return _shift(tensor_dict, mass, r, sign=-1.0)


def shift_from_cg(tensor_dict, mass, r):
    """T about a point offset r from the CG, given T about the CG."""
    return _shift(tensor_dict, mass, r, sign=+1.0)


def _shift(td, mass, r, sign):
    rr = dot(r, r)
    x, y, z = r
    return {
        "ixx": td["ixx"] + sign * mass * (rr - x * x),
        "iyy": td["iyy"] + sign * mass * (rr - y * y),
        "izz": td["izz"] + sign * mass * (rr - z * z),
        "ixy": td["ixy"] + sign * mass * (-x * y),
        "ixz": td["ixz"] + sign * mass * (-x * z),
        "iyz": td["iyz"] + sign * mass * (-y * z),
    }


def rotate_tensor(tensor_dict, R):
    """T' = R T R^T."""
    T = tensor_from_dict(tensor_dict)
    return dict_from_tensor(mat_mul(mat_mul(R, T), transpose(R)))


def combine(items):
    """Combine leaves into one rigid body.

    items: iterable of (mass, cg_xyz, tensor_dict_about_own_cg_or_None)
    Returns (mass, cg, tensor_about_combined_cg, inertia_complete: bool).

    inertia_complete is False if any contributing item with mass > 0 had no
    inertia data; the mass and CG are still exact, only the tensor is partial
    and must not be exported.
    """
    items = list(items)
    total = sum(m for m, _, _ in items)
    if total <= 0.0:
        return 0.0, (0.0, 0.0, 0.0), zero_tensor_dict(), False

    cg = (
        sum(m * c[0] for m, c, _ in items) / total,
        sum(m * c[1] for m, c, _ in items) / total,
        sum(m * c[2] for m, c, _ in items) / total,
    )

    acc = zero_tensor_dict()
    complete = True
    for m, c, td in items:
        if td is None:
            if m > 0.0:
                complete = False
            continue
        d = vec_sub(c, cg)
        shifted = shift_from_cg(td, m, d)
        for k in TENSOR_KEYS:
            acc[k] += shifted[k]
    return total, cg, acc, complete
