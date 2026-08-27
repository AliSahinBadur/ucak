"""Command line surface.

Every subcommand prints exactly one JSON envelope and exits.  The agent reads
`message_tr` and `next_command` and nothing else.  Arguments are few and
positionalless on purpose: a small model can copy a command, it cannot invent
one reliably.
"""

import argparse
import getpass
import hashlib
import os
import platform
import struct
import sys

from . import config, diff as diff_mod, export as export_mod, rollup as rollup_mod
from . import store, transform, units, walk
from .envelope import CmcError, fail, ok
from . import __version__

MAX_HASH_BYTES = 500 * 1024 * 1024


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _api_and_root(args, for_calibration=False):
    """Return (api, root, session_meta) for the chosen source."""
    if args.source == "fake":
        from . import fake_source

        api = fake_source.FakeApi()
        if for_calibration:
            root = fake_source.calibration_block(args.length, args.width, args.height, args.density)
            meta = {"document_name": "CalibBlock.CATPart", "document_path": None}
        else:
            root = fake_source.vehicle(inject_faults=getattr(args, "inject_faults", False))
            meta = {"document_name": "FakeVehicle.CATProduct", "document_path": None}
        return api, root, {
            "catia_version": {"source": "fake"},
            "work_mode": {"work_mode_value": None, "verified": True, "source": "fake"},
            **meta,
        }

    from . import catia_com

    catia = catia_com.attach()
    version = catia_com.probe_version(catia)
    root, doc_meta = catia_com.active_root(catia)
    work_mode = catia_com.force_design_mode(root)
    return catia_com.CatiaApi(), root, {
        "catia_version": version,
        "work_mode": work_mode,
        "_catia": catia,
        **doc_meta,
    }


def _sha256(path):
    if not path or not os.path.isfile(path):
        return None
    try:
        if os.path.getsize(path) > MAX_HASH_BYTES:
            return "skipped_too_large"
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _need(path, code, message, hint):
    data = config.read_json(path)
    if data is None:
        raise CmcError(code, message, hint)
    return data


def _run_or_die(run_id_arg, step):
    run_id = config.resolve_run(run_id_arg)
    if not run_id:
        raise CmcError(
            "E_NO_RUN",
            "Hangi ölçüm üzerinde çalışılacağı belli değil.",
            "Önce `python -m cmc extract` çalıştırın.",
        )
    if not config.run_dir(run_id).exists():
        raise CmcError(
            "E_RUN_NOT_FOUND",
            f"'{run_id}' ölçümü bulunamadı.",
            "`python -m cmc history` ile mevcut ölçümleri listeleyin.",
        )
    return run_id


def _fmt(value, digits=3):
    return f"{value:.{digits}f}"


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_doctor(args):
    bits = struct.calcsize("P") * 8
    has_pywin32 = True
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        has_pywin32 = False

    problems = []
    if platform.system() == "Windows":
        if bits != 64:
            problems.append("Python 64-bit değil, CATIA V5 R2021+ ile konuşamaz.")
        if not has_pywin32:
            problems.append("pywin32 kurulu değil (`pip install pywin32`).")
    purged = []
    if has_pywin32:
        from . import catia_com

        purged = catia_com.purge_gen_py()

    workspace = {
        "units_profile.json": (config.home() / "units_profile.json").exists(),
        "subassembly_map.json": (config.home() / "subassembly_map.json").exists(),
        "transform_profile.json": (config.home() / "transform_profile.json").exists(),
        "adams_map.json": (config.home() / "adams_map.json").exists(),
    }

    if problems:
        raise CmcError(
            "E_ENVIRONMENT",
            "Ortam hazır değil: " + " ".join(problems),
            "Sorunları giderip `python -m cmc doctor` komutunu tekrar çalıştırın.",
            python_bits=bits, pywin32=has_pywin32, workspace=workspace,
        )

    if (config.home() / "units_profile.json").exists():
        ask = _ASK_EXTRACT
        template = _TEMPLATE_EXTRACT
    else:
        ask = _ASK_CALIBRATE
        template = _TEMPLATE_CALIBRATE
    return ok(
        "doctor",
        "Ortam uygun. Python {}-bit, pywin32 {}.".format(bits, "var" if has_pywin32 else "yok"),
        next_command=None,
        ask_user_tr=ask,
        command_template=template,
        python_bits=bits, pywin32=has_pywin32, workspace=workspace,
        purged_gen_py=purged, cmc_version=__version__, workspace_path=str(config.home()),
    )


_ASK_CALIBRATE = (
    "Kalibrasyon bloğunun ölçülerini (uzunluk, genişlik, yükseklik, mm) ve "
    "malzeme yoğunluğunu (kg/m^3) kullanıcıya sorun. Blok CATIA'da açık olmalı. "
    "Bu değerleri kendiniz seçmeyin."
)
_TEMPLATE_CALIBRATE = (
    "python -m cmc calibrate --length <UZUNLUK> --width <GENISLIK> "
    "--height <YUKSEKLIK> --density <YOGUNLUK>"
)
_ASK_EXTRACT = (
    "Araç adını, varyantı ve revizyon numarasını kullanıcıya sorun. "
    "Bu değerleri kendiniz uydurmayın; kayıtlar bunlara göre saklanıyor."
)
_TEMPLATE_EXTRACT = (
    "python -m cmc extract --vehicle <ARAC> --variant <VARYANT> --revision <REVIZYON>"
)


def cmd_attach(args):
    api, root, session = _api_and_root(args)
    session.pop("_catia", None)
    config.write_json(config.home() / "session.json", session)
    profile_exists = (config.home() / "units_profile.json").exists()
    return ok(
        "attach",
        "CATIA oturumuna bağlanıldı: {}.".format(session.get("document_name") or "?"),
        next_command=None,
        ask_user_tr=_ASK_EXTRACT if profile_exists else _ASK_CALIBRATE,
        command_template=_TEMPLATE_EXTRACT if profile_exists else _TEMPLATE_CALIBRATE,
        document=session.get("document_name"),
        catia_version=session.get("catia_version"),
        work_mode=session.get("work_mode"),
    )


def cmd_calibrate(args):
    api, root, session = _api_and_root(args, for_calibration=True)
    raw = api.analyze(root)
    expected = units.expected_block(args.length, args.width, args.height, args.density)
    profile, evidence = units.solve(raw, expected)

    profile.update({
        "created_at": config.now_iso(),
        "machine": platform.node(),
        "created_by": getpass.getuser(),
        "catia_version": session.get("catia_version"),
        "block_mm": [args.length, args.width, args.height],
        "block_density_kg_m3": args.density,
        "evidence": evidence,
    })
    config.write_json(config.home() / "units_profile.json", profile)

    warnings = []
    for note in evidence.get("notes", []):
        warnings.append({"kind": note, "message_tr": _NOTE_TR.get(note, note)})

    inertia_msg = ("atalet: {} referansı, çarpım işareti {}".format(
        profile["inertia_ref"], profile["inertia_product_sign"])
        if units.inertia_ready(profile) else
        "atalet çözülemedi, sadece kütle ve CG kullanılabilir")
    return ok(
        "calibrate",
        "Kalibrasyon tamam. Kütle ölçeği {}, uzunluk ölçeği {}, {}.".format(
            profile["mass_to_kg"], profile["length_to_mm"], inertia_msg),
        next_command=None,
        ask_user_tr=_ASK_EXTRACT,
        command_template=_TEMPLATE_EXTRACT,
        warnings=warnings,
        profile={k: profile[k] for k in
                 ("mass_to_kg", "length_to_mm", "volume_to_mm3", "inertia_to_kg_mm2",
                  "inertia_ref", "inertia_product_sign")},
        inertia_usable=units.inertia_ready(profile),
        artifact=str(config.home() / "units_profile.json"),
    )


_NOTE_TR = {
    "mass_scale_not_a_clean_power_of_ten":
        "Kütle ölçeği ondalık bir katsayı çıkmadı, blok yoğunluğunu kontrol edin.",
    "length_scale_not_a_clean_power_of_ten":
        "Uzunluk ölçeği ondalık bir katsayı çıkmadı, blok ölçülerini kontrol edin.",
    "volume_scale_not_a_clean_power_of_ten":
        "Hacim ölçeği ondalık bir katsayı çıkmadı.",
    "inertia_scale_not_a_clean_power_of_ten":
        "Atalet ölçeği ondalık bir katsayı çıkmadı.",
    "inertia_not_reported": "CATIA atalet matrisi vermedi, atalet aktarımı kapalı.",
    "inertia_reference_ambiguous":
        "Atalet referans noktası belirlenemedi (ne orijin ne CG tutuyor), atalet aktarımı kapalı.",
    "inertia_product_sign_undetermined":
        "Atalet çarpım terimlerinin işareti bu parçadan belirlenemedi; blok orijinde "
        "değil, bir köşesi orijinde olacak şekilde modellenmeli.",
    "inertia_product_terms_vanished":
        "Atalet çarpım terimleri sıfır geldi, işaret belirlenemedi.",
    "inertia_diagonal_non_positive": "Atalet köşegeni pozitif değil, veri güvenilmez.",
}


def cmd_extract(args):
    profile = units.load(config.read_json(config.home() / "units_profile.json"))
    api, root, session = _api_and_root(args)
    catia = session.pop("_catia", None)

    run_id = config.new_run_id()
    components = []
    try:
        if catia is not None:
            from . import catia_com

            catia_com.quiet(catia, True)
        for record in walk.iter_leaves(api, root, profile):
            components.append(record)
        totals = walk.root_totals(api, root, profile)
    finally:
        if catia is not None:
            from . import catia_com

            catia_com.quiet(catia, False)

    if not components:
        raise CmcError(
            "E_EMPTY_TREE",
            "Montajda hiç parça bulunamadı.",
            "Doğru CATProduct aktif mi ve ağaç açık mı kontrol edin.",
        )

    source_path = session.get("document_path")
    meta = {
        "run_id": run_id,
        "cmc_version": __version__,
        "vehicle": args.vehicle,
        "variant": args.variant,
        "revision": args.revision,
        "source": args.source,
        "source_document": source_path or session.get("document_name"),
        "source_sha256": _sha256(source_path),
        "catia_version": session.get("catia_version"),
        "work_mode": session.get("work_mode"),
        "units_profile": {k: profile.get(k) for k in
                          ("mass_to_kg", "length_to_mm", "volume_to_mm3",
                           "inertia_to_kg_mm2", "inertia_ref", "inertia_product_sign")},
        "measured_by": getpass.getuser(),
        "measured_at": config.now_iso(),
        "root_totals": totals,
    }
    config.write_json(config.run_dir(run_id) / "meta.json", meta)
    config.write_json(config.run_dir(run_id) / "components.json", components)
    config.set_last_run(run_id)

    zero = sum(1 for c in components if "zero_mass" in c["flags"] or "no_mass_value" in c["flags"])
    no_mat = sum(1 for c in components if "no_material" in c["flags"])
    warnings = []
    if zero:
        warnings.append({"kind": "zero_mass",
                         "message_tr": f"{zero} parça sıfır kütle raporluyor."})
    if no_mat:
        warnings.append({"kind": "no_material",
                         "message_tr": f"{no_mat} parçanın malzemesi tanımsız."})

    return ok(
        "extract",
        "{} parça tarandı, CATIA montaj kütlesi {} kg.".format(
            len(components), _fmt(totals["mass_kg"])),
        next_command=f"python -m cmc rollup --run {run_id}",
        warnings=warnings,
        run_id=run_id,
        leaf_count=len(components),
        catia_root_mass_kg=totals["mass_kg"],
        artifact=str(config.run_dir(run_id) / "components.json"),
    )


def cmd_rollup(args):
    run_id = _run_or_die(args.run, "rollup")
    meta = config.read_json(config.run_dir(run_id) / "meta.json")
    components = config.read_json(config.run_dir(run_id) / "components.json")
    bucket_file = _need(
        config.home() / "subassembly_map.json",
        "E_NO_BUCKET_MAP",
        "Alt yapı eşleme dosyası yok.",
        "assets/subassembly_map.example.json dosyasını workspace'e "
        "subassembly_map.json olarak kopyalayıp düzenleyin.",
    )

    rolled = rollup_mod.build(
        components,
        bucket_file["buckets"],
        bucket_file.get("groups"),
        meta.get("root_totals"),
    )
    config.write_json(config.run_dir(run_id) / "rollup.json", rolled)

    assigned = {c["occurrence_path"]: c for c in components}
    compiled = rollup_mod.compile_patterns(bucket_file["buckets"])
    with_bucket, _, _ = rollup_mod.assign(list(assigned.values()), compiled)
    store.save(meta, rolled, with_bucket)

    totals = rolled["totals"]
    return ok(
        "rollup",
        "{} alt yapı hesaplandı. Toplam {} kg, CG X {} / Y {} / Z {} mm. "
        "Kütle ve CG kontrolleri CATIA'nın kendi montaj değerleriyle tutuyor.".format(
            len(rolled["buckets"]), _fmt(totals["mass_kg"]), _fmt(totals["cg_mm"][0]),
            _fmt(totals["cg_mm"][1]), _fmt(totals["cg_mm"][2])),
        next_command=f"python -m cmc diff --run {run_id}",
        warnings=rolled["warnings"],
        run_id=run_id,
        totals=totals,
        checks=rolled["checks"],
        bucket_conflict_count=rolled["bucket_conflict_count"],
        artifact=str(config.run_dir(run_id) / "rollup.json"),
    )


def cmd_diff(args):
    run_id = _run_or_die(args.run, "diff")
    meta = config.read_json(config.run_dir(run_id) / "meta.json")
    data = diff_mod.compare(run_id, meta["vehicle"], meta["variant"])
    config.write_json(config.run_dir(run_id) / "diff.json", data)

    if not data["has_previous"]:
        message = "Bu araç ve varyant için ilk ölçüm, karşılaştırma yapılmadı."
    else:
        dx, dy, dz = data["delta_total_cg_mm"]
        message = ("Önceki revizyon {}: toplam kütle farkı {:+.3f} kg, "
                   "CG farkı X {:+.2f} / Y {:+.2f} / Z {:+.2f} mm, "
                   "{} alt yapıda eşik üstü değişim.").format(
            data["previous"]["revision"], data["delta_total_mass_kg"],
            dx, dy, dz, data["significant_bucket_count"])

    return ok(
        "diff",
        message,
        next_command=f"python -m cmc preview --run {run_id}",
        run_id=run_id,
        has_previous=data["has_previous"],
        artifact=str(config.run_dir(run_id) / "diff.json"),
    )


def cmd_preview(args):
    run_id = _run_or_die(args.run, "preview")
    meta = config.read_json(config.run_dir(run_id) / "meta.json")
    rolled = _need(
        config.run_dir(run_id) / "rollup.json",
        "E_NO_ROLLUP", "Bu ölçüm için alt yapı toplamı hesaplanmamış.",
        f"Önce `python -m cmc rollup --run {run_id}` çalıştırın.",
    )
    adams_map = _need(
        config.home() / "adams_map.json",
        "E_NO_ADAMS_MAP", "Adams parça eşleme dosyası yok.",
        "assets/adams_map.example.json dosyasını workspace'e adams_map.json "
        "olarak kopyalayıp düzenleyin.",
    )
    transform_profile = config.read_json(config.home() / "transform_profile.json")
    units_profile = units.load(config.read_json(config.home() / "units_profile.json"))
    diff_data = config.read_json(config.run_dir(run_id) / "diff.json")

    prepared = export_mod.prepare(
        run_id, rolled, meta, adams_map, transform_profile, units_profile, diff_data)

    (config.run_dir(run_id) / "preview.txt").write_text(prepared["preview_text"], encoding="utf-8")
    config.write_json(config.run_dir(run_id) / "approval.json", {
        "run_id": run_id,
        "token": prepared["token"],
        "created_at": config.now_iso(),
        "rows": prepared["rows"],
        "landmark_check": prepared["landmark_check"],
        "include_inertia": prepared["include_inertia"],
    })

    warnings = []
    if not prepared["include_inertia"]:
        warnings.append({"kind": "no_inertia",
                         "message_tr": "Atalet değerleri yazılmayacak, kalibrasyon eksik."})
    for row in prepared["rows"]:
        if row["inertia_skip_reason"] == "bucket_inertia_incomplete":
            warnings.append({"kind": "no_inertia_bucket",
                             "message_tr": f"{row['bucket']}: atalet eksik, yazılmayacak."})

    return ok(
        "preview",
        "Önizleme hazır. {} Adams parçası güncellenecek. Aşağıdaki metni "
        "kullanıcıya gösterin ve onay isteyin; onaylanmadan export çalıştırmayın.".format(
            len(prepared["rows"])),
        next_command=None,
        ask_user_tr=(
            "preview_text alanını kullanıcıya olduğu gibi gösterin ve "
            "'Bu değişiklikleri onaylıyor musunuz?' diye sorun. Kullanıcı "
            "onaylarsa command_after_approval alanındaki komutu SİZ "
            "çalıştırın. Kullanıcıya export komutunu yazmayın."),
        warnings=warnings,
        run_id=run_id,
        preview_text=prepared["preview_text"],
        approval_token=prepared["token"],
        command_after_approval=(
            f"python -m cmc export --run {run_id} --approve {prepared['token']}"),
        artifact=str(config.run_dir(run_id) / "preview.txt"),
    )


def cmd_export(args):
    run_id = _run_or_die(args.run, "export")
    approval = config.read_json(config.run_dir(run_id) / "approval.json")
    if not approval:
        raise CmcError(
            "E_NO_PREVIEW",
            "Bu ölçüm için önizleme üretilmemiş.",
            f"Önce `python -m cmc preview --run {run_id}` çalıştırın ve "
            "kullanıcıya gösterin.",
        )
    if args.approve != approval["token"]:
        raise CmcError(
            "E_APPROVAL",
            "Onay kodu eşleşmiyor, dosya yazılmadı.",
            "Onay kodu önizleme çıktısındaki kodla birebir aynı olmalı. "
            "Kod uydurulamaz; önizlemeyi kullanıcıya gösterip oradaki kodu kullanın.",
        )

    meta = config.read_json(config.run_dir(run_id) / "meta.json")
    rolled = config.read_json(config.run_dir(run_id) / "rollup.json")
    adams_map = config.read_json(config.home() / "adams_map.json")
    transform_profile = config.read_json(config.home() / "transform_profile.json")
    units_profile = units.load(config.read_json(config.home() / "units_profile.json"))
    diff_data = config.read_json(config.run_dir(run_id) / "diff.json")

    prepared = export_mod.prepare(
        run_id, rolled, meta, adams_map, transform_profile, units_profile, diff_data)
    if prepared["token"] != approval["token"]:
        raise CmcError(
            "E_STALE_APPROVAL",
            "Önizlemeden sonra veriler değişmiş, onay geçersiz.",
            f"`python -m cmc preview --run {run_id}` komutunu tekrar çalıştırın "
            "ve yeni önizlemeyi kullanıcıya gösterin.",
        )

    path = export_mod.write(run_id, prepared["cmd_text"])
    return ok(
        "export",
        "{} parça için Adams komut dosyası yazıldı: {}".format(len(prepared["rows"]), path),
        next_command=None,
        run_id=run_id,
        artifact=str(path),
        part_count=len(prepared["rows"]),
        inertia_written=prepared["include_inertia"],
    )


def cmd_show(args):
    run_id = _run_or_die(args.run, "show")
    rolled = _need(
        config.run_dir(run_id) / "rollup.json",
        "E_NO_ROLLUP", "Bu ölçüm için alt yapı toplamı hesaplanmamış.",
        f"Önce `python -m cmc rollup --run {run_id}` çalıştırın.",
    )
    lines = ["{:<24} {:>12} {:>14} {:>14} {:>14}".format(
        "ALT YAPI", "KUTLE [kg]", "X [mm]", "Y [mm]", "Z [mm]")]
    lines.append("-" * 82)
    for b in rolled["buckets"]:
        lines.append("{:<24} {:>12.3f} {:>14.4f} {:>14.4f} {:>14.4f}".format(
            b["name"][:24], b["mass_kg"], *b["cg_mm"]))
    for g in rolled["groups"]:
        lines.append("{:<24} {:>12.3f} {:>14.4f} {:>14.4f} {:>14.4f}".format(
            ("* " + g["name"])[:24], g["mass_kg"], *g["cg_mm"]))
    lines.append("-" * 82)
    t = rolled["totals"]
    lines.append("{:<24} {:>12.3f} {:>14.4f} {:>14.4f} {:>14.4f}".format(
        "TOPLAM", t["mass_kg"], *t["cg_mm"]))

    return ok(
        "show",
        "\n".join(lines),
        next_command=None,
        run_id=run_id,
        totals=t,
        checks=rolled["checks"],
    )


def cmd_history(args):
    rows = store.history(args.vehicle, args.variant, args.limit)
    if not rows:
        return ok("history", "Kayıtlı ölçüm yok.", next_command=None, measurements=[])
    lines = ["{} | {} | {} | {} | {:.3f} kg".format(
        r["run_id"], r["vehicle"], r["variant"], r["revision"], r["total_mass_kg"])
        for r in rows]
    return ok(
        "history",
        "\n".join(lines),
        next_command=None,
        measurements=[{k: r[k] for k in ("run_id", "vehicle", "variant", "revision",
                                         "measured_at", "total_mass_kg")} for r in rows],
    )


def cmd_selftest(args):
    from . import selftest

    results = selftest.run()
    failed = [r for r in results if not r["passed"]]
    if failed:
        raise CmcError(
            "E_SELFTEST",
            "{}/{} iç tutarlılık testi başarısız.".format(len(failed), len(results)),
            "Kurulum bozuk olabilir; başarısız testleri geliştiriciye iletin.",
            failures=failed,
        )
    return ok(
        "selftest",
        "{} iç tutarlılık testi geçti.".format(len(results)),
        next_command="python -m cmc doctor",
        results=[r["name"] for r in results],
    )


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="cmc", description="CATIA mass/CG pipeline")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)

    def add_source(sp):
        sp.add_argument("--source", choices=("catia", "fake"), default="catia",
                        help="fake: CATIA olmadan sentetik montajla çalışır")

    sp = sub.add_parser("doctor", help="ortam kontrolü")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("attach", help="açık CATIA oturumuna bağlan")
    add_source(sp)
    sp.set_defaults(func=cmd_attach)

    sp = sub.add_parser("calibrate", help="birim ve atalet konvansiyonunu ölç")
    sp.add_argument("--length", type=float, required=True)
    sp.add_argument("--width", type=float, required=True)
    sp.add_argument("--height", type=float, required=True)
    sp.add_argument("--density", type=float, required=True, help="kg/m^3")
    add_source(sp)
    sp.set_defaults(func=cmd_calibrate)

    sp = sub.add_parser("extract", help="montajı tara")
    sp.add_argument("--vehicle", required=True)
    sp.add_argument("--variant", required=True)
    sp.add_argument("--revision", required=True)
    sp.add_argument("--inject-faults", action="store_true",
                    help="sadece --source fake ile: hatalı parça senaryosu")
    add_source(sp)
    sp.set_defaults(func=cmd_extract)

    for name, func, helptext in (
        ("rollup", cmd_rollup, "alt yapı bazında topla ve doğrula"),
        ("diff", cmd_diff, "önceki revizyonla karşılaştır"),
        ("preview", cmd_preview, "değişiklik önizlemesi üret"),
        ("show", cmd_show, "sonuç tablosunu göster"),
    ):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("--run", default="last")
        sp.set_defaults(func=func)

    sp = sub.add_parser("export", help="onaydan sonra .cmd yaz")
    sp.add_argument("--run", default="last")
    sp.add_argument("--approve", required=True, help="önizlemedeki onay kodu")
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("history", help="kayıtlı ölçümler")
    sp.add_argument("--vehicle")
    sp.add_argument("--variant")
    sp.add_argument("--limit", type=int, default=20)
    sp.set_defaults(func=cmd_history)

    sp = sub.add_parser("selftest", help="iç tutarlılık testleri")
    sp.set_defaults(func=cmd_selftest)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except CmcError as err:
        err.step = args.command
        return fail(err)
    except KeyboardInterrupt:
        return fail(CmcError("E_INTERRUPTED", "İşlem kullanıcı tarafından durduruldu.", None))
    except Exception as exc:  # noqa: BLE001 - the agent must still get valid JSON
        return fail(CmcError(
            "E_UNEXPECTED",
            "Beklenmeyen hata: {}: {}".format(type(exc).__name__, exc),
            "Bu bir yazılım hatası olabilir. Komutu tekrar denemeyin, "
            "hatayı geliştiriciye iletin.",
        ))


if __name__ == "__main__":
    sys.exit(main())
