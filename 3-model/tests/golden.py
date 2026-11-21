"""골든 테스트 — 손으로 푼 답과 맞는지. 담당: 팀원 A (확장)

여기가 틀리면 모든 비교가 무의미하다. 1주차에 통과시키고 건드리지 않는다.
실행:  python 3-model/tests/golden.py
"""
from __future__ import annotations
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from core.recourse import recourse
from core.evaluate import evaluate

def case_single_berth():
    """선석 1개·크레인 2기·선박 3척. 저하 없음(kappa=1). 1척당 딱 2시간.

        V1 도착 0 -> 0~2    대기 0    재항 2
        V2 도착 1 -> 2~4    대기 1    재항 3
        V3 도착 2 -> 4~6    대기 2    재항 4
        총 재항 9시간, 총 대기 3시간, makespan 6
    """
    inst = {
        "id": "golden_single", "horizon_h": 24,
        "berths": [{"id": "B1", "length_m": 400, "q_max": 2}],
        "cranes": {"total": 2, "rate_tph": 100.0},
        "recovery": {"t_reopen_h": 0.0, "kappa": 1.0, "kappa_recover_h": 0.0},
        "vessels": [
            {"id": "V1", "arrival_h": 0.0, "loa_m": 200, "workload_t": 400.0, "q_min": 1, "q_max": 2},
            {"id": "V2", "arrival_h": 1.0, "loa_m": 200, "workload_t": 400.0, "q_min": 1, "q_max": 2},
            {"id": "V3", "arrival_h": 2.0, "loa_m": 200, "workload_t": 400.0, "q_min": 1, "q_max": 2},
        ],
    }
    s1   = {"sequence": {"B1": ["V1", "V2", "V3"]}, "cranes": {"V1": 2, "V2": 2, "V3": 2}}
    real = {"arrival_h": {"V1": 0.0, "V2": 1.0, "V3": 2.0},
            "workload_t": {"V1": 400.0, "V2": 400.0, "V3": 400.0}}
    m = evaluate(inst, recourse(inst, s1, real))
    return m, {"total_port_h": 9.0, "total_wait_h": 3.0, "makespan_h": 6.0, "max_wait_h": 2.0}

def case_crane_contention():
    """선석 2개인데 크레인이 3기뿐. 두 배 모두 2기씩 원하면 동시 진행 불가.

        V1 0~2 (크레인 2기 점유, 1기 남음 -> V2는 2기를 못 받음)
        V2 2~4
        총 재항 = 2 + 4 = 6,  makespan 4
    """
    inst = {
        "id": "golden_crane", "horizon_h": 24,
        "berths": [{"id": "B1", "length_m": 400, "q_max": 2},
                   {"id": "B2", "length_m": 400, "q_max": 2}],
        "cranes": {"total": 3, "rate_tph": 100.0},
        "recovery": {"t_reopen_h": 0.0, "kappa": 1.0, "kappa_recover_h": 0.0},
        "vessels": [
            {"id": "V1", "arrival_h": 0.0, "loa_m": 200, "workload_t": 400.0, "q_min": 2, "q_max": 2},
            {"id": "V2", "arrival_h": 0.0, "loa_m": 200, "workload_t": 400.0, "q_min": 2, "q_max": 2},
        ],
    }
    s1   = {"sequence": {"B1": ["V1"], "B2": ["V2"]}, "cranes": {"V1": 2, "V2": 2}}
    real = {"arrival_h": {"V1": 0.0, "V2": 0.0}, "workload_t": {"V1": 400.0, "V2": 400.0}}
    m = evaluate(inst, recourse(inst, s1, real))
    return m, {"total_port_h": 6.0, "makespan_h": 4.0}

def case_kappa():
    """크레인 저하 kappa=0.5, 회복 없음 -> 처리시간이 정확히 2배.
       선석1·크레인2·선박1, 원래 2시간 -> 4시간."""
    inst = {
        "id": "golden_kappa", "horizon_h": 24,
        "berths": [{"id": "B1", "length_m": 400, "q_max": 2}],
        "cranes": {"total": 2, "rate_tph": 100.0},
        "recovery": {"t_reopen_h": 0.0, "kappa": 0.5, "kappa_recover_h": 0.0},
        "vessels": [{"id": "V1", "arrival_h": 0.0, "loa_m": 200,
                     "workload_t": 400.0, "q_min": 2, "q_max": 2}],
    }
    s1   = {"sequence": {"B1": ["V1"]}, "cranes": {"V1": 2}}
    real = {"arrival_h": {"V1": 0.0}, "workload_t": {"V1": 400.0}}
    m = evaluate(inst, recourse(inst, s1, real))
    return m, {"total_port_h": 4.0, "makespan_h": 4.0}

CASES = [("선석 1개 순차", case_single_berth),
         ("크레인 경합",   case_crane_contention),
         ("생산성 저하",   case_kappa)]

if __name__ == "__main__":
    bad = 0
    for name, fn in CASES:
        got, want = fn()
        errs = [f"{k}: 기대 {v} / 실제 {got.get(k)}"
                for k, v in want.items() if abs(got.get(k, -999) - v) > 1e-6]
        print(f"{'OK  ' if not errs else 'FAIL'} {name}")
        for e in errs:
            print(f"       {e}"); bad += 1
    print("\n모두 통과" if not bad else f"\n{bad}개 불일치 — recourse.py 확인")
    sys.exit(1 if bad else 0)
