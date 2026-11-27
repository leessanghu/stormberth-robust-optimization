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
           ("saa", "SAA"), ("robust", "로버스트"), ("perfect", "완전정보")]
METRIC = "total_port_h"

# 실현 1개마다 따로 계획하는 방법. 완전정보(WS)는 정의상 여기 들어간다.
PER_REAL = {"perfect"}

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

def run_one(inst, reals, plan_fn, cfg, per_real=False):
    """per_real=True 면 실현마다 계획을 다시 짠다 (완전정보 전용)."""
    vals, infeas = [], 0
    t = time.perf_counter()
    if not per_real:
        s1 = plan_fn(inst, cfg)
        validate_stage1(inst, s1)                 # 모양이 틀리면 여기서 멈춘다
    plan_s = time.perf_counter() - t
    for r in reals:
        if per_real:
            t2 = time.perf_counter()
            s1 = plan_fn(inst, cfg, r)            # 실현값을 보고 짠다
            validate_stage1(inst, s1)
            plan_s += time.perf_counter() - t2
        m = evaluate(inst, recourse(inst, s1, r))
        if m["feasible"]: vals.append(m[METRIC])
        else:             infeas += 1
    if not vals:
        return None
    return {"mean": st.mean(vals), "worst": max(vals), "best": min(vals),
            "sd": st.pstdev(vals), "infeasible": infeas, "plan_s": plan_s,
            "_vals": vals}        # 짝지은 비교용 (CSV 에는 안 들어감)

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

    rows, detail = [], {}
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
                r = run_one(inst, reals, fn, cfg, per_real=(mod in PER_REAL))
            except NotImplementedError:
                print(f"{label:<16}{'미구현':>10}"); continue
            except Exception as e:
                print(f"{label:<16}{'오류':>10}  {type(e).__name__}: {e}"); continue
            if r is None:
                print(f"{label:<16}{'전부 실패':>10}"); continue
            print(f"{label:<16}{r['mean']:>10.1f}{r['worst']:>10.1f}"
                  f"{r['sd']:>10.1f}{r['plan_s']:>9.2f}")
            detail.setdefault(inst["id"], {})[mod] = r.pop("_vals")
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
        paired_report(detail)

def check_order(rows):
    """정리로 보장되는 순서만 점검한다.

    두 부등식을 **반드시 나눠서** 본다. 묶으면 멀쩡한 결과가 버그로 찍힌다.

    ① 완전정보(WS) <= SAA(RP)   — 진짜 하한. 실현을 보고 짠 계획이
       못 보고 짠 계획보다 나쁠 수는 없다. 같은 탐색기·같은 실현으로
       평가하므로 휴리스틱이어도 성립한다. **깨지면 코드 버그다.**

    ② SAA(RP) <= nominal(EEV)   — 여기서는 **정리가 아니다.**
       Birge & Louveaux 의 RP <= EEV 는 (a) 각 문제를 정확히 풀고
       (b) 계획에 쓴 그 분포로 평가할 때의 정리다. 우리는 둘 다 아니다 —
       국소탐색 휴리스틱으로 풀고, 계획에 안 쓴 실현 60개로 평가한다.
       그래서 1% 안쪽 역전은 정상이다. 참고로만 띄운다.

    'nominal <= FCFS' 도 정리가 아니다. 불확실성이 크면 nominal 이
    명목 시나리오에 과적합해 FCFS 보다 나빠질 수 있다. 실제로 그렇게 나온다.
    """
    by = {}
    for r in rows: by.setdefault(r["instance"], {})[r["method"]] = r["mean"]
    print("\n[정리 점검 ①] 완전정보 <= SAA  — 진짜 하한. 깨지면 버그")
    n_ws = bad_ws = 0
    for inst, d in by.items():
        w, a = d.get("perfect"), d.get("saa")
        if w is None or a is None:
            print(f"  --  {inst}: 아직 판단 불가"); continue
        n_ws += 1
        ok = w <= a + 1e-6
        if not ok: bad_ws += 1
        print(f"  {'OK ' if ok else 'BUG'} {inst}: 완전정보 {w:.1f} <= SAA {a:.1f}")
    if n_ws:
        print(f"  -> {n_ws - bad_ws}/{n_ws} 통과" +
              ("" if bad_ws == 0 else f"  ** {bad_ws}건 깨짐 — 코드 버그다. 고칠 것 **"))

    print("\n[참고 ②] SAA <= nominal  — 정리가 아니다. 역전해도 버그가 아니다")
    n_rp = inv = 0
    for inst, d in by.items():
        a, nm = d.get("saa"), d.get("nominal")
        if a is None or nm is None: continue
        n_rp += 1
        if a > nm + 1e-6:
            inv += 1
            worse = (a - nm) / nm * 100.0 if nm else 0.0
            print(f"  역전 {inst}: SAA {a:.1f} > nominal {nm:.1f}"
                  f"  (SAA 가 {worse:.2f}% 나쁨)")
    if n_rp:
        print(f"  -> {n_rp - inv}/{n_rp} 성립, {inv}건 역전 "
              f"(휴리스틱 탐색 + 표본 외 평가에서는 정상)")

    print("\n[참고] FCFS 대비 — 정리가 아니다. 음수면 과적합 신호")
    for inst, d in by.items():
        f = d.get("fcfs")
        if f is None: continue
        txt = "  ".join(f"{m} {(f-v)/f*100:+5.1f}%"
                        for m in ("nominal", "robust", "saa", "perfect")
                        if (v := d.get(m)) is not None)
        print(f"  {inst}: {txt}")


def paired_report(detail):
    """같은 실현에서 짝지어 비교한다. 실현이 험해서 생기는 변동이 상쇄된다.

    이게 없으면 방법 간 차이(수 %)가 실현 간 변동(수십 %)에 묻혀
    '어느 쪽이 나은지 말할 수 없다'로 끝난다. 실측으로 확인한 사항이다.
    """
    if not detail: return
    print("\n[짝지은 비교] FCFS 대비 절감 — 같은 실현끼리 짝지어 t 검정")
    print(f"  {'방법':<10}{'절감률':>9}{'t':>8}{'이긴 인스턴스':>13}")
    methods = [m for m in ("nominal", "robust", "saa", "perfect")
               if any(m in d for d in detail.values())]
    for m in methods:
        pcts = []
        for inst, d in detail.items():
            if m not in d or "fcfs" not in d: continue
            base, v = d["fcfs"], d[m]
            if len(base) != len(v): continue
            diff = [b - a for a, b in zip(v, base)]
            pcts.append(st.mean(diff) / st.mean(base) * 100)
        if len(pcts) < 2: continue
        se = st.pstdev(pcts) / (len(pcts) - 1) ** 0.5
        t = st.mean(pcts) / se if se > 1e-12 else 0.0
        print(f"  {m:<10}{st.mean(pcts):>8.2f}%{t:>8.2f}"
              f"{sum(x > 0 for x in pcts):>9}/{len(pcts)}")


if __name__ == "__main__":
    main()
