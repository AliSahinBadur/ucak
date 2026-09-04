from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.services.catia_skill_service import (
    CatiaSkillService,
    ensure_skill_unpacked,
    load_runner,
)


class SkillBundleTests(unittest.TestCase):
    def test_unpack_and_load_runner(self) -> None:
        with TemporaryDirectory() as temp_dir:
            skill_root = ensure_skill_unpacked(target_root=Path(temp_dir))
            self.assertTrue((skill_root / "SKILL.md").is_file())
            self.assertTrue((skill_root / "cmc" / "cli.py").is_file())
            runner = load_runner(skill_root)
            self.assertTrue(hasattr(runner, "dispatch"))

            # Ikinci cagri yeniden acmamali (hash damgasi tutuyor).
            stamp = (skill_root / ".skill-hash").read_text(encoding="ascii")
            skill_root_again = ensure_skill_unpacked(target_root=Path(temp_dir))
            self.assertEqual(skill_root, skill_root_again)
            self.assertEqual(stamp, (skill_root / ".skill-hash").read_text(encoding="ascii"))

    def test_harness_gates_block_bad_commands(self) -> None:
        with TemporaryDirectory() as temp_dir:
            runner = load_runner(ensure_skill_unpacked(target_root=Path(temp_dir)))

            with self.assertRaises(runner.Blocked):
                runner.validate("rm -rf /")
            with self.assertRaises(runner.Blocked):
                runner.validate("python -m cmc run --vehicle <ARAC> --variant BASE --revision R01")
            with self.assertRaises(runner.Blocked):
                runner.validate("python -m cmc export --run last --inject-faults x")

            # Modelin uydurdugu --approve sessizce atilir; onayi harness ekler.
            sub, argv = runner.validate("python -m cmc export --run last --approve deadbeef")
            self.assertEqual("export", sub)
            self.assertNotIn("--approve", argv)

    def test_source_flag_is_normalised_not_blocked(self) -> None:
        """Model `--source` yazdiginda tur olmemeli: kaynagi ortam secer.

        `doctor`/`history` bu argumani hic tanimiyor, `run` ise ortamin
        sectigi kaynakla calismali; ikisinde de model komutu bloklanmiyor,
        duzeltiliyor."""
        with TemporaryDirectory() as temp_dir:
            runner = load_runner(ensure_skill_unpacked(target_root=Path(temp_dir)))

            sub, argv = runner.validate("python -m cmc doctor --source fake", force_source="fake")
            self.assertEqual("doctor", sub)
            self.assertNotIn("--source", argv)

            sub, argv = runner.validate("python -m cmc history --source fake", force_source="fake")
            self.assertEqual("history", sub)
            self.assertNotIn("--source", argv)

            # Model kaynagi degistiremez: fake kurulumda --source catia da fake olur.
            _, argv = runner.validate(
                "python -m cmc run --vehicle ARAC-X --variant BASE --revision R04 --source catia",
                force_source="fake")
            self.assertEqual(["--source", "fake"], argv[-2:])
            self.assertEqual(1, argv.count("--source"))

            # `--flag=deger` yazimi da ayni komut sayilir.
            _, argv = runner.validate(
                "python -m cmc run --vehicle=ARAC-X --variant=BASE --revision=R04",
                force_source="fake")
            self.assertIn("ARAC-X", argv)
            self.assertNotIn("--vehicle=ARAC-X", argv)

            # Uydurulan argumanlar hala bloklu ve hata izinlileri sayiyor.
            with self.assertRaises(runner.Blocked) as blocked:
                runner.validate("python -m cmc calibrate --block 100x50x25 --density 7850")
            self.assertIn("--length", str(blocked.exception))

    def test_approval_word_gate(self) -> None:
        with TemporaryDirectory() as temp_dir:
            runner = load_runner(ensure_skill_unpacked(target_root=Path(temp_dir)))
            self.assertTrue(runner.reads_as_approval("evet"))
            self.assertTrue(runner.reads_as_approval("Sonuçları kontrol ettim, onaylıyorum."))
            self.assertFalse(runner.reads_as_approval("onaylandı mı?"))
            self.assertFalse(runner.reads_as_approval("evet ama önce dur"))


class CatiaSkillServiceTests(unittest.TestCase):
    """Servis dongusunu skill paketindeki stub senaryolariyla surer:
    gercek Ollama yok, cmc --source fake ile gercek alt surec var."""

    def _service(self, temp_dir: str, stub_name: str) -> CatiaSkillService:
        skill_root = ensure_skill_unpacked(target_root=Path(temp_dir) / "skills")
        runner = load_runner(skill_root)
        stub = runner.StubClient(skill_root / "runner" / stub_name)

        def stub_client(host, model, messages, **kw):
            return stub(host, model, messages, **kw)

        return CatiaSkillService(
            skill_target_root=Path(temp_dir) / "skills",
            workspace_root=Path(temp_dir) / "ws",
            fake=True,
            llm_client=stub_client,
            max_steps=12,
            max_nudges=1,
        )

    def test_misbehaving_model_is_blocked(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = self._service(temp_dir, "stub-misbehaving.jsonl")

            first = service.chat("kütle çıkar")
            second = service.chat("150x80x40", session_id=first["session_id"])

            events = first["events"] + second["events"]
            codes = [item.get("code") for item in events if item["kind"] == "result"]
            commands = [item["text"] for item in events if item["kind"] == "command"]

            # Yer tutucu, kabuk komutu ve izinsiz alt komut engellenmeli.
            self.assertIn("E_BLOCKED", codes)
            self.assertTrue(any("rm -rf" in command for command in commands))
            # Onaysiz export durmali: taze workspace'te E_NO_PREVIEW,
            # onizlemesi olan workspace'te E_NOT_APPROVED_BY_HUMAN.
            self.assertTrue({"E_NO_PREVIEW", "E_NOT_APPROVED_BY_HUMAN"} & set(codes))
            # Reddedilen yazma diske de yansimamali.
            workspace = Path(temp_dir) / "ws" / "local"
            self.assertEqual([], list(workspace.glob("runs/*/export.cmd")))

    def test_a_second_measurement_waits_instead_of_racing_catia(self) -> None:
        """Uclar artik LAN'a acik: iki oturum ayni anda olcum isteyebilir.
        CATIA tek COM ornegi oldugu icin ikinci komut calismamali, modele
        okunur bir E_BUSY donmeli ve diske hicbir sey yazilmamali."""
        with TemporaryDirectory() as temp_dir:
            service = self._service(temp_dir, "stub-onay-akisi.jsonl")
            self.assertTrue(service._cmc_lock.acquire(blocking=False))
            try:
                turn = service.chat("araç montajından kütle çıkar, ARAC-X / BASE / R04")
            finally:
                service._cmc_lock.release()

            codes = [item.get("code") for item in turn["events"] if item["kind"] == "result"]
            self.assertIn("E_BUSY", codes)
            self.assertEqual([], list((Path(temp_dir) / "ws").glob("*/runs/*")))

    def test_preview_and_button_approval_exports(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = self._service(temp_dir, "stub-onay-akisi.jsonl")

            # Kalibrasyonu deterministik hazirla (stub senaryosu dogrudan
            # `run` ile basliyor).
            import subprocess
            import sys

            workspace = Path(temp_dir) / "ws" / "local"
            workspace.mkdir(parents=True, exist_ok=True)
            for name, example in {
                "subassembly_map.json": "subassembly_map.example.json",
                "transform_profile.json": "transform_profile.example.json",
                "adams_map.json": "adams_map.example.json",
            }.items():
                (workspace / name).write_bytes(
                    (service.skill_root / "assets" / example).read_bytes()
                )
            import os

            env = dict(os.environ)
            env["PYTHONPATH"] = str(service.skill_root) + os.pathsep + env.get("PYTHONPATH", "")
            calibrate = subprocess.run(
                [
                    sys.executable, "-m", "cmc", "calibrate",
                    "--length", "150", "--width", "80", "--height", "40",
                    "--density", "7850", "--source", "fake",
                ],
                cwd=str(workspace),
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(0, calibrate.returncode, calibrate.stderr)

            first = service.chat("araç montajından kütle çıkar, ARAC-X / BASE / R04")
            self.assertEqual("PREVIEW_READY", first["state"])
            self.assertTrue(first["approval_pending"])
            self.assertTrue(any(item["kind"] == "screen" for item in first["events"]))
            # Onay kodu modelin baglamina girmemeli.
            for message in service._sessions[first["session_id"]].messages:
                if message.get("role") == "tool":
                    self.assertNotIn("approval_token", message.get("content", ""))
                    self.assertNotIn("preview_text", message.get("content", ""))

            approved = service.approve_and_export(first["session_id"])
            result_events = [item for item in approved["events"] if item["kind"] == "result"]
            self.assertTrue(result_events)
            self.assertEqual("ok", result_events[-1]["status"])
            self.assertFalse(approved["approval_pending"])
            exports = list(workspace.glob("runs/*/export.cmd"))
            self.assertEqual(1, len(exports))

            # Word-gate onayi export ile tuketildi: model bir sonraki turda
            # kendi basina tekrar export cagirirsa kapi kapali olmali.
            session = service._sessions[first["session_id"]]
            self.assertIsNone(session.gate.approved_run_id)


if __name__ == "__main__":
    unittest.main()
