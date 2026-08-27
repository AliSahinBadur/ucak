# Wiring the CATIA Mass/CG Skill into ucak — Agent/Tool-Calling Layer Plan

**Status:** planning only, nothing in this doc is implemented yet.
**Depends on:** `skill/SKILL.md`, `skill/EXPLAINER.md`, `skill/catia-mass-cg.skill` (the packaged `cmc` CLI).
**Does not touch:** the RAG document pipeline (`SearchService`, `QAService`, etc.) — this is a parallel track, not a refactor of it.

---

## 1. What this closes

Today `ucak/skill/` is a fully-formed Claude Skill with no caller: nothing under `app/` imports `cmc` or loads `SKILL.md`, and `pywin32` (needed by `cmc/catia_com.py`) is only declared in `requirements-skill.txt` / the `skill` dependency-group — installable, not invoked. This plan adds the layer that lets ucak's own chat model (`qwen2.5:3b` via Ollama, `app/config.py:80`) actually drive the skill: read `SKILL.md`, call `cmc` subcommands as tools, relay `message_tr`, and stop for approval before `export`.

## 2. Execution boundary — the one decision that shapes everything else

`cmc/catia_com.py` talks to CATIA over COM (`pywin32`), which only works **on the machine where CATIA is running**. ucak's server is sometimes run on `--host 0.0.0.0` for LAN demo access (README), the same situation that already makes `os.startfile` in `main.py:1129` open files on the *server's* desktop instead of the requesting engineer's (flagged as §5.13 in `ARCHITECTURE_AND_IMPROVEMENTS.md`, never fixed).

Two options:

| | Localhost-only (recommended v1) | Relay to a client-side agent |
|---|---|---|
| How | Tool layer only runs when the request's client is `127.0.0.1`/`::1` — i.e. the engineer runs ucak on the same workstation as CATIA, which is how single-user usage already works | Server sends the next `cmc` command to the browser; a small local companion process on the engineer's machine executes it and posts the JSON back |
| Effort | Small — one guard function, reused for §5.13 too | New component (local daemon + pairing/auth), materially bigger |
| Fits today's usage | Yes — the CATIA-holding engineer is the one asking the question | Only needed once ucak is genuinely multi-engineer over LAN for this feature |

**Recommendation:** build localhost-only for v1, and fix §5.13 (`os.startfile`) with the same guard while we're in that code path — it's the same bug. Document the relay option here so it isn't rediscovered from scratch later.

```python
def _is_local_client(request: Request) -> bool:
    host = request.client.host if request.client else None
    return host in {"127.0.0.1", "::1"}
```

Return `409`/a clear `message_tr` from the new endpoint when this fails, rather than silently doing nothing.

## 3. Component map

```
Browser ── POST /skills/catia-mass-cg/chat ──┐
                                              ▼
                              app/routers/catia_skill.py   (new APIRouter — do not add to main.py, §5.1)
                                              │
                                              ▼
                              CatiaSkillChatService          (new, app/services/)
                              - owns the tool loop
                              - loads SKILL.md as system prompt
                              - enforces temperature=0, no-thinking, max-turns
                                              │
                        ┌─────────────────────┼─────────────────────┐
                        ▼                                           ▼
              ToolCallingLLMProvider                          CmcRunner
              (new, extends llm_provider.py)                  (new, app/services/)
              - POST /api/chat with `tools`                   - subprocess: sys.executable -m cmc ...
              - multi-turn message list                       - cwd = per-user workspace dir
              - parses tool_calls from Ollama                 - timeout, argv built from typed args only
                        │                                           │
                        ▼                                           ▼
                  Ollama (qwen2.5:3b)                    unpacked cmc/ package
                                                          (installed once from catia-mass-cg.skill)
```

## 4. `LLMProvider` needs tool-calling — it doesn't have it today

`app/services/llm_provider.py:24-40` is single-turn: `generate(prompt)` sends one `role: user` message and returns text; `generate_json` just regex-extracts `{...}` from free text (`_extract_json_object`, line 106). There is no `tools` field, no multi-turn history, no `tool_calls` parsing. This has to be added, not reused as-is.

Add alongside the existing Protocol (don't change its signature — other callers depend on it):

```python
class ToolCallingLLMProvider(Protocol):
    def chat(
        self,
        messages: list[dict],       # role: system|user|assistant|tool
        tools: list[dict],          # OpenAI-style function schema, Ollama /api/chat accepts this
        *,
        temperature: float = 0.0,
    ) -> ChatTurn:                  # { content: str|None, tool_calls: list[ToolCall] }
        ...
```

`OllamaLLMProvider` already POSTs to `{OLLAMA_HOST}/api/chat` (line 84) — extend the same client with a `tools` payload and read `payload["message"].get("tool_calls")`. `LLM_TIMEOUT_SECONDS` (currently feeding a 30s-class default) needs a separate, larger timeout for this path — `extract` walking a large assembly tree over COM can run well past typical chat timeouts.

## 5. `CmcRunner` — the only thing allowed to touch a subprocess

One job: given a validated, typed call, build an argv list (never a shell string — no `shell=True`, no string concatenation) and run it.

```python
class CmcRunner:
    def __init__(self, cmc_root: Path, workspace: Path, timeout_s: float):
        ...
    def run(self, subcommand: str, args: dict) -> dict:
        # subcommand must be in the fixed allowlist below; anything else raises
        # before a subprocess is ever started
        argv = [sys.executable, "-m", "cmc", subcommand, *_build_flags(subcommand, args)]
        result = subprocess.run(argv, cwd=self.workspace, capture_output=True,
                                 text=True, timeout=self.timeout_s)
        return _parse_envelope(result.stdout, result.returncode)
```

Allowlist (from `cmc/cli.py:558-604`, exhaustive — nothing outside this list is ever executed):
`doctor, attach, calibrate, extract, rollup, diff, preview, export, show, history, selftest`.

Notes grounded in the actual `cli.py`:
- Every command prints exactly one JSON object to stdout, success or failure (`envelope.py:25-58`) — parse stdout as JSON regardless of exit code, then cross-check `status` against exit code (`0`↔`ok`, `1`↔`error`) as a sanity assertion, not the source of truth.
- **Exception:** `argparse` itself can reject malformed args (missing required flag) before `main()`'s try/except ever runs, printing usage text to stderr and exiting `2` — no JSON at all. `CmcRunner` must catch a JSON-parse failure on stdout and synthesize its own error envelope (`E_TOOL_LAYER_BAD_ARGS`) rather than crashing the chat loop. This should be rare if the tool JSON-schemas below enforce required fields before we ever build argv, but the runner can't assume the schema validation upstream is perfect.
- `--source` is **not** a per-call model-chosen argument. Fix it per chat session from a session-level "practice mode" toggle (UI checkbox, default off/real). Letting the model pick `fake` vs `catia` per tool call risks a real measurement silently running against the synthetic vehicle, or vice versa — EXPLAINER.md's own "içerir gerçek tuzak" fake vehicle exists precisely to be indistinguishable from a careless glance.

## 6. Tool schemas (one per allowlisted subcommand)

Typed schemas, not a single free-text `command_line` tool — matches `cli.py`'s own docstring reasoning ("a small model can copy a command, it cannot invent one reliably", `cli.py:1-7`) by having Ollama's structured tool-calling reject malformed calls before they reach `CmcRunner` at all.

| Tool | Required args | Maps to |
|---|---|---|
| `cmc_doctor` | — | `doctor` |
| `cmc_attach` | — | `attach` |
| `cmc_calibrate` | `length, width, height, density` (float) | `calibrate --length … --density …` |
| `cmc_extract` | `vehicle, variant, revision` (str) | `extract --vehicle … --revision …` |
| `cmc_rollup` | `run_id` (str, default `"last"`) | `rollup --run …` |
| `cmc_diff` | `run_id` | `diff --run …` |
| `cmc_preview` | `run_id` | `preview --run …` |
| `cmc_export` | `run_id, approve_code, user_confirmed` (bool) | `export --run … --approve …` — see §8 |
| `cmc_show` | `run_id` | `show --run …` |
| `cmc_history` | `vehicle?, variant?, limit?` | `history …` |
| `cmc_selftest` | — | `selftest` |

`--source` and `--inject-faults` are session-level config, never model-exposed args (§5).

## 7. `CatiaSkillChatService` — the loop

```
1. Load SKILL.md verbatim as the system message (skip references/*.md —
   EXPLAINER.md is explicit that those are for humans, not loaded to the
   model: "references/ dosyaları modele yüklenmez, insan içindir")
2. Append conversation history + new user message
3. Call ToolCallingLLMProvider.chat(messages, tools) with temperature=0
4. If content only  -> show message_tr-equivalent text to user, stop turn
5. If tool_calls    -> for each (small models rarely batch, but handle 1):
     - reject anything not in the allowlist before calling CmcRunner
     - run via CmcRunner
     - append {"role": "tool", "content": <json envelope>} to messages
     - loop back to step 3, capped at MAX_TURNS (config, default ~6 —
       doctor→attach/calibrate→extract→rollup→diff→preview is 5-6 steps)
6. Never let the model author message_tr itself — SKILL.md rule 4 says
   show the field verbatim; the service should render `message_tr` from
   the tool result directly into the chat UI rather than trusting the
   model's paraphrase of it, since a 3B model paraphrasing a number is
   exactly the failure EXPLAINER.md §"Neden LLM hiçbir sayı hesaplamıyor"
   is designed to prevent.
```

## 8. Approval gate: don't rely on the model alone

`cmc export` already requires a token copied from `preview`'s output (`cli.py:441-447`, `E_APPROVAL`/`E_STALE_APPROVAL`). That defends the *file write* from a wrong number, but not from the *decision to export* being made by the model off a misread chat message or a prompt-injected document. Add a second, independent gate at the tool layer:

- `cmc_export`'s tool schema takes `user_confirmed: bool`.
- The backend sets this **only** from a distinct UI action (an explicit "Onayla ve dışa aktar" button rendered under the `preview_text` shown to the user) — never from the model's tool-call arguments being trusted as-is, and never inferred from free-text chat like "yes" or "evet".
- `CatiaSkillChatService` rejects the `cmc_export` tool call server-side if the session has no matching pending confirmation, before `CmcRunner` ever runs it — independent of what the model passed.

This is defense in depth on top of SKILL.md's own rule 6, not a replacement for it.

## 9. Per-user workspace and skill install

- `cmc` reads/writes `units_profile.json`, `subassembly_map.json`, `runs/<id>/…`, `memory.sqlite` in its working directory (`EXPLAINER.md` §"Çalışma klasörü"). Give each authenticated user their own: `data/catia_skill/<username>/`, keyed off the existing session cookie (`main.py:124-144`, `APP_USERS`). Prevents two engineers on the same box clobbering each other's calibration/run history.
- The `cmc/` package itself only exists inside `skill/catia-mass-cg.skill` (a zip) today. At server startup (or lazily on first tool call), unpack it once to a runtime path, e.g. `data/skills/catia-mass-cg/cmc/`, skip if already unpacked and the zip's hash matches a stamp file. Import/run it via `sys.executable -m cmc` with `PYTHONPATH` including that unpack dir — don't vendor `cmc` into `app/` proper, keep the skill self-contained and independently updatable by dropping in a new `.skill` file.

## 10. Config additions (`app/config.py`, same `os.getenv` pattern as the rest of the file)

```python
CATIA_SKILL_ENABLED = os.getenv("CATIA_SKILL_ENABLED", "false").lower() == "true"
CATIA_SKILL_WORKSPACE_ROOT = os.getenv("CATIA_SKILL_WORKSPACE_ROOT", "data/catia_skill")
CATIA_SKILL_CMC_TIMEOUT_SECONDS = float(os.getenv("CATIA_SKILL_CMC_TIMEOUT_SECONDS", "120"))
CATIA_SKILL_MAX_TURNS = int(os.getenv("CATIA_SKILL_MAX_TURNS", "8"))
```

Default `CATIA_SKILL_ENABLED=false` — same graceful-degradation posture as the rest of the app (`AGENTS.md`, §4.1 of the architecture review): the feature is off until an engineer explicitly turns it on on their own machine.

## 11. Routing — explicit mode, not heuristic auto-detection

`ChatRequest.assistant_mode` (`api_models.py:210`) is currently `Literal["auto", "report", "general"]`, dispatched in `main.py:732`. It would be tempting to add keyword heuristics (the skill's own frontmatter `description` already lists trigger phrases: "CATIA", "kütle", "CG", "Adams", …) the way `_is_general_chat_message` (`main.py:777`) does for general chat.

**Don't auto-route into this mode.** Unlike general chat or RAG Q&A, a misrouted message here can attach to a live CATIA COM session and, at the end of the flow, overwrite Adams rigid-body values an engineer set by hand (EXPLAINER.md's own stated worry). Add `"catia_skill"` as a fourth explicit literal value; only reach `CatiaSkillChatService` when the user (or a UI mode switch) sets it directly.

## 12. Testing

Follow the project's own `--source fake` escape hatch — no CATIA license or hardware needed for CI:

- New `scripts/run_catia_skill_checks.py` (same family as the existing `scripts/run_*_checks.py`) driving `CatiaSkillChatService` end-to-end against `cmc --source fake`, asserting the doctor→calibrate→extract→rollup→diff→preview→export chain completes, the approval-token gate actually blocks an unconfirmed export, and a deliberately malformed tool call never reaches `CmcRunner`.
- Unit tests for `CmcRunner`'s argv-building and the "argparse exited 2 with no JSON" fallback path — these are pure functions, cheap to cover, and this is new code so it shouldn't repeat the untested-pure-function gap flagged as §5.3 in `ARCHITECTURE_AND_IMPROVEMENTS.md`.
- Run `python -m cmc selftest` in CI once as a smoke check that the unpacked skill bundle is intact.

## 13. Suggested sequence

1. **Boundary + provider plumbing.** `_is_local_client` guard (and fix §5.13 with it); extend `llm_provider.py` with tool-calling support; nothing user-facing yet.
2. **`CmcRunner` + skill unpack-on-startup**, unit-tested against `--source fake`, no chat loop wired yet — verifies the subprocess/JSON-envelope contract in isolation.
3. **`CatiaSkillChatService` + `app/routers/catia_skill.py`**, gated behind `CATIA_SKILL_ENABLED=false` by default, explicit `assistant_mode="catia_skill"` only.
4. **Approval-gate UI** (the confirm button feeding `user_confirmed`) — ship before turning the flag on anywhere real export happens.
5. **Enable for one pilot engineer** with real CATIA, using `run_catia_skill_checks.py` fake-mode as the CI gate and a manual real-CATIA smoke test before wider rollout.

## 14. Open questions for you before implementation starts

- Confirm localhost-only (§2) is acceptable for v1, vs. wanting the relay design sketched now instead of deferred.
- Where should the confirm-before-export UI live — a new panel, or reuse the existing chat UI's message actions?
- Should `CATIA_SKILL_ENABLED` be a global server flag, or per-user (some engineers have CATIA, some don't)?
