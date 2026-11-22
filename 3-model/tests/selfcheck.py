"""혼자서 내 plan.py 가 맞는지 확인한다. 다른 사람 코드가 없어도 된다.

    python 3-model/tests/selfcheck.py nominal

통과 기준이 아니라 **진단**이다. X 가 뜨면 뭐가 왜 틀렸는지 알려준다.
전부 O 가 나오면 run_all.py 로 넘어가면 된다.
"""
from __future__ import annotations
import sys, glob, random, pathlib, importlib, traceback

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from core.schema import load_instance, validate_stage1
from core.recourse import recourse
from core.evaluate import evaluate

OK, NG = "  O ", "  X "

def realization(inst, seed):
    """평가용 실현 1개. selfcheck 전용이라 본 실험 수치와는 무관하다."""
    import math
    rnd = random.Random(seed)
    s = math.sqrt(math.log(1 + 0.2 ** 2))
    ln = lambda: rnd.lognormvariate(0.0, s) * math.exp(-s * s / 2)
    return {"arrival_h":  {v["id"]: max(0.0, v["arrival_h"] + rnd.uniform(-4, 4))
                           for v in inst["vessels"]},
            "workload_t": {v["id"]: v["workload_t"] * ln() for v in inst["vessels"]}}

def main(name):
    try:
        mod = importlib.import_module("tasks.%s.plan" % name)
    except Exception:
        print("X  tasks/%s/plan.py 를 불러올 수 없습니다" % name); traceback.print_exc(); return 1

    cfg = {"run": {"search_iters": 400, "seed": 20261119, "restarts": 2},
           "scenario": {"n_scenario_saa": 10, "gamma": 3, "n_vertex": 6,
                        "late_h": 6.0, "heavy_mult": 1.6}}
    files = sorted(glob.glob(str(HERE / "instances" / "*.json")))
    files = [f for f in files if ".real." not in f]
    fails = 0

    for f in files[:2]:
        inst = load_instance(f)
        print("\n=== %s (%d척) ===" % (pathlib.Path(f).stem, len(inst["vessels"])))
        real = realization(inst, 777)

        # 1. 돌아가는가
        try:
            s1 = mod.plan(inst, cfg, real) if name == "perfect" else mod.plan(inst, cfg)
        except NotImplementedError as e:
            print(NG, ("아직 구현 전입니다 — %s" % e) if str(e) else "아직 구현 전입니다"); return 1
        except Exception as e:
            print(NG, "실행 중 오류: %s: %s" % (type(e).__name__, e))
            if not fails: traceback.print_exc()
            fails += 1; continue
        print(OK, "실행됨")

        # 2. 형식이 맞는가
        try:
            validate_stage1(inst, s1); print(OK, "형식 정상 (모든 배 1회 배정, 크레인 범위 준수)")
        except Exception as e:
            print(NG, "형식 오류: %s" % e); fails += 1; continue

        # 3. 2단계가 실제로 돌아가는가
        sched = recourse(inst, s1, real)
        if not sched.get("feasible"):
            print(NG, "recourse 실행불가 — 1단계 결정이 잘못됐습니다"); fails += 1; continue
        m = evaluate(inst, sched)
        print(OK, "평가됨  총 재항시간 %.1f h  (최대대기 %.1f h)" % (m["total_port_h"], m["max_wait_h"]))

        # 4. 재현되는가 — 같은 입력이면 같은 답이어야 한다
        s1b = mod.plan(inst, cfg, real) if name == "perfect" else mod.plan(inst, cfg)
        if s1b["sequence"] == s1["sequence"] and s1b["cranes"] == s1["cranes"]:
            print(OK, "재현성 정상 (같은 cfg → 같은 계획)")
        else:
            print(NG, "재현 안 됨 — 시드를 cfg 에서 읽지 않았거나 난수가 샙니다"); fails += 1

        # 5. cfg 를 실제로 쓰는가 — 예산을 바꾸면 결과가 달라져야 한다 (fcfs 제외)
        if name != "fcfs":
            cfg2 = {**cfg, "run": {**cfg["run"], "seed": 999, "search_iters": 900}}
            s1c = mod.plan(inst, cfg2, real) if name == "perfect" else mod.plan(inst, cfg2)
            if s1c["sequence"] == s1["sequence"]:
                print("  ? cfg 를 바꿔도 결과가 같습니다 — 시드·iters 를 코드에 박지 않았는지 확인")
            else:
                print(OK, "cfg 반영됨")

        # 6. 결과값 (판정하지 않는다. 비교는 run_all.py 가 한다)
        print("    총 재항시간 %.1f h" % m["total_port_h"])

        # 7. 완전정보 전용 — real 이 없을 때 명목값으로 되돌아가는가
        if name == "perfect":
            try:
                s1n = mod.plan(inst, cfg, None); validate_stage1(inst, s1n)
                print(OK, "real=None 일 때도 동작 (명목값으로 되돌아감)")
            except Exception as e:
                print(NG, "real=None 처리 안 됨: %s" % e); fails += 1
            sc_real = evaluate(inst, recourse(inst, s1, real))["total_port_h"]
            sc_nom  = evaluate(inst, recourse(inst, s1n, real))["total_port_h"]
            if sc_real <= sc_nom + 1e-6:
                print(OK, "실현을 본 계획이 명목 계획보다 좋음 (완전정보답습니다)")
            else:
                print(NG, "실현을 보고 짰는데 더 나쁩니다 — real 을 안 쓰고 있을 가능성"); fails += 1

    print("\n" + ("전부 통과. run_all.py 로 넘어가세요." if fails == 0
                  else "X 가 %d개 있습니다. 위 메시지를 보고 고치세요." % fails))
    return 1 if fails else 0

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("fcfs", "nominal", "saa", "robust", "perfect"):
        print("사용법: python 3-model/tests/selfcheck.py [fcfs|nominal|saa|robust|perfect]"); sys.exit(2)
    sys.exit(main(sys.argv[1]))
