"""Connect the packaged CATIA mass/CG skill to the web application.

The command allowlist, channel separation and human approval gate remain in
the skill bundle's own harness. This service adds unpacking, per-user
workspaces, in-memory chat sessions and the Ollama tool-call loop.
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import os
import shlex
import shutil
import stat
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Callable

import httpx

from .. import config


logger = logging.getLogger(__name__)

SKILL_ARCHIVE_PATH = config.BASE_DIR / "skill" / "catia-mass-cg.skill"
RUNNER_MODULE_NAME = "ucak_catia_skill_runner"
MAX_SESSIONS = 32

WORKSPACE_SEED_FILES = {
    "subassembly_map.json": "subassembly_map.example.json",
    "transform_profile.json": "transform_profile.example.json",
    "adams_map.json": "adams_map.example.json",
}


class CatiaSkillUnavailableError(RuntimeError):
    """The bundle is missing, invalid or incompatible with the service."""


class CatiaSkillLLMError(RuntimeError):
    """Ollama could not be reached or returned an invalid response."""


class CatiaSkillBusyError(RuntimeError):
    """A turn is already running for the same session."""


def _repair_missing_cmc_subcommand(command: str) -> tuple[str, str | None]:
    """Repair only unambiguous option-only tool calls from small models."""
    stripped = str(command or "").strip()
    try:
        tokens = shlex.split(stripped)
    except ValueError:
        return stripped, None

    while tokens and tokens[0] in {"python", "python3", "py", "-m", "cmc"}:
        tokens.pop(0)
    if not tokens or not tokens[0].startswith("--"):
        return stripped, None

    flags = {token.split("=", 1)[0] for token in tokens if token.startswith("--")}
    subcommand = None
    if {"--vehicle", "--variant", "--revision"}.issubset(flags):
        subcommand = "run"
    elif {"--length", "--width", "--height", "--density"}.issubset(flags):
        subcommand = "calibrate"
    if subcommand is None:
        return stripped, None

    repaired = shlex.join([subcommand, *tokens])
    return repaired, f"Modelin eksik '{subcommand}' alt komutu güvenli biçimde tamamlandı."


def _archive_digest(archive_path: Path) -> str:
    return hashlib.sha256(archive_path.read_bytes()).hexdigest()


def _extract_skill_bundle(bundle: zipfile.ZipFile, target: Path) -> None:
    """Extract only regular files that remain below the target directory."""
    resolved_target = target.resolve()
    for member in bundle.infolist():
        member_path = Path(member.filename)
        destination = (resolved_target / member_path).resolve()
        unix_mode = member.external_attr >> 16
        if member_path.is_absolute() or ".." in member_path.parts:
            raise CatiaSkillUnavailableError("Skill paketi guvenli olmayan bir dosya yolu iceriyor.")
        if destination != resolved_target and resolved_target not in destination.parents:
            raise CatiaSkillUnavailableError("Skill paketi hedef klasorun disina cikmaya calisiyor.")
        if stat.S_ISLNK(unix_mode):
            raise CatiaSkillUnavailableError("Skill paketindeki sembolik baglantilar desteklenmiyor.")
    bundle.extractall(resolved_target)


def ensure_skill_unpacked(
    archive_path: Path | None = None,
    target_root: Path | None = None,
) -> Path:
    """Unpack the versioned skill bundle once and return its runtime path."""
    archive = archive_path or SKILL_ARCHIVE_PATH
    if not archive.is_file():
        raise CatiaSkillUnavailableError(f"Skill paketi bulunamadi: {archive}")

    root = target_root or (config.DATA_DIR / "skills")
    target = root / "catia-mass-cg"
    stamp = target / ".skill-hash"
    digest = _archive_digest(archive)

    if (
        stamp.is_file()
        and stamp.read_text(encoding="ascii").strip() == digest
        and (target / "SKILL.md").is_file()
    ):
        return target

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive) as bundle:
            _extract_skill_bundle(bundle, target)
    except zipfile.BadZipFile as exc:
        raise CatiaSkillUnavailableError(f"Skill paketi acilamadi: {archive}") from exc
    stamp.write_text(digest, encoding="ascii")
    logger.info("CATIA skill paketi acildi: %s (%s)", target, digest[:12])
    return target


def load_runner(skill_root: Path) -> ModuleType:
    """Load the command harness shipped inside the skill bundle."""
    runner_path = skill_root / "runner" / "agent.py"
    if not runner_path.is_file():
        raise CatiaSkillUnavailableError(f"Skill harness'i bulunamadi: {runner_path}")
    spec = importlib.util.spec_from_file_location(RUNNER_MODULE_NAME, runner_path)
    if spec is None or spec.loader is None:
        raise CatiaSkillUnavailableError(f"Skill harness'i yuklenemedi: {runner_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[RUNNER_MODULE_NAME] = module
    spec.loader.exec_module(module)
    for required in ("Gate", "dispatch", "for_model", "TOOLS"):
        if not hasattr(module, required):
            raise CatiaSkillUnavailableError(
                f"Skill harness'inda beklenen '{required}' yok; paket surumu uyumsuz."
            )
    # Windows may launch Python children with cp1252 stdout. The packaged CMC
    # emits Turkish JSON, so both ends of its subprocess channel must use UTF-8.
    def run_utf8(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess:
        child_env = dict(kwargs.get("env") or os.environ)
        child_env["PYTHONIOENCODING"] = "utf-8"
        child_env["PYTHONUTF8"] = "1"
        kwargs["env"] = child_env
        if kwargs.get("text") or kwargs.get("universal_newlines"):
            kwargs.setdefault("encoding", "utf-8")
        return subprocess.run(*args, **kwargs)

    module.subprocess = SimpleNamespace(
        run=run_utf8,
        TimeoutExpired=subprocess.TimeoutExpired,
    )
    return module


def _default_llm_client(
    host: str,
    model: str,
    messages: list[dict],
    tools: list[dict],
    timeout_seconds: float,
) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "top_p": 1, "seed": 0, "num_ctx": 8192},
    }
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(f"{host}/api/chat", json=payload)
            response.raise_for_status()
            message = response.json()["message"]
            if not isinstance(message, dict):
                raise ValueError("message alani nesne degil")
            return message
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise CatiaSkillLLMError(
            f"Ollama'ya ulasilamadi veya model yaniti okunamadi ({host}): {exc}"
        ) from exc


@dataclass
class CatiaSkillSession:
    session_id: str
    username: str
    workspace: Path
    messages: list[dict] = dataclass_field(default_factory=list)
    gate: Any = None
    last_state: str | None = None
    created_at: float = dataclass_field(default_factory=time.time)
    updated_at: float = dataclass_field(default_factory=time.time)
    lock: threading.Lock = dataclass_field(default_factory=threading.Lock)


class CatiaSkillService:
    """Run a stateful, tool-calling CATIA skill conversation."""

    def __init__(
        self,
        *,
        archive_path: Path | None = None,
        skill_target_root: Path | None = None,
        workspace_root: Path | None = None,
        fake: bool | None = None,
        model_name: str | None = None,
        ollama_host: str | None = None,
        llm_client: Callable[..., dict] | None = None,
        llm_timeout_seconds: float | None = None,
        cmc_timeout_seconds: float | None = None,
        max_steps: int | None = None,
        max_nudges: int | None = None,
    ) -> None:
        self.skill_root = ensure_skill_unpacked(archive_path, skill_target_root)
        self.runner = load_runner(self.skill_root)
        self.workspace_root = Path(workspace_root or config.CATIA_SKILL_WORKSPACE_ROOT)
        self.fake = config.CATIA_SKILL_SOURCE == "fake" if fake is None else fake
        self.model_name = model_name or config.CATIA_SKILL_MODEL_NAME
        self.ollama_host = ollama_host or config.OLLAMA_HOST
        self.llm_client = llm_client or _default_llm_client
        self.llm_timeout_seconds = (
            config.CATIA_SKILL_LLM_TIMEOUT_SECONDS
            if llm_timeout_seconds is None
            else llm_timeout_seconds
        )
        self.cmc_timeout_seconds = (
            config.CATIA_SKILL_CMC_TIMEOUT_SECONDS
            if cmc_timeout_seconds is None
            else cmc_timeout_seconds
        )
        self.max_steps = config.CATIA_SKILL_MAX_STEPS if max_steps is None else max_steps
        self.max_nudges = config.CATIA_SKILL_MAX_NUDGES if max_nudges is None else max_nudges
        self.system_prompt = (self.skill_root / "SKILL.md").read_text(encoding="utf-8")
        self._sessions: dict[str, CatiaSkillSession] = {}
        self._sessions_lock = threading.Lock()

    def _workspace_for(self, username: str) -> Path:
        safe = "".join(char if char.isalnum() or char in "-_." else "_" for char in username) or "local"
        workspace = self.workspace_root / safe
        workspace.mkdir(parents=True, exist_ok=True)
        for target_name, example_name in WORKSPACE_SEED_FILES.items():
            target = workspace / target_name
            example = self.skill_root / "assets" / example_name
            if not target.exists() and example.is_file():
                shutil.copyfile(example, target)
        return workspace

    def _new_session(self, username: str) -> CatiaSkillSession:
        session = CatiaSkillSession(
            session_id=uuid.uuid4().hex,
            username=username,
            workspace=self._workspace_for(username),
            messages=[{"role": "system", "content": self.system_prompt}],
            gate=self.runner.Gate(auto=False, interactive=False),
        )
        with self._sessions_lock:
            while len(self._sessions) >= MAX_SESSIONS:
                oldest = min(self._sessions.values(), key=lambda item: item.updated_at)
                del self._sessions[oldest.session_id]
            self._sessions[session.session_id] = session
        return session

    def _get_session(self, session_id: str, username: str) -> CatiaSkillSession:
        with self._sessions_lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise ValueError("Oturum bulunamadi veya suresi doldu; yeni bir sohbet baslatin.")
        if session.username != username:
            raise ValueError("Bu oturum baska bir kullaniciya ait.")
        return session

    def reset(self, session_id: str, username: str) -> None:
        session = self._get_session(session_id, username)
        with self._sessions_lock:
            self._sessions.pop(session.session_id, None)

    def chat(self, message: str, *, session_id: str | None = None, username: str = "local") -> dict:
        session = self._get_session(session_id, username) if session_id else self._new_session(username)
        if not session.lock.acquire(blocking=False):
            raise CatiaSkillBusyError("Bu oturumda suren bir istek var; bitmesini bekleyin.")
        try:
            events = self._chat_turn(session, message.strip())
            session.updated_at = time.time()
            return self._response(session, events)
        finally:
            session.lock.release()

    def run_shortcut(
        self,
        shortcut: str,
        *,
        message: str,
        session_id: str | None = None,
        username: str = "local",
    ) -> dict:
        """Run a UI-owned, argument-free command without LLM interpretation."""
        commands = {"doctor": "doctor", "history": "history", "selftest": "selftest"}
        command = commands.get(shortcut)
        if command is None:
            raise ValueError("Desteklenmeyen CATIA skill kisayolu.")
        session = self._get_session(session_id, username) if session_id else self._new_session(username)
        if not session.lock.acquire(blocking=False):
            raise CatiaSkillBusyError("Bu oturumda suren bir istek var; bitmesini bekleyin.")
        try:
            clean_message = message.strip()
            session.gate.note_user(clean_message)
            session.messages.append({"role": "user", "content": clean_message})
            session.messages.append(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "run_cmc",
                                "arguments": {"command": f"python -m cmc {command}"},
                            }
                        }
                    ],
                }
            )
            events: list[dict] = []
            self._dispatch(session, command, events)
            session.updated_at = time.time()
            return self._response(session, events)
        finally:
            session.lock.release()

    def approve_and_export(self, session_id: str, *, username: str = "local") -> dict:
        """Approve the exact visible preview and export deterministically."""
        session = self._get_session(session_id, username)
        if not session.lock.acquire(blocking=False):
            raise CatiaSkillBusyError("Bu oturumda suren bir istek var; bitmesini bekleyin.")
        try:
            if not session.gate.pending_run_id:
                raise ValueError("Onaylanacak bir onizleme yok; once olcum yapin.")
            session.gate.approved_run_id = session.gate.pending_run_id
            events: list[dict] = []
            result, _ = self._dispatch(session, "export --run last", events)
            session.messages.append(
                {
                    "role": "user",
                    "content": (
                        "[harness] Kullanici ekrandaki onizlemeyi onayladi; "
                        f"aktarim sonucu: {result.get('status', '')} {result.get('message_tr', '')}"
                    ),
                }
            )
            session.updated_at = time.time()
            return self._response(session, events)
        finally:
            session.lock.release()

    def status(self) -> dict:
        with self._sessions_lock:
            session_count = len(self._sessions)
        return {
            "source": "fake" if self.fake else "catia",
            "model": self.model_name,
            "ollama_host": self.ollama_host,
            "skill_root": str(self.skill_root),
            "workspace_root": str(self.workspace_root),
            "sessions": session_count,
        }

    def _chat_turn(self, session: CatiaSkillSession, user_text: str) -> list[dict]:
        events: list[dict] = []
        session.gate.note_user(user_text)
        session.messages.append({"role": "user", "content": user_text})

        nudges = 0
        blanks = 0
        for _ in range(self.max_steps):
            message = self.llm_client(
                self.ollama_host,
                self.model_name,
                session.messages,
                tools=self.runner.TOOLS,
                timeout_seconds=self.llm_timeout_seconds,
            )
            if not isinstance(message, dict):
                raise CatiaSkillLLMError("Model yaniti beklenen nesne biciminde degil.")
            session.messages.append(message)

            tool_calls = message.get("tool_calls") or []
            content = (message.get("content") or "").strip()
            if content and not tool_calls:
                events.append({"kind": "model", "text": content})

            if not tool_calls and not content:
                blanks += 1
                if blanks <= self.max_nudges:
                    session.messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Bos yanit verdin. Siradaki cmc komutunu run_cmc araci ile calistir "
                                "veya eksik bilgiyi kullanicidan iste."
                            ),
                        }
                    )
                    continue
                events.append(
                    {
                        "kind": "harness",
                        "text": "Model yanit uretmiyor; daha guclu bir tool-calling model deneyin.",
                    }
                )
                break

            if not tool_calls:
                if (
                    session.gate.approved_run_id
                    and session.last_state == "PREVIEW_READY"
                    and nudges < self.max_nudges
                ):
                    nudges += 1
                    events.append({"kind": "harness", "text": f"Hatirlatma {nudges}: export cagrilmadi."})
                    session.messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Onayi verdim. Simdi run_cmc ile `python -m cmc export --run last` "
                                "komutunu calistir; kullaniciya komut yazma."
                            ),
                        }
                    )
                    continue
                break

            nudges = 0
            for tool_call in tool_calls:
                function = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
                arguments = function.get("arguments") or {}
                command = arguments.get("command", "") if isinstance(arguments, dict) else ""
                repaired_command, repair_note = _repair_missing_cmc_subcommand(str(command))
                if repair_note:
                    events.append({"kind": "harness", "text": repair_note})
                self._dispatch(session, repaired_command, events)
        return events

    def _dispatch(
        self,
        session: CatiaSkillSession,
        command: str,
        events: list[dict],
    ) -> tuple[dict, str | None]:
        events.append({"kind": "command", "text": command})
        args = SimpleNamespace(fake=self.fake, timeout=self.cmc_timeout_seconds)
        result, preview_text = self.runner.dispatch(
            command,
            session.workspace,
            str(self.skill_root),
            args,
            session.gate,
        )
        events.append(
            {
                "kind": "result",
                "status": str(result.get("status") or ""),
                "state": str(result.get("state") or ""),
                "code": str(result.get("code") or ""),
                "message_tr": str(result.get("message_tr") or ""),
                "hint_tr": str(result.get("hint_tr") or ""),
            }
        )
        if preview_text:
            events.append({"kind": "screen", "text": str(preview_text)})
        session.messages.append({"role": "tool", "content": self.runner.for_model(result)})
        session.last_state = result.get("state")
        session.gate.note_result(result)
        return result, preview_text

    @staticmethod
    def _response(session: CatiaSkillSession, events: list[dict]) -> dict:
        return {
            "session_id": session.session_id,
            "events": events,
            "state": session.last_state,
            "approval_pending": bool(
                session.gate.pending_run_id
                and session.gate.approved_run_id != session.gate.pending_run_id
                and session.last_state == "PREVIEW_READY"
            ),
            "pending_run_id": session.gate.pending_run_id,
        }


_service_lock = threading.Lock()
_service: CatiaSkillService | None = None


def get_catia_skill_service() -> CatiaSkillService:
    global _service
    with _service_lock:
        if _service is None:
            _service = CatiaSkillService()
        return _service
