from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from app.services.catia_skill_service import (
    CatiaSkillService,
    ensure_skill_unpacked,
    load_runner,
)


def test_unpack_and_load_runner(tmp_path: Path) -> None:
    skill_root = ensure_skill_unpacked(target_root=tmp_path)
    assert (skill_root / "SKILL.md").is_file()
    assert (skill_root / "cmc" / "cli.py").is_file()
    runner = load_runner(skill_root)
    assert hasattr(runner, "dispatch")

    stamp = (skill_root / ".skill-hash").read_text(encoding="ascii")
    assert ensure_skill_unpacked(target_root=tmp_path) == skill_root
    assert (skill_root / ".skill-hash").read_text(encoding="ascii") == stamp


def test_harness_blocks_unsafe_commands(tmp_path: Path) -> None:
    runner = load_runner(ensure_skill_unpacked(target_root=tmp_path))

    for command in (
        "rm -rf /",
        "python -m cmc run --vehicle <ARAC> --variant BASE --revision R01",
        "python -m cmc export --run last --inject-faults x",
    ):
        try:
            runner.validate(command)
        except runner.Blocked:
            continue
        raise AssertionError(f"Unsafe command was accepted: {command}")

    subcommand, argv = runner.validate("python -m cmc export --run last --approve deadbeef")
    assert subcommand == "export"
    assert "--approve" not in argv


def test_source_flag_is_normalised_not_blocked(tmp_path: Path) -> None:
    runner = load_runner(ensure_skill_unpacked(target_root=tmp_path))

    subcommand, argv = runner.validate("python -m cmc doctor --source fake", force_source="fake")
    assert subcommand == "doctor"
    assert "--source" not in argv

    subcommand, argv = runner.validate("python -m cmc history --source fake", force_source="fake")
    assert subcommand == "history"
    assert "--source" not in argv

    _, argv = runner.validate(
        "python -m cmc run --vehicle ARAC-X --variant BASE --revision R04 --source catia",
        force_source="fake",
    )
    assert argv[-2:] == ["--source", "fake"]
    assert argv.count("--source") == 1

    _, argv = runner.validate(
        "python -m cmc run --vehicle=ARAC-X --variant=BASE --revision=R04",
        force_source="fake",
    )
    assert "ARAC-X" in argv
    assert "--vehicle=ARAC-X" not in argv

    try:
        runner.validate("python -m cmc calibrate --block 100x50x25 --density 7850")
    except runner.Blocked as error:
        assert "--length" in str(error)
    else:
        raise AssertionError("Unknown calibrate arguments were accepted")


def test_approval_word_gate_is_fail_closed(tmp_path: Path) -> None:
    runner = load_runner(ensure_skill_unpacked(target_root=tmp_path))
    assert runner.reads_as_approval("evet")
    assert runner.reads_as_approval("Sonuclari kontrol ettim, onayliyorum.")
    assert not runner.reads_as_approval("onaylandi mi?")
    assert not runner.reads_as_approval("evet ama once dur")


def _stub_service(temp_dir: Path, stub_name: str) -> CatiaSkillService:
    skill_root = ensure_skill_unpacked(target_root=temp_dir / "skills")
    runner = load_runner(skill_root)
    stub = runner.StubClient(skill_root / "runner" / stub_name)

    def stub_client(host, model, messages, **kwargs):
        return stub(host, model, messages, **kwargs)

    return CatiaSkillService(
        skill_target_root=temp_dir / "skills",
        workspace_root=temp_dir / "ws",
        fake=True,
        llm_client=stub_client,
        max_steps=12,
        max_nudges=1,
    )


def test_misbehaving_model_cannot_export(tmp_path: Path) -> None:
    service = _stub_service(tmp_path, "stub-misbehaving.jsonl")
    first = service.chat("kutle cikar")
    second = service.chat("150x80x40", session_id=first["session_id"])

    events = first["events"] + second["events"]
    codes = [item.get("code") for item in events if item["kind"] == "result"]
    commands = [item["text"] for item in events if item["kind"] == "command"]
    assert "E_BLOCKED" in codes
    assert any("rm -rf" in command for command in commands)
    assert {"E_NO_PREVIEW", "E_NOT_APPROVED_BY_HUMAN"} & set(codes)
    workspace = tmp_path / "ws" / "local"
    assert list(workspace.glob("runs/*/export.cmd")) == []


def test_visible_preview_requires_button_approval_before_export(tmp_path: Path) -> None:
    service = _stub_service(tmp_path, "stub-onay-akisi.jsonl")
    workspace = tmp_path / "ws" / "local"
    workspace.mkdir(parents=True, exist_ok=True)
    for name, example in {
        "subassembly_map.json": "subassembly_map.example.json",
        "transform_profile.json": "transform_profile.example.json",
        "adams_map.json": "adams_map.example.json",
    }.items():
        (workspace / name).write_bytes((service.skill_root / "assets" / example).read_bytes())

    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(service.skill_root) + os.pathsep + environment.get("PYTHONPATH", "")
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"
    calibrate = subprocess.run(
        [
            sys.executable,
            "-m",
            "cmc",
            "calibrate",
            "--length",
            "150",
            "--width",
            "80",
            "--height",
            "40",
            "--density",
            "7850",
            "--source",
            "fake",
        ],
        cwd=str(workspace),
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert calibrate.returncode == 0, calibrate.stderr

    preview = service.chat("ARAC-X / BASE / R04 montajindan kutle cikar")
    assert preview["state"] == "PREVIEW_READY"
    assert preview["approval_pending"] is True
    assert any(item["kind"] == "screen" for item in preview["events"])
    for message in service._sessions[preview["session_id"]].messages:
        if message.get("role") == "tool":
            assert "approval_token" not in message.get("content", "")
            assert "preview_text" not in message.get("content", "")

    approved = service.approve_and_export(preview["session_id"])
    result_events = [item for item in approved["events"] if item["kind"] == "result"]
    assert result_events[-1]["status"] == "ok"
    assert approved["approval_pending"] is False
    assert len(list(workspace.glob("runs/*/export.cmd"))) == 1
    assert service._sessions[preview["session_id"]].gate.approved_run_id is None
