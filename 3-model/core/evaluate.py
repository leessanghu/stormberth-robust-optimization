"""실현된 일정 -> 지표. 보고서의 모든 숫자는 여기서만 나온다."""
from __future__ import annotations

def evaluate(inst: dict, sched: dict) -> dict:
    if not sched.get("feasible", False):
        return {"feasible": False}
    V = {v["id"]: v for v in inst["vessels"]}
    wait = sched["wait_h"]; end = sched["end_h"]
    port = {k: end[k] - min(sched["start_h"][k] - wait[k], sched["start_h"][k])
            for k in V}                                   # 재항시간 = 도착~출항
    n = len(V)
    return {
        "feasible":      True,
        "total_port_h":  sum(port.values()),      # 주지표
        "mean_port_h":   sum(port.values()) / n,
        "total_wait_h":  sum(wait.values()),
        "max_wait_h":    max(wait.values()),
        "makespan_h":    max(end.values()),
        "n_vessel":      n,
    }
