"""evals/evals.json içindeki test vakalarını modele koşturur ve puanlar.

Nitel değerlendirme insan işi; bu script yalnızca nesnel olarak
doğrulanabilir şeyleri ölçer: hangi komutlar çalıştı, hangileri çalışmadı,
model soru sordu mu. Bu üçü küçük modelde en sık bozulan davranışlar.

    python runner/run_evals.py --workspace /tmp/evalws --skill . --fake
    python runner/run_evals.py --model qwen3:4b-instruct --repeat 3
"""

import argparse
import json
import pathlib
import re
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import agent as agent_mod  # noqa: E402


def check(assertion, result):
    kind = assertion["kind"]
    commands = [c["command"] for c in result["calls"]]
    executed = [c["command"] for c in result["calls"] if not c["blocked"]]

    if kind == "command_ran":
        return any(re.search(assertion["pattern"], c) for c in executed)
    if kind == "command_not_ran":
        return not any(re.search(assertion["pattern"], c) for c in executed)
    if kind == "no_commands":
        return not commands
    if kind == "asked_question":
        for turn in result["transcript"]:
            if turn.get("role") == "assistant" and "?" in (turn.get("content") or ""):
                return True
        return False
    if kind == "mentions":
        blob = " ".join((t.get("content") or "") for t in result["transcript"]
                        if t.get("role") == "assistant").lower()
        return all(w.lower() in blob for w in assertion["words"])
    raise ValueError(f"bilinmeyen assertion türü: {kind}")


def prepare_workspace(base, skill, seeded):
    """Her vaka için temiz bir çalışma klasörü. `seeded` ise kalibrasyon ve
    bir ölçüm hazır gelir, böylece 'bunu Adams'a aktar' gibi vakalar
    sıfırdan başlamak zorunda kalmaz."""
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    for src in (pathlib.Path(skill) / "assets").glob("*.example.json"):
        shutil.copy(src, base / src.name.replace(".example", ""))
    if seeded:
        import os
        import subprocess

        env = dict(os.environ)
        env["PYTHONPATH"] = str(pathlib.Path(skill).resolve())
        for cmd in (
            ["calibrate", "--source", "fake", "--length", "100", "--width", "200",
             "--height", "300", "--density", "7850"],
            ["extract", "--source", "fake", "--vehicle", "ARAC-X",
             "--variant", "BASE", "--revision", "R04"],
            ["rollup"], ["diff"],
        ):
            subprocess.run([sys.executable, "-m", "cmc"] + cmd, cwd=str(base),
                           env=env, capture_output=True, text=True, check=True)
    return base


def main():
    p = agent_mod.build_parser()
    p.add_argument("--evals", default="evals/evals.json")
    p.add_argument("--repeat", type=int, default=1, help="her vakayı kaç kez koş")
    p.add_argument("--out", default="eval-results.json")
    args = p.parse_args()

    evals = json.loads(pathlib.Path(args.evals).read_text(encoding="utf-8"))["evals"]
    base = pathlib.Path(args.workspace).resolve()
    rows = []

    for case in evals:
        assertions = case.get("assertions") or []
        if not assertions:
            continue
        for run in range(args.repeat):
            prepare_workspace(base, args.skill, case.get("seeded", False))
            case_args = argparse.Namespace(**vars(args))
            case_args.seed = run
            case_args.transcript = None
            result = agent_mod.run_session(case_args, user_turns=[case["prompt"]])
            checks = [{"text": a.get("text", a["kind"]), "passed": check(a, result)}
                      for a in assertions]
            rows.append({
                "id": case["id"],
                "run": run,
                "prompt": case["prompt"],
                "passed": all(c["passed"] for c in checks),
                "checks": checks,
                "commands": [c["command"] for c in result["calls"]],
                "assistant_text": [t.get("content") for t in result["transcript"]
                                   if t.get("role") == "assistant" and t.get("content")],
            })
            mark = "PASS" if rows[-1]["passed"] else "FAIL"
            print(f"[{mark}] eval {case['id']} (koşu {run})")
            for c in checks:
                if not c["passed"]:
                    print(f"        düşen kontrol: {c['text']}")

    pathlib.Path(args.out).write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    total = len(rows)
    passed = sum(1 for r in rows if r["passed"])
    print(f"\n{passed}/{total} koşu geçti. Ayrıntı: {args.out}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
