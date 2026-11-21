"""모든 방법을 동일 조건으로 돌리고 비교표를 낸다.

★ 보고서의 숫자는 **오직 이 파일의 출력**에서만 나온다.
  팀원이 자기 스크립트로 뽑은 숫자는 쓰지 않는다. 그게 지난 팀플이 깨진 이유다.

실행:
  python 3-model/run_all.py            # 전부
  python 3-model/run_all.py --demo     # 하네스 자체 점검 (임시 planner)
  python 3-model/run_all.py --only fcfs
"""
from __future__ import annotations
import sys, json, glob, time, argparse, pathlib, importlib, statistics as st

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from core.schema import load_instance, validate_stage1
from core.recourse import recourse
from core.evaluate import evaluate

METHODS = [("fcfs", "FCFS"), ("nominal", "결정론 nominal"),
           ("robust", "로버스트"), ("perfect", "완전정보")]
METRIC = "total_port_h"

def load_cfg() -> dict:
    p = HERE / "config.yaml"
    try:
        import yaml
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except ImportError:
        print("! pyyaml 없음 — 기본값 사용 (pip install pyyaml)")
        return {"run": {"time_limit_s": 60, "n_realization": 20, "seed": 20261119},
                "scenario": {"n_scenario_saa": 15, "gamma": 3}}

def demo_plan(inst, cfg):
    """하네스 점검용 임시 planner. 결과 보고에는 절대 쓰지 않는다."""
    berths = {b["id"]: b for b in inst["berths"]}
    seq = {b: [] for b in berths}; load = {b: 0.0 for b in berths}; cr = {}
    for v in sorted(inst["vessels"], key=lambda x: x["arrival_h"]):
        fits = [b for b in berths.values() if v["loa_m"] <= b["length_m"]]
        best = min(fits, key=lambda b: load[b["id"]])
        seq[best["id"]].append(v["id"]); load[best["id"]] += v["workload_t"]
        cr[v["id"]] = min(v["q_max"], best["q_max"])
    return {"sequence": seq, "cranes": cr}

def run_one(inst, reals, plan_fn, cfg):
    t = time.perf_counter()
    s1 = plan_fn(inst, cfg)
    plan_s = time.perf_counter() - t
    validate_stage1(inst, s1)                     # 모양이 틀리면 여기서 멈춘다
    vals, infeas = [], 0
    for r in reals:
        m = evaluate(inst, recourse(inst, s1, r))
        if m["feasible"]: vals.append(m[METRIC])
        else:             infeas += 1
    if not vals:
        return None
    return {"mean": st.mean(vals), "worst": max(vals), "best": min(vals),
            "sd": st.pstdev(vals), "infeasible": infeas, "plan_s": plan_s}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    cfg = load_cfg()

    insts = sorted(glob.glob(str(HERE / "instances" / "*.json")))
    insts = [p for p in insts if not p.endswith(".real.json")]
    if not insts:
        print("인스턴스 없음 — python 3-model/make_samples.py 먼저"); return

    methods = [("demo", "DEMO(임시)", demo_plan)] if a.demo else []
    if not a.demo:
        for mod, label in METHODS:
            if a.only and mod != a.only: continue
            try:
                m = importlib.import_module(f"tasks.{mod}.plan")
                methods.append((mod, label, m.plan))
            except Exception as e:
                methods.append((mod, label, None)); print(f"! {mod} 불러오기 실패: {e}")

    rows = []
    for ip in insts:
        inst  = load_instance(ip)
        reals = json.loads(pathlib.Path(ip.replace(".json", ".real.json")).read_text())
        reals = reals[: cfg["run"]["n_realization"]]
        print(f"\n=== {inst['id']}  (선박 {len(inst['vessels'])}척, sha {inst['_sha']}, "
              f"실현 {len(reals)}개) ===")
        print(f"{'방법':<16}{'평균':>10}{'최악':>10}{'표준편차':>10}{'계획(s)':>9}")
        for mod, label, fn in methods:
            if fn is None: continue
            try:
                r = run_one(inst, reals, fn, cfg)
            except NotImplementedError:
                print(f"{label:<16}{'미구현':>10}"); continue
            except Exception as e:
                print(f"{label:<16}{'오류':>10}  {type(e).__name__}: {e}"); continue
            if r is None:
                print(f"{label:<16}{'전부 실패':>10}"); continue
            print(f"{label:<16}{r['mean']:>10.1f}{r['worst']:>10.1f}"
                  f"{r['sd']:>10.1f}{r['plan_s']:>9.2f}")
            rows.append({"instance": inst["id"], "sha": inst["_sha"],
                         "method": mod, **r})

    if rows:
        import csv
        out = HERE / "output" / "results.csv"
        out.parent.mkdir(exist_ok=True)
        with open(out, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
        print(f"\n저장: {out}")
        check_order(rows)

def check_order(rows):
    """WS <= RP <= EEV 는 정리다. 깨지면 코드 버그. (제안서 평가 절차 점검)"""
    print("\n[순서 점검] 완전정보 <= SAA <= nominal 이어야 함 (평균 기준)")
    by = {}
    for r in rows: by.setdefault(r["instance"], {})[r["method"]] = r["mean"]
    for inst, d in by.items():
        ws, rp, eev = d.get("perfect"), d.get("saa"), d.get("nominal")
        if None in (ws, rp, eev): print(f"  {inst}: 아직 판단 불가"); continue
        ok = ws <= rp + 1e-6 <= eev + 1e-6
        print(f"  {'OK ' if ok else 'BUG'} {inst}: {ws:.1f} <= {rp:.1f} <= {eev:.1f}")

if __name__ == "__main__":
    main()
