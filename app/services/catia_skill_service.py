"""CATIA kütle/CG skill'ini (skill/catia-mass-cg.skill) web uygulamasına bağlar.

Güvenlik kapıları (komut izin listesi, yer tutucu kontrolü, insan onay kapısı,
kanal ayrımı) burada YENİDEN yazılmaz: skill paketinin kendi harness'ı
(runner/agent.py) çalışma anında paketten açılır ve `validate`, `dispatch`,
`Gate`, `for_model` oradan içe aktarılır. Böylece skill dosyası güncellenince
kapılar da onunla birlikte güncellenir ve tek kaynaktan gelir.

Bu servis yalnızca şunları ekler:
- .skill arşivini DATA_DIR/skills altına (hash damgalı) açmak
- oturum yönetimi (mesaj geçmişi + onay kapısı durumu, kullanıcı başına workspace)
- Ollama'ya araç çağrılı sohbet isteği (httpx ile, sunucuyu düşürmeden)
- ekran kanalı olaylarını (önizleme tablosu, komut satırları) UI'ya taşımak
- onay düğmesi için deterministik export yolu (model davranışına bağlı değil)
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import shutil
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

from ..config import BASE_DIR, get_settings


logger = logging.getLogger(__name__)

SKILL_ARCHIVE_PATH = BASE_DIR / "skill" / "catia-mass-cg.skill"
RUNNER_MODULE_NAME = "ucak_catia_skill_runner"
MAX_SESSIONS = 32

# Workspace ilk kurulurken assets/ içindeki örneklerden kopyalanan ayar
# dosyaları. units_profile.json bilerek burada YOK: o ölçümle (calibrate)
# üretilir, elle veya kopyayla yazılmaz (SKILL.md, "Ayar dosyaları").
WORKSPACE_SEED_FILES = {
    "subassembly_map.json": "subassembly_map.example.json",
    "transform_profile.json": "transform_profile.example.json",
    "adams_map.json": "adams_map.example.json",
}


class CatiaSkillUnavailableError(RuntimeError):
    """Skill paketi yok, açılamadı veya harness yüklenemedi."""


class CatiaSkillLLMError(RuntimeError):
    """Ollama'ya ulaşılamadı veya model yanıtı okunamadı."""


class CatiaSkillBusyError(RuntimeError):
    """Aynı oturumda halen süren bir sohbet turu var."""


def _archive_digest(archive_path: Path) -> str:
    return hashlib.sha256(archive_path.read_bytes()).hexdigest()


def ensure_skill_unpacked(
    archive_path: Path | None = None,
    target_root: Path | None = None,
) -> Path:
    """Skill arşivini çalışma dizinine açar; hash tutuyorsa yeniden açmaz."""
    archive = archive_path or SKILL_ARCHIVE_PATH
    if not archive.is_file():
        raise CatiaSkillUnavailableError(f"Skill paketi bulunamadı: {archive}")

    root = target_root or (get_settings().DATA_DIR / "skills")
    target = root / "catia-mass-cg"
    stamp = target / ".skill-hash"
    digest = _archive_digest(archive)

    if stamp.is_file() and stamp.read_text(encoding="ascii").strip() == digest and (
        target / "SKILL.md"
    ).is_file():
        return target

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(target)
    except zipfile.BadZipFile as exc:
        raise CatiaSkillUnavailableError(f"Skill paketi açılamadı: {archive}") from exc
    stamp.write_text(digest, encoding="ascii")
    logger.info("CATIA skill paketi açıldı: %s (%s)", target, digest[:12])
    return target


def load_runner(skill_root: Path) -> ModuleType:
    """Paketin kendi harness'ını (runner/agent.py) modül olarak yükler."""
    runner_path = skill_root / "runner" / "agent.py"
    if not runner_path.is_file():
        raise CatiaSkillUnavailableError(f"Skill harness'ı bulunamadı: {runner_path}")
    spec = importlib.util.spec_from_file_location(RUNNER_MODULE_NAME, runner_path)
    if spec is None or spec.loader is None:
        raise CatiaSkillUnavailableError(f"Skill harness'ı yüklenemedi: {runner_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[RUNNER_MODULE_NAME] = module
    spec.loader.exec_module(module)
    for required in ("Gate", "dispatch", "for_model", "TOOLS"):
        if not hasattr(module, required):
            raise CatiaSkillUnavailableError(
                f"Skill harness'ında beklenen '{required}' yok; paket sürümü uyumsuz."
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
            return response.json()["message"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise CatiaSkillLLMError(
            f"Ollama'ya ulaşılamadı veya model yanıtı okunamadı ({host}): {exc}"
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
    """Oturumlu, araç çağrılı CATIA skill sohbeti.

    Bir kez kurulur (get_catia_skill_service) ve istekler arasında oturumları
    bellekte tutar. Oturum durumu diskte değil bellekte: sunucu yeniden
    başlarsa sohbet sıfırlanır ama ölçümler (runs/, memory.sqlite) workspace'te
    kalır ve `history` ile geri gelir.
    """

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
        settings = get_settings()
        self.skill_root = ensure_skill_unpacked(archive_path, skill_target_root)
        self.runner = load_runner(self.skill_root)
        self.workspace_root = Path(workspace_root or settings.CATIA_SKILL_WORKSPACE_ROOT)
        self.fake = settings.CATIA_SKILL_SOURCE == "fake" if fake is None else fake
        self.model_name = model_name or settings.CATIA_SKILL_MODEL_NAME
        self.ollama_host = ollama_host or settings.OLLAMA_HOST
        self.llm_client = llm_client or _default_llm_client
        self.llm_timeout_seconds = (
            settings.CATIA_SKILL_LLM_TIMEOUT_SECONDS if llm_timeout_seconds is None else llm_timeout_seconds
        )
        self.cmc_timeout_seconds = (
            settings.CATIA_SKILL_CMC_TIMEOUT_SECONDS if cmc_timeout_seconds is None else cmc_timeout_seconds
        )
        self.max_steps = settings.CATIA_SKILL_MAX_STEPS if max_steps is None else max_steps
        self.max_nudges = settings.CATIA_SKILL_MAX_NUDGES if max_nudges is None else max_nudges
        self.system_prompt = (self.skill_root / "SKILL.md").read_text(encoding="utf-8")
        self._sessions: dict[str, CatiaSkillSession] = {}
        self._sessions_lock = threading.Lock()

    # -- oturumlar ----------------------------------------------------------

    def _workspace_for(self, username: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in username) or "local"
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
            raise ValueError("Oturum bulunamadı veya süresi doldu; yeni bir sohbet başlatın.")
        if session.username != username:
            raise ValueError("Bu oturum başka bir kullanıcıya ait.")
        return session

    def reset(self, session_id: str, username: str) -> None:
        session = self._get_session(session_id, username)
        with self._sessions_lock:
            self._sessions.pop(session.session_id, None)

    # -- sohbet döngüsü ------------------------------------------------------

    def chat(self, message: str, *, session_id: str | None = None, username: str = "local") -> dict:
        session = (
            self._get_session(session_id, username) if session_id else self._new_session(username)
        )
        if not session.lock.acquire(blocking=False):
            raise CatiaSkillBusyError("Bu oturumda süren bir istek var; bitmesini bekleyin.")
        try:
            events = self._chat_turn(session, message.strip())
            session.updated_at = time.time()
            return self._response(session, events)
        finally:
            session.lock.release()

    def approve_and_export(self, session_id: str, *, username: str = "local") -> dict:
        """Onay düğmesi: ekrandaki bekleyen önizlemeyi onaylar ve export'u
        harness üzerinden DETERMİNİSTİK çalıştırır. Modelin export'u çağırmayı
        akıl etmesine bağlı değildir; kapı yine harness'ta kontrol edilir
        (run_id eşlemesi, onay kodu diskten, E_STALE_APPROVAL cmc'de)."""
        session = self._get_session(session_id, username)
        if not session.lock.acquire(blocking=False):
            raise CatiaSkillBusyError("Bu oturumda süren bir istek var; bitmesini bekleyin.")
        try:
            if not session.gate.pending_run_id:
                raise ValueError("Onaylanacak bir önizleme yok; önce ölçüm yapın.")
            session.gate.approved_run_id = session.gate.pending_run_id
            events: list[dict] = []
            command = "export --run last"
            result, preview_text = self._dispatch(session, command, events)
            note = (
                "[harness] Kullanıcı ekrandaki önizlemeyi onay düğmesiyle onayladı; "
                f"aktarım çalıştırıldı. Sonuç: {result.get('status', '')} "
                f"{result.get('message_tr', '')}"
            )
            session.messages.append({"role": "user", "content": note})
            session.updated_at = time.time()
            return self._response(session, events)
        finally:
            session.lock.release()

    def status(self) -> dict:
        settings = get_settings()
        with self._sessions_lock:
            session_count = len(self._sessions)
        return {
            "enabled": settings.CATIA_SKILL_ENABLED,
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
            msg = self.llm_client(
                self.ollama_host,
                self.model_name,
                session.messages,
                tools=self.runner.TOOLS,
                timeout_seconds=self.llm_timeout_seconds,
            )
            session.messages.append(msg)

            tool_calls = msg.get("tool_calls") or []
            content = (msg.get("content") or "").strip()
            if content:
                events.append({"kind": "model", "text": content})

            if not tool_calls and not content:
                blanks += 1
                if blanks <= self.max_nudges:
                    session.messages.append({"role": "user", "content": (
                        "Boş yanıt verdin. Ne yapman gerektiğini SKILL.md söylüyor: "
                        "sıradaki cmc komutunu run_cmc aracıyla çalıştır, ya da bilgi "
                        "gerekiyorsa kullanıcıya sor."
                    )})
                    continue
                events.append({"kind": "harness", "text": (
                    "Model yanıt üretemiyor. Daha büyük bir model veya daha yüksek "
                    "nicemleme gerekebilir (runner/README.md, 'Model başarısız olursa')."
                )})
                break

            if not tool_calls:
                if (
                    session.gate.approved_run_id
                    and session.last_state == "PREVIEW_READY"
                    and nudges < self.max_nudges
                ):
                    nudges += 1
                    events.append({"kind": "harness", "text": f"Hatırlatma {nudges}: export çağrılmadı."})
                    session.messages.append({"role": "user", "content": (
                        "Onayı verdim. Şimdi run_cmc aracıyla "
                        "`python -m cmc export --run last` komutunu çalıştır. "
                        "Bana komut yazma, kullanıcı komut çalıştırmıyor."
                    )})
                    continue
                break

            nudges = 0
            for call in tool_calls:
                command = (call.get("function", {}).get("arguments") or {}).get("command", "")
                if not isinstance(command, str):
                    command = str(command)
                self._dispatch(session, command, events)
        return events

    def _dispatch(self, session: CatiaSkillSession, command: str, events: list[dict]) -> tuple[dict, str | None]:
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
            # Ekran kanalı: tablo ve onay kodu kullanıcıya gider, modelin
            # bağlamına girmez (runner/README.md, "Kanal ayrımı").
            events.append({"kind": "screen", "text": str(preview_text)})
        session.messages.append({"role": "tool", "content": self.runner.for_model(result)})
        session.last_state = result.get("state")
        session.gate.note_result(result)
        return result, preview_text

    def _response(self, session: CatiaSkillSession, events: list[dict]) -> dict:
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
