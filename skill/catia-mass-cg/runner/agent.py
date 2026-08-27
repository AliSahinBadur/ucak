"""Ollama ile cmc hattını süren ajan döngüsü.

Ollama sadece modeli servis eder. Döngü, araç kısıtı ve güvenlik kapıları
burada. Küçük bir model için harness'ın işi modeli akıllandırmak değil,
yapabileceği hata sayısını azaltmaktır:

1. TEK ARAÇ.  Model sadece `run_cmc` çağırabilir ve komut bir izin listesine
   karşı doğrulanır. Serbest kabuk erişimi yok, Python yazma yok.
2. BAĞLAM KIRPMA.  Araç sonucundan modele yalnızca sabit bir alan kümesi
   döner. 2000 parçalık `components.json` modelin bağlamına hiç girmez;
   girerse hem bozar hem uydurur.
3. İNSAN KAPISI.  `export`, kullanıcı bu oturumda açıkça onaylamadan
   çalıştırılamaz. cmc'deki onay kodu zaten var; bu ikinci katman, modelin
   kodu bir yerden kopyalayıp kapıyı atlamasına karşı.

Kullanım:
    ollama serve                      # ayrı terminalde
    ollama pull qwen3:4b-instruct
    python runner/agent.py --workspace C:\\cmc-ws --skill .

    python runner/agent.py --workspace /tmp/ws --fake     # CATIA olmadan
"""

import argparse
import json
import pathlib
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.request

# --------------------------------------------------------------------------
# izin listesi
# --------------------------------------------------------------------------

ALLOWED = {
    "doctor": set(),
    "attach": {"--source"},
    "calibrate": {"--length", "--width", "--height", "--density", "--source"},
    "extract": {"--vehicle", "--variant", "--revision", "--source", "--inject-faults"},
    "rollup": {"--run"},
    "diff": {"--run"},
    "preview": {"--run"},
    "export": {"--run", "--approve"},
    "show": {"--run"},
    "history": {"--vehicle", "--variant", "--limit"},
    "selftest": set(),
}

# Modele geri dönen alanlar. Bunun dışındaki her şey diskte kalır.
PASSTHROUGH = (
    "status", "step", "code", "message_tr", "hint_tr", "next_command",
    "ask_user_tr", "command_template", "command_after_approval",
    "approval_token", "warnings", "warnings_total", "warnings_shown",
    "run_id", "unmapped", "unmapped_total", "inertia_usable",
)
PREVIEW_TEXT_LIMIT = 4000

APPROVAL_WORDS = re.compile(
    r"\b(onaylıyorum|onayliyorum|onaylandı|onaylandi|onay veriyorum|kabul ediyorum|"
    r"tamam yaz|yaz gitsin|approve[d]?|i approve)\b", re.IGNORECASE)


class Blocked(Exception):
    pass


def validate(command, force_source=None):
    """Model komutu yazamaz, kopyalar. Yine de her komut doğrulanır."""
    try:
        parts = shlex.split(command)
    except ValueError as exc:
        raise Blocked(f"Komut ayrıştırılamadı: {exc}")

    while parts and parts[0] in ("python", "python3", "-m", "cmc", "py"):
        parts.pop(0)
    if not parts:
        raise Blocked("Boş komut.")

    sub = parts[0]
    if sub not in ALLOWED:
        raise Blocked(
            f"'{sub}' izinli bir cmc komutu değil. İzinliler: {', '.join(sorted(ALLOWED))}")

    allowed_flags = ALLOWED[sub]
    for token in parts[1:]:
        if token.startswith("-") and token not in allowed_flags:
            raise Blocked(f"'{sub}' komutunda '{token}' argümanı izinli değil.")
        if "<" in token or ">" in token:
            raise Blocked(
                f"'{token}' hâlâ bir yer tutucu. Bu değeri kullanıcıya sorun, "
                "kendiniz doldurmayın.")

    if force_source and sub in ("attach", "calibrate", "extract") and "--source" not in parts:
        parts += ["--source", force_source]

    return sub, [sys.executable, "-m", "cmc"] + parts


def trim(raw):
    """Modelin göreceği kısım. Geri kalanı diskte, insan için."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"status": "error", "code": "E_BAD_OUTPUT",
                "message_tr": "Komut JSON üretmedi.", "raw": raw[:500]}
    out = {k: data[k] for k in PASSTHROUGH if k in data and data[k] not in (None, [], {})}
    if "preview_text" in data:
        out["preview_text"] = data["preview_text"][:PREVIEW_TEXT_LIMIT]
    return out


# --------------------------------------------------------------------------
# ollama
# --------------------------------------------------------------------------

TOOLS = [{
    "type": "function",
    "function": {
        "name": "run_cmc",
        "description": (
            "CATIA kütle/CG hattının bir komutunu çalıştırır. Komut, SKILL.md'de "
            "listelenen cmc komutlarından biri olmalı ve tam olarak kopyalanmalıdır. "
            "Yer tutucu (<ARAC> gibi) içeren komut reddedilir."),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Örnek: python -m cmc rollup --run 2026-08-27T09-04-54",
                }
            },
            "required": ["command"],
        },
    },
}]


def chat(host, model, messages, seed=0, num_ctx=8192):
    payload = {
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "top_p": 1, "seed": seed, "num_ctx": num_ctx},
    }
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read().decode("utf-8"))["message"]
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"Ollama'ya ulaşılamadı ({host}): {exc}\n"
            "`ollama serve` çalışıyor mu?")


class StubClient:
    """Test için: Ollama olmadan döngüyü sürer. Senaryo JSONL dosyasından
    okunur, her satır bir asistan mesajıdır."""

    def __init__(self, path):
        self.turns = [json.loads(line) for line in
                      pathlib.Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
        self.i = 0

    def __call__(self, host, model, messages, **kw):
        if self.i >= len(self.turns):
            return {"role": "assistant", "content": "(senaryo bitti)"}
        turn = self.turns[self.i]
        self.i += 1
        return turn


# --------------------------------------------------------------------------
# döngü
# --------------------------------------------------------------------------

def run_session(args, user_turns=None):
    skill = pathlib.Path(args.skill) / "SKILL.md"
    if not skill.exists():
        raise SystemExit(f"SKILL.md bulunamadı: {skill}")
    system = skill.read_text(encoding="utf-8")

    workspace = pathlib.Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    env_path = str(pathlib.Path(args.skill).resolve())

    client = StubClient(args.stub) if args.stub else chat
    messages = [{"role": "system", "content": system}]
    transcript = []
    approved = False
    calls = []

    pending = list(user_turns or [])
    while True:
        if pending:
            user = pending.pop(0)
        elif user_turns is not None:
            break
        else:
            try:
                user = input("\n> ").strip()
            except EOFError:
                break
            if user.lower() in ("q", "quit", "exit"):
                break
        if not user:
            continue
        if APPROVAL_WORDS.search(user):
            approved = True
        messages.append({"role": "user", "content": user})
        transcript.append({"role": "user", "content": user})

        pending_next = None
        nudges = 0
        blanks = 0
        for _ in range(args.max_steps):
            msg = client(args.host, args.model, messages, seed=args.seed)
            messages.append(msg)
            transcript.append(msg)

            tool_calls = msg.get("tool_calls") or []
            content = (msg.get("content") or "").strip()
            if content:
                print(f"\n[model] {content}")
            if args.verbose:
                print(f"[ham] {json.dumps(msg, ensure_ascii=False)[:800]}")

            if not tool_calls and not content:
                # Boş yanıt: model ne konuştu ne araç çağırdı. Sessizce çıkmak
                # kullanıcıya hiçbir şey söylemez, o yüzden durumu bildirip
                # bir kez daha soruyoruz.
                blanks += 1
                print(f"[harness] model boş yanıt döndürdü ({blanks}. kez)")
                if blanks <= args.max_nudges:
                    messages.append({"role": "user", "content": (
                        "Boş yanıt verdin. Ne yapman gerektiğini SKILL.md "
                        "söylüyor: sıradaki cmc komutunu run_cmc aracıyla "
                        "çalıştır, ya da bilgi gerekiyorsa kullanıcıya sor.")})
                    continue
                print("[harness] model yanıt üretemiyor. Daha büyük bir model "
                      "veya daha yüksek nicemleme deneyin (runner/README.md, "
                      "'Model başarısız olursa').")
                break

            if not tool_calls:
                # Küçük modellerin en sık sapması: sıradaki komutu çalıştırmak
                # yerine kullanıcıya yazmak. Kullanıcı komutu elle çalıştırmak
                # zorunda kalırsa ajanın faydası kalmaz. Bir kez hatırlatıp
                # devam ediyoruz. İnsandan bilgi bekleyen adımlarda
                # (ask_user_tr) hatırlatma yapılmaz, orada durmak doğrudur.
                if pending_next and nudges < args.max_nudges:
                    nudges += 1
                    print(f"[harness] hatırlatma {nudges}: komut çalıştırılmadı")
                    messages.append({"role": "user", "content": (
                        f"Bu komut henüz çalıştırılmadı: {pending_next}\n"
                        "Kullanıcıya komut önerme, kullanıcı komut çalıştırmıyor. "
                        "run_cmc aracıyla sen çalıştır.")})
                    continue
                break

            # Bütçe toplam değil, ÜST ÜSTE takılma sayısıdır: her başarılı
            # komuttan sonra sıfırlanır. Aksi halde her adımda bir hatırlatma
            # gerektiren bir model zinciri yarıda bırakır.
            pending_next = None
            nudges = 0
            for call in tool_calls:
                command = (call.get("function", {}).get("arguments") or {}).get("command", "")
                if not isinstance(command, str):
                    command = str(command)
                result = dispatch(command, workspace, env_path, args, approved)
                calls.append({"command": command, "blocked": result.get("_blocked", False)})
                print(f"[cmc] {command}\n      -> {result.get('status')} "
                      f"{result.get('code','')} {result.get('message_tr','')[:160]}")
                messages.append({"role": "tool", "content": json.dumps(result, ensure_ascii=False)})
                transcript.append({"role": "tool", "command": command, "content": result})
                if result.get("next_command") and not result.get("ask_user_tr"):
                    pending_next = result["next_command"]

    if args.transcript:
        pathlib.Path(args.transcript).write_text(
            "\n".join(json.dumps(t, ensure_ascii=False) for t in transcript) + "\n",
            encoding="utf-8")
    return {"calls": calls, "transcript": transcript, "approved": approved}


def dispatch(command, workspace, env_path, args, approved):
    try:
        sub, argv = validate(command, force_source="fake" if args.fake else None)
    except Blocked as exc:
        return {"status": "error", "code": "E_BLOCKED", "message_tr": str(exc),
                "hint_tr": "SKILL.md'deki komut listesine bakın.", "_blocked": True}

    if sub == "export" and not approved and not args.auto_approve:
        return {"status": "error", "code": "E_NOT_APPROVED_BY_HUMAN",
                "message_tr": "Kullanıcı bu oturumda onay vermedi, export çalıştırılmadı.",
                "hint_tr": "Önce preview çıktısını kullanıcıya gösterip onay isteyin.",
                "_blocked": True}

    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = env_path + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(argv, cwd=str(workspace), env=env,
                          capture_output=True, text=True, timeout=args.timeout)
    return trim(proc.stdout or proc.stderr)


def build_parser():
    p = argparse.ArgumentParser(description="cmc hattını Ollama ile sür")
    p.add_argument("--workspace", required=True, help="cmc çalışma klasörü")
    p.add_argument("--skill", default=".", help="skill klasörü (SKILL.md burada)")
    p.add_argument("--model", default="qwen3:4b-instruct")
    p.add_argument("--host", default="http://localhost:11434")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--max-steps", type=int, default=12)
    p.add_argument("--max-nudges", type=int, default=3,
                   help="art arda kaç kez hatırlatılsın (başarılı komutta sıfırlanır)")
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--fake", action="store_true", help="CATIA yerine sentetik montaj")
    p.add_argument("--auto-approve", action="store_true",
                   help="SADECE test için: insan onay kapısını atlar")
    p.add_argument("--transcript", help="konuşmayı JSONL olarak kaydet")
    p.add_argument("--verbose", action="store_true",
                   help="modelin ham yanıtını bas (teşhis için)")
    p.add_argument("--stub", help="Ollama yerine senaryo dosyası (harness testi)")
    return p


if __name__ == "__main__":
    run_session(build_parser().parse_args())
