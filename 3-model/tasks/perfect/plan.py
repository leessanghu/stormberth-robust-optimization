"""perfect — 완전정보 (Wait-and-See, WS)

실현값 real 을 미리 안다고 보고, 그 실현 하나에 대해 1단계를 고른다.
run_all.py 가 실현마다 plan(inst, cfg, real) 을 따로 부른다 (PER_REAL).

다른 방법과 똑같이 공용 탐색 엔진(core.planutil.local_search)을 쓴다.
다른 점은 시나리오 하나뿐이다:  scenarios = [real]
"""
from __future__ import annotations
import importlib
import statistics

from core.planutil import local_search, score

# 다른 방법의 계획도 후보로 넣을지. 기본은 꺼 둔다 (팀 합의 후 켤 것).
# 켜면 같은 실현에서 WS 가 그 방법들보다 나쁠 수 없게 되어,
# 휴리스틱 운 때문에 '완전정보 <= SAA <= nominal' 점검이 깨지는 일을 막는다.
USE_OTHER_PLANS = False
OTHERS = ("nominal", "saa", "robust", "fcfs")
_cache: dict = {}   # 다른 방법의 계획은 실현과 무관하므로 인스턴스마다 한 번만 계산


def _other_plans(inst, cfg) -> list[dict]:
    key = inst["id"]
    if key not in _cache:
        plans = []
        for name in OTHERS:
            try:
                plans.append(importlib.import_module(f"tasks.{name}.plan").plan(inst, cfg))
            except Exception:        # 미구현이거나 오류면 건너뜀
                pass
        _cache[key] = plans
    return _cache[key]


def plan(inst, cfg, real=None):
    """real = {"arrival_h": {선박id: 시각}, "workload_t": {선박id: 톤}} 또는 None.

    반환: {"sequence": {선석id: [선박id, ...]}, "cranes": {선박id: 크레인수}}
    탐색 예산(시드·반복수·재시작)은 cfg 에서 읽는다.
    """
    if real is None:
        raise ValueError("완전정보는 실현값 real 이 필요합니다 (run_all 의 PER_REAL 경로)")

    run = (cfg or {}).get("run", {})
    seed     = int(run.get("seed", 20261119)) % 100000
    iters    = int(run.get("search_iters", 1000))
    restarts = int(run.get("restarts", 8))

    scenarios = [real]                       # ← 완전정보의 핵심: 실현 하나만 본다
    agg = statistics.mean                    # 시나리오 1개라 평균 = 그 값

    best, best_val = local_search(inst, scenarios, agg=agg,
                                  iters=iters, seed=seed, restarts=restarts)

    if USE_OTHER_PLANS:
        for s1 in _other_plans(inst, cfg):
            val = score(inst, s1, scenarios, agg)
            if val < best_val:
                best, best_val = s1, val
    return best
