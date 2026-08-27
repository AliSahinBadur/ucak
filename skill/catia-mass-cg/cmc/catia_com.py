"""The only module that touches CATIA.

Design rules that make this survive CATIA V5 R2021 ... R2026 unchanged:

1. LATE BINDING ONLY.  `win32com.client.gencache` / makepy wrappers are pinned
   to one type library version and break on the next release.  We dispatch
   dynamically and never import a generated wrapper.
2. NOTHING IS ASSUMED, EVERYTHING IS PROBED.  Enum values (work mode), unit
   scales and the inertia reference point differ between releases and
   installations.  Where the API is ambiguous we try candidates and verify the
   result, or we read the answer from the calibration profile.
3. FAILURES ARE CLASSIFIED.  A small agent cannot debug COM; it can only relay
   a message.  Every known failure mode gets its own error code and a Turkish
   hint that names the actual fix.

The tree walk itself lives in cmc.walk and talks to the `CatiaApi` object
defined here, so the same walk code can be exercised against cmc.fake_source
on a machine with no CATIA at all.
"""

import os

from .envelope import CmcError

# Candidate values for Product.ApplyWorkMode.  The documented enum name is
# catDesignMode but the numeric value is not dependable across releases, so we
# try each and keep whichever makes Analyze.Mass report a non-zero mass.
WORK_MODE_CANDIDATES = (1, 0, 2, 3)


def _win32():
    try:
        import pythoncom  # noqa: F401
        import win32com.client as w
    except ImportError as exc:
        raise CmcError(
            "E_NO_PYWIN32",
            "pywin32 kurulu değil, CATIA'ya bağlanılamıyor.",
            "64-bit Python kullanın ve `pip install pywin32` çalıştırın. "
            "32-bit Python ile CATIA V5 R2021+ oturumuna bağlanılamaz.",
        ) from exc
    return w


def purge_gen_py():
    """Delete the makepy cache so an early-bound wrapper generated against a
    different CATIA release cannot shadow late binding.  Cheap and idempotent."""
    import shutil
    import tempfile

    candidates = [os.path.join(tempfile.gettempdir(), "gen_py")]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(os.path.join(local, "Temp", "gen_py"))

    removed = []
    for path in candidates:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
            removed.append(path)
    return removed


def attach():
    """Attach to the CATIA session already open on this desktop."""
    w = _win32()
    import pythoncom

    try:
        ptr = pythoncom.GetActiveObject("CATIA.Application")
    except Exception as exc:  # com_error
        raise CmcError(
            "E_ATTACH_NOT_FOUND",
            "Açık bir CATIA oturumu bulunamadı.",
            "CATIA açık mı kontrol edin. Açıksa, CATIA ile bu agent aynı "
            "kullanıcı hesabında ve aynı yetki seviyesinde çalışmalı: biri "
            "yönetici olarak başlatıldıysa diğeri de yönetici olmalı.",
        ) from exc

    return w.dynamic.Dispatch(ptr)


def probe_version(catia):
    """Record whatever the installation is willing to report.  Never branch on
    this; it exists so a wrong number can be traced back later."""
    info = {}
    for path in (
        "SystemConfiguration.Version",
        "SystemConfiguration.Release",
        "SystemConfiguration.ServicePack",
        "FullName",
    ):
        try:
            obj = catia
            for part in path.split("."):
                obj = getattr(obj, part)
            info[path] = str(obj)
        except Exception:
            info[path] = None
    return info


def active_root(catia):
    try:
        doc = catia.ActiveDocument
    except Exception as exc:
        raise CmcError(
            "E_NO_ACTIVE_DOC",
            "CATIA'da açık bir doküman yok.",
            "Ölçülecek CATProduct dosyasını CATIA'da açıp aktif pencere yapın.",
        ) from exc
    try:
        root = doc.Product
    except Exception as exc:
        raise CmcError(
            "E_NOT_A_PRODUCT",
            "Aktif doküman bir CATProduct değil.",
            "Araç montajını (CATProduct) aktif pencere yapın.",
        ) from exc

    meta = {"document_name": None, "document_path": None}
    for key, attr in (("document_name", "Name"), ("document_path", "FullName")):
        try:
            meta[key] = str(getattr(doc, attr))
        except Exception:
            pass
    return root, meta


def force_design_mode(root):
    """Visualisation / cgr mode silently reports zero mass.  Try each candidate
    enum value and verify by reading a mass back."""
    attempts = []
    for mode in WORK_MODE_CANDIDATES:
        try:
            root.ApplyWorkMode(mode)
        except Exception:
            attempts.append({"value": mode, "applied": False, "mass": None})
            continue
        try:
            mass = float(root.Analyze.Mass)
        except Exception:
            mass = 0.0
        attempts.append({"value": mode, "applied": True, "mass": mass})
        if mass > 0.0:
            return {"work_mode_value": mode, "verified": True, "attempts": attempts}

    raise CmcError(
        "E_WORKMODE",
        "Design mode'a geçilemedi, montaj sıfır kütle raporluyor.",
        "Tools > Options > Infrastructure > Product Structure > Cache "
        "Management kapalı olmalı ve montaj Design mode'da açılmalı. "
        "Parçalara hiç malzeme atanmamış olma ihtimalini de kontrol edin.",
        attempts=attempts,
    )


def quiet(catia, enabled):
    """Suppress redraw during a long walk.  Always restore in a finally block."""
    for attr in ("RefreshDisplay", "Interactive"):
        try:
            setattr(catia, attr, not enabled)
        except Exception:
            pass


def _out_array(n):
    """CATIA fills caller-allocated arrays.  pywin32 needs an explicit BYREF
    VARIANT for that; a plain Python list silently comes back unchanged."""
    import pythoncom
    import win32com.client as w

    return w.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BYREF | pythoncom.VT_R8, [0.0] * n)


class CatiaApi:
    """Thin accessor layer over the COM objects.

    Every method is defensive: CATIA raises on a missing property instead of
    returning None, and one unlucky part must not abort a 2000-part walk.
    """

    name = "catia"

    def children(self, product):
        try:
            coll = product.Products
            count = int(coll.Count)
        except Exception:
            return []
        out = []
        for i in range(1, count + 1):
            try:
                out.append(coll.Item(i))
            except Exception:
                continue
        return out

    def position(self, product):
        """Occurrence transform of `product` inside its parent.

        GetComponents returns 12 doubles: the first 9 are the rotation matrix
        column by column (the images of x, y, z), the last 3 the translation.
        """
        identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        try:
            arr = _out_array(12)
            product.Position.GetComponents(arr)
            c = [float(v) for v in arr.value]
        except Exception:
            return identity, (0.0, 0.0, 0.0)
        R = ((c[0], c[3], c[6]), (c[1], c[4], c[7]), (c[2], c[5], c[8]))
        return R, (c[9], c[10], c[11])

    def analyze(self, product):
        """Raw Analyze values, in whatever units this installation uses."""
        out = {"mass_raw": None, "volume_raw": None, "cg_raw": None, "inertia_raw": None}
        try:
            an = product.Analyze
        except Exception:
            return out
        try:
            out["mass_raw"] = float(an.Mass)
        except Exception:
            pass
        try:
            out["volume_raw"] = float(an.Volume)
        except Exception:
            pass
        try:
            arr = _out_array(3)
            an.GetGravityCenter(arr)
            out["cg_raw"] = tuple(float(v) for v in arr.value)
        except Exception:
            pass
        try:
            arr = _out_array(9)
            an.GetInertia(arr)
            out["inertia_raw"] = [float(v) for v in arr.value]
        except Exception:
            pass
        return out

    def material(self, product):
        """Best effort across releases; None is a valid, expected answer."""
        for getter in (
            lambda p: p.ReferenceProduct.UserRefProperties.Item("Material").Value,
            lambda p: p.UserRefProperties.Item("Material").Value,
            lambda p: p.ReferenceProduct.Material.Name,
        ):
            try:
                value = getter(product)
                if value:
                    return str(value)
            except Exception:
                continue
        return None

    def name_of(self, product, fallback):
        for attr in ("Name", "PartNumber"):
            try:
                value = str(getattr(product, attr))
                if value:
                    return value.replace("/", "_")
            except Exception:
                continue
        return fallback

    def part_number(self, product):
        try:
            return str(product.PartNumber)
        except Exception:
            return None
