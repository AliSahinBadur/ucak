"""A synthetic assembly that behaves like CATIA, quirks included.

Purpose: the engineer can run and trust the whole pipeline (traversal,
transform chaining, calibration solver, rollup invariants, revision diff,
Adams export) on a laptop with no CATIA licence, and the agent's behaviour can
be tested repeatably.

To make it a real test rather than a demo, the fake reports values in
deliberately mixed units, the way a real installation does:

    mass       kg          (scale 1)
    CG         mm          (scale 1)
    volume     m^3         (scale 1e9 to mm^3)
    inertia    kg*m^2 about the PART ORIGIN, off-diagonals as integral(x*y dm)

If the calibration solver cannot recover exactly those four facts, it is not
good enough for a real machine either.

The vehicle sums to 2046.402 kg to match the manual table this pipeline
replaces.  The wheels sit *inside* the axle subtrees, which is precisely the
double counting trap the bucket map has to resolve.
"""

from . import geom

DENSITY = 7850.0  # kg/m^3, used to fabricate plausible volumes

IDENT = geom.IDENTITY
ROT_Z90 = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))


class Node:
    def __init__(self, name, part_number=None, position=(IDENT, (0.0, 0.0, 0.0)),
                 mass=None, cg_local=None, box=None, material="Steel", children=None):
        self.name = name
        self.part_number = part_number or name.split(".")[0]
        self.position = position
        self.mass = mass
        self.cg_local = cg_local
        self.box = box
        self.material = material
        self.children = children or []


class FakeApi:
    """Same surface as cmc.catia_com.CatiaApi."""

    name = "fake"

    def children(self, node):
        return node.children

    def position(self, node):
        return node.position

    def analyze(self, node):
        if node.children:
            return _aggregate_analyze(node)
        if node.mass is None:
            return {"mass_raw": None, "volume_raw": None, "cg_raw": None, "inertia_raw": None}
        return {
            "mass_raw": node.mass,
            "volume_raw": (node.mass / DENSITY) if node.mass else 0.0,
            "cg_raw": tuple(node.cg_local),
            "inertia_raw": _raw_inertia(node),
        }

    def material(self, node):
        return node.material

    def name_of(self, node, fallback):
        return node.name or fallback

    def part_number(self, node):
        return node.part_number


# --------------------------------------------------------------------------
# inertia fabrication
# --------------------------------------------------------------------------

def _raw_inertia(node):
    """Box inertia about the part origin, in kg*m^2, products as integrals."""
    if not node.mass or not node.box:
        return None
    l, w, h = node.box
    m = node.mass
    t_cg = {
        "ixx": m * (w * w + h * h) / 12.0,
        "iyy": m * (l * l + h * h) / 12.0,
        "izz": m * (l * l + w * w) / 12.0,
        "ixy": 0.0, "ixz": 0.0, "iyz": 0.0,
    }
    t_o = geom.shift_from_cg(t_cg, m, tuple(node.cg_local))  # kg*mm^2, tensor
    s = 1e-6  # mm^2 -> m^2
    return [
        t_o["ixx"] * s, -t_o["ixy"] * s, -t_o["ixz"] * s,
        -t_o["ixy"] * s, t_o["iyy"] * s, -t_o["iyz"] * s,
        -t_o["ixz"] * s, -t_o["iyz"] * s, t_o["izz"] * s,
    ]


def _aggregate_analyze(node):
    """What CATIA reports for a subassembly: its children combined, expressed
    in the node's own axis system."""
    items = []
    _collect(node, IDENT, (0.0, 0.0, 0.0), items)
    if not items:
        return {"mass_raw": None, "volume_raw": None, "cg_raw": None, "inertia_raw": None}
    mass, cg, tensor, _ = geom.combine(items)
    if mass <= 0:
        return {"mass_raw": 0.0, "volume_raw": 0.0, "cg_raw": (0.0, 0.0, 0.0), "inertia_raw": None}
    t_o = geom.shift_from_cg(tensor, mass, cg)
    s = 1e-6
    inertia = [
        t_o["ixx"] * s, -t_o["ixy"] * s, -t_o["ixz"] * s,
        -t_o["ixy"] * s, t_o["iyy"] * s, -t_o["iyz"] * s,
        -t_o["ixz"] * s, -t_o["iyz"] * s, t_o["izz"] * s,
    ]
    return {
        "mass_raw": mass,
        "volume_raw": mass / DENSITY,
        "cg_raw": cg,
        "inertia_raw": inertia,
    }


def _collect(node, R_acc, T_acc, out):
    for child in node.children:
        R_c, T_c = child.position
        R_n, T_n = geom.compose(R_acc, T_acc, R_c, T_c)
        if child.children:
            _collect(child, R_n, T_n, out)
        elif child.mass:
            cg = geom.apply(R_n, T_n, tuple(child.cg_local))
            t_cg = None
            raw = _raw_inertia(child)
            if raw:
                td = geom.raw9_to_tensor_dict([v * 1e6 for v in raw], 1)
                td = geom.shift_to_cg(td, child.mass, tuple(child.cg_local))
                t_cg = geom.rotate_tensor(td, R_n)
            out.append((child.mass, cg, t_cg))


# --------------------------------------------------------------------------
# the vehicle
# --------------------------------------------------------------------------

def _leaf(name, mass, cg_root, origin, R=IDENT, box=(400.0, 300.0, 300.0), material="Steel"):
    """Place a leaf so that its CG lands exactly on `cg_root` once the parent
    transform (R, origin) is applied.  Local CG = R^T (cg_root - origin)."""
    delta = geom.vec_sub(cg_root, origin)
    local = geom.mat_vec(geom.transpose(R), delta)
    return Node(name, mass=mass, cg_local=local, box=box, material=material)


def _group(name, origin, R, leaves):
    return Node(name, position=(R, origin), children=leaves)


def vehicle(inject_faults=False):
    """Synthetic vehicle, 2046.402 kg total."""
    fa_o = (500.0, 0.0, -300.0)
    ra_o = (3300.0, 0.0, -350.0)
    ch_o = (2000.0, 0.0, -200.0)

    front_axle = _group("FrontAxle.1", fa_o, IDENT, [
        _leaf("FA_Beam.1", 140.0, (505.0, 0.0, -330.0), fa_o),
        _leaf("FA_Diff.1", 70.0, (520.0, -40.0, -310.0), fa_o),
        _leaf("Wheel_FL.1", 62.0, (500.0, 820.0, -330.0), fa_o, box=(300.0, 300.0, 300.0), material="Rubber"),
        _leaf("Wheel_FR.1", 62.0, (500.0, -820.0, -330.0), fa_o, box=(300.0, 300.0, 300.0), material="Rubber"),
    ])

    rear_axle = _group("RearAxle.1", ra_o, IDENT, [
        _leaf("RA_Beam.1", 220.0, (3310.0, 0.0, -360.0), ra_o),
        _leaf("RA_Diff.1", 100.0, (3280.0, -30.0, -340.0), ra_o),
        _leaf("Wheel_RL.1", 62.0, (3300.0, 830.0, -350.0), ra_o, box=(300.0, 300.0, 300.0), material="Rubber"),
        _leaf("Wheel_RR.1", 62.0, (3300.0, -830.0, -350.0), ra_o, box=(300.0, 300.0, 300.0), material="Rubber"),
    ])

    front_susp = _group("FrontSuspension.1", (500.0, 0.0, -200.0), IDENT, [
        _leaf("FS_Left.1", 90.0, (505.0, 600.0, -220.0), (500.0, 0.0, -200.0)),
        _leaf("FS_Right.1", 90.0, (505.0, -600.0, -220.0), (500.0, 0.0, -200.0)),
    ])

    rear_susp = _group("RearSuspension.1", (3300.0, 0.0, -250.0), IDENT, [
        _leaf("RS_Left.1", 89.2445, (3305.0, 610.0, -270.0), (3300.0, 0.0, -250.0)),
        _leaf("RS_Right.1", 89.2445, (3305.0, -610.0, -270.0), (3300.0, 0.0, -250.0)),
    ])

    steering_col = _group("SteeringColumn.1", (900.0, -350.0, 200.0), IDENT, [
        _leaf("SC_Tube.1", 18.0, (930.0, -360.0, 260.0), (900.0, -350.0, 200.0), box=(600.0, 80.0, 80.0)),
    ])

    steering_link = _group("SteeringLinkage.1", (700.0, 0.0, -150.0), IDENT, [
        _leaf("SL_Rod.1", 12.0, (720.0, -20.0, -160.0), (700.0, 0.0, -150.0), box=(800.0, 60.0, 60.0)),
    ])

    # rotated on purpose: exercises the rotation part of the transform chain
    chassis = _group("Chassis.1", ch_o, ROT_Z90, [
        _leaf("CH_FrontRail.1", 439.9565, (1400.0, 30.0, -180.0), ch_o, R=ROT_Z90,
              box=(2000.0, 400.0, 300.0)),
        _leaf("CH_RearRail.1", 439.9565, (2600.0, -30.0, -190.0), ch_o, R=ROT_Z90,
              box=(2000.0, 400.0, 300.0)),
    ])

    children = [front_axle, front_susp, rear_axle, rear_susp,
                steering_col, steering_link, chassis]

    if inject_faults:
        # a part with no material: CATIA reports it as zero mass, silently
        chassis.children.append(
            Node("CH_Bracket.1", mass=0.0, cg_local=(10.0, 10.0, 10.0),
                 box=(50.0, 50.0, 50.0), material=None)
        )
        # a part nobody thought to map to a bucket
        children.append(_group("Toolbox.1", (2500.0, 500.0, 100.0), IDENT, [
            _leaf("TB_Case.1", 0.0, (2510.0, 505.0, 110.0), (2500.0, 500.0, 100.0),
                  box=(300.0, 200.0, 150.0), material=None),
        ]))

    return Node("Vehicle", children=children)


def calibration_block(length, width, height, density=DENSITY):
    """The calibration artefact, reported in the fake's mixed units."""
    mass = length * width * height * density / 1e9
    return Node("CalibBlock", mass=mass,
                cg_local=(length / 2.0, width / 2.0, height / 2.0),
                box=(length, width, height), material="Steel")
