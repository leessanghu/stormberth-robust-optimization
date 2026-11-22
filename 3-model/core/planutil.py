"""★ 공용 탐색 엔진. 네 방법이 **전부 이걸 쓴다**. 수정 권한: 이상후만.

왜 탐색을 공유하나 — 방법마다 탐색을 따로 짜면 "방법이 좋아서 이긴 건지
탐색이 좋아서 이긴 건지" 구분이 안 된다. 실측으로 이 탐색은 전역 최적 대비
0~0.90% (최악 1건 3.26%) 떨어지는데, 방법 간 차이는 약 0.8% 다.
즉 **탐색 노이즈가 방법 차이보다 크다.** 공유하지 않으면 비교가 성립하지 않는다.

담당자가 쓰는 건 이 두 개뿐이다.
    local_search(inst, 내_시나리오들, agg=내_목적함수, ...)
    assign_cranes(inst, sequence)

**시나리오를 만드는 코드는 여기 없다.** 그게 방법마다 다른 지점이고,
각자 자기 tasks/<방법>/plan.py 안에 쓴다.

시작시각 S_i 는 절대 여기서 정하지 않는다 — 그건 core/recourse.py 의 몫이다.
"""
from __future__ import annotations
import random
from core.recourse import recourse
from core.evaluate import evaluate


# ── 기본 조회 ──────────────────────────────────────────────────────────────
def fits(inst: dict) -> dict:
    """선박별로 길이가 맞는 선석 목록. (C2) 전처리."""
    B = {b["id"]: b for b in inst["berths"]}
    return {v["id"]: [b for b in B if v["loa_m"] <= B[b]["length_m"]]
            for v in inst["vessels"]}


def assign_cranes(inst: dict, sequence: dict) -> dict:
    """(C3) 선박별 크레인 수 = 선박 상한과 선석 상한 중 작은 쪽.

    크레인 총량(C7)은 여기서 안 본다. 동시에 몇 척이 붙는지는
    2단계에서야 정해지므로, recourse 가 실제로 여유를 보고 미룬다.
    """
    B = {b["id"]: b for b in inst["berths"]}
    V = {v["id"]: v for v in inst["vessels"]}
    out = {}
    for b, seq in sequence.items():
        for i in seq:
            out[i] = max(V[i]["q_min"], min(V[i]["q_max"], B[b]["q_max"]))
    return out


# ── 시나리오 ───────────────────────────────────────────────────────────────
def nominal_scenario(inst: dict) -> dict:
    """명목 시나리오 = 인스턴스에 적힌 값 그대로."""
    return {"arrival_h":  {v["id"]: v["arrival_h"]  for v in inst["vessels"]},
            "workload_t": {v["id"]: v["workload_t"] for v in inst["vessels"]}}


# ── 평가 ───────────────────────────────────────────────────────────────────
BIG = 1e9

def score(inst: dict, s1: dict, scenarios: list[dict], agg) -> float:
    """1단계 결정을 시나리오들에 걸어보고 agg(평균 or 최댓값)로 묶는다."""
    vals = []
    for sc in scenarios:
        m = evaluate(inst, recourse(inst, s1, sc))
        vals.append(m["total_port_h"] if m["feasible"] else BIG)
    return agg(vals)


# ── 공통 탐색 ──────────────────────────────────────────────────────────────
def fcfs_sequence(inst: dict) -> dict:
    """선착순 배정. 모든 방법의 출발점이기도 하다."""
    B = {b["id"]: b for b in inst["berths"]}
    F = fits(inst)
    R, kap = inst["cranes"]["rate_tph"], inst["recovery"]["kappa"]
    t0 = inst["recovery"]["t_reopen_h"]
    free = {b: float(t0) for b in B}
    seq = {b: [] for b in B}
    for v in sorted(inst["vessels"], key=lambda x: (x["arrival_h"], x["id"])):
        i = v["id"]
        b = min(F[i], key=lambda b: (max(free[b], v["arrival_h"]), b))
        q = max(v["q_min"], min(v["q_max"], B[b]["q_max"]))
        start = max(free[b], v["arrival_h"], t0)
        free[b] = start + v["workload_t"] / (q * R * kap)
        seq[b].append(i)
    return seq


def _copy(s1): return {"sequence": {b: list(s) for b, s in s1["sequence"].items()},
                       "cranes": dict(s1["cranes"])}


def local_search(inst: dict, scenarios: list[dict], agg,
                 iters: int = 1000, seed: int = 7, restarts: int = 1,
                 start: dict | None = None):
    """FCFS 에서 출발해 '선석 이동' / '순서 교환' 두 수를 반복한다.

    restarts 번 되풀이하고 **자기 목적함수 기준** 가장 좋은 것을 돌려준다.
    평가지표를 보고 고르는 게 아니다 — 그건 커닝이다.

    왜 재시작이 필요한가: 한 번만 돌리면 시드에 따라 결과가 ±12시간 흔들려,
    방법 간 차이(약 10시간)보다 노이즈가 커진다. 그러면 비교 자체가 성립하지 않는다.
    """
    best_s1, best_val = None, float("inf")
    for r in range(max(1, restarts)):
        s1, val = _one_pass(inst, scenarios, agg, iters, seed + 1009 * r)
        if val < best_val:
            best_s1, best_val = s1, val
    return best_s1, best_val


def _one_pass(inst, scenarios, agg, iters, seed):
    rnd = random.Random(seed)
    F = fits(inst)
    cur = {"sequence": fcfs_sequence(inst), "cranes": {}}
    cur["cranes"] = assign_cranes(inst, cur["sequence"])
    best = score(inst, cur, scenarios, agg)
    ids = [v["id"] for v in inst["vessels"]]

    for _ in range(iters):
        cand = _copy(cur)
        i = rnd.choice(ids)
        src = next(b for b, s in cand["sequence"].items() if i in s)
        if rnd.random() < 0.5:                                   # 다른 선석으로
            tgt = rnd.choice(F[i])
            cand["sequence"][src].remove(i)
            pos = rnd.randint(0, len(cand["sequence"][tgt]))
            cand["sequence"][tgt].insert(pos, i)
        else:                                                    # 같은 선석 안 교환
            s = cand["sequence"][src]
            if len(s) < 2:
                continue
            p, q = rnd.sample(range(len(s)), 2)
            s[p], s[q] = s[q], s[p]
        cand["cranes"] = assign_cranes(inst, cand["sequence"])
        val = score(inst, cand, scenarios, agg)
        if val < best - 1e-9:
            cur, best = cand, val
    return cur, best
