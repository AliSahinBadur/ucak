"""Assembly traversal, independent of where the data comes from.

Takes an `api` object (cmc.catia_com.CatiaApi or cmc.fake_source.FakeApi) and
produces leaf records already expressed in root axes and in kg / mm / kg*mm^2.

The transform chain is the part people get wrong.  Analyze values on a
sub-product are expressed in *that product's own* axis system.  If you read
them without composing the occurrence transforms from the root down, every
individual part looks plausible and the assembly CG is quietly wrong.
"""

from .envelope import CmcError
from . import geom

MAX_DEPTH = 64


def iter_leaves(api, root, units, progress=None):
    root_name = api.name_of(root, "Root")
    stack = [(root, "/" + root_name, geom.IDENTITY, geom.ZERO_T, 0)]
    seen = 0

    while stack:
        product, path, R_acc, T_acc, depth = stack.pop()
        if depth > MAX_DEPTH:
            raise CmcError(
                "E_TREE_DEPTH",
                f"Ağaç {MAX_DEPTH} seviyeden derin, döngüsel referans olabilir.",
                "Kendini referans eden bir alt ürün olup olmadığını kontrol edin.",
                path=path,
            )

        children = api.children(product)
        if not children:
            seen += 1
            if progress and seen % 250 == 0:
                progress(seen)
            yield leaf_record(api, product, path, R_acc, T_acc, units)
            continue

        for index, child in enumerate(children, start=1):
            name = api.name_of(child, f"Item{index}")
            R_c, T_c = api.position(child)
            R_n, T_n = geom.compose(R_acc, T_acc, R_c, T_c)
            stack.append((child, f"{path}/{name}", R_n, T_n, depth + 1))


def leaf_record(api, product, path, R_acc, T_acc, units):
    raw = api.analyze(product)
    flags = []

    if raw["mass_raw"] is None:
        mass = 0.0
        flags.append("no_mass_value")
    else:
        mass = raw["mass_raw"] * units["mass_to_kg"]
        if mass <= 0.0:
            flags.append("zero_mass")

    if raw["cg_raw"] is None:
        cg_local = (0.0, 0.0, 0.0)
        flags.append("no_cg_value")
    else:
        cg_local = tuple(v * units["length_to_mm"] for v in raw["cg_raw"])

    # translations are lengths too, so they take the same scale
    T_mm = tuple(v * units["length_to_mm"] for v in T_acc)
    cg_root = geom.apply(R_acc, T_mm, cg_local)

    volume_mm3 = None
    density = None
    if raw["volume_raw"] is not None:
        volume_mm3 = raw["volume_raw"] * units["volume_to_mm3"]
        if volume_mm3 > 1e-9:
            density = mass / volume_mm3 * 1e9  # kg/m^3
    if not density or density <= 0.0:
        flags.append("no_density")

    tensor = None
    if raw["inertia_raw"] is not None and mass > 0.0 and units.get("inertia_ref"):
        scaled = [v * units["inertia_to_kg_mm2"] for v in raw["inertia_raw"]]
        td = geom.raw9_to_tensor_dict(scaled, units["inertia_product_sign"] or 1)
        if units["inertia_ref"] == "origin":
            td = geom.shift_to_cg(td, mass, cg_local)
        tensor = geom.rotate_tensor(td, R_acc)
    else:
        flags.append("no_inertia")

    material = api.material(product)
    if not material:
        flags.append("no_material")

    return {
        "occurrence_path": path,
        "instance_name": path.rsplit("/", 1)[-1],
        "part_number": api.part_number(product),
        "mass_kg": mass,
        "cg_mm": list(cg_root),
        "volume_mm3": volume_mm3,
        "density_kg_m3": density,
        "material": material,
        "inertia_tensor_cg_root_axes": tensor,
        "flags": flags,
    }


def root_totals(api, root, units):
    """CATIA's own answer for the whole assembly.

    This is the independent check on our leaf summation.  If the two disagree
    the traversal is wrong and nothing may be exported.
    """
    raw = api.analyze(root)
    mass = (raw["mass_raw"] or 0.0) * units["mass_to_kg"]
    cg = None
    if raw["cg_raw"] is not None:
        cg = [v * units["length_to_mm"] for v in raw["cg_raw"]]
    return {"mass_kg": mass, "cg_mm": cg}
