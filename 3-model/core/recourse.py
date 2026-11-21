"""★ 공용 복구 규칙 (2단계). 이 파일이 이 프로젝트에서 가장 중요하다.

모든 방법(FCFS·nominal·SAA·로버스트)이 **같은 이 함수**로 2단계를 푼다.
방법마다 2단계를 따로 구현하면 비교가 성립하지 않는다. 수정 권한: 이상후만.

규칙 (list scheduling, 결정론적·유일):
  1단계가 선석별 접안 순서와 선박별 크레인 수를 확정했으므로,
  남은 일은 "언제 시작하나"뿐이다. 다음 조건이 모두 충족되는 가장 이른 시각에 시작한다.
     (a) 재개 시각을 지났다        t >= t_reopen
     (b) 배가 도착했다             t >= arrival
     (c) 그 선석의 앞 배가 끝났다
     (d) 남은 크레인이 충분하다    여유 >= q_i
  (d)에서 여럿이 경합하면 (도착시각, 선박id) 순으로 우선한다.

이건 '최적'이 아니라 '규칙'이다. 모형 목적값은 이 규칙 하 평가값의 하한이며,
방법 간 비교는 평가값으로만 한다. (제안서 §6)
"""
from __future__ import annotations

EPS = 1e-9

def crane_efficiency(t: float, rec: dict) -> float:
    """재개 직후 크레인 생산성 저하. kappa에서 시작해 kappa_recover_h에 걸쳐 1.0으로."""
    k, h = rec["kappa"], rec.get("kappa_recover_h", 0.0)
    if h <= 0:
        return k
    x = (t - rec["t_reopen_h"]) / h
    return k + (1.0 - k) * min(max(x, 0.0), 1.0)

def handling_hours(workload_t: float, q: int, rate_tph: float,
                   t_start: float, rec: dict) -> float:
    """처리시간. 생산성은 시작 시각 기준으로 한 번 결정한다 (명시적 근사)."""
    return workload_t / (q * rate_tph * crane_efficiency(t_start, rec))

def recourse(inst: dict, s1: dict, real: dict) -> dict:
    """1단계 결정 + 실현값 -> 실제 일정.

    real = {"arrival_h": {vid: float}, "workload_t": {vid: float}}
    반환 = {"start_h": {...}, "end_h": {...}, "wait_h": {...}, "feasible": bool}
    """
    V   = {v["id"]: v for v in inst["vessels"]}
    rec = inst["recovery"]
    Q   = inst["cranes"]["total"]
    rate= inst["cranes"]["rate_tph"]
    t0  = rec["t_reopen_h"]

    arrival  = {k: float(real["arrival_h"][k])  for k in V}
    workload = {k: float(real["workload_t"][k]) for k in V}

    ptr        = {b: 0 for b in s1["sequence"]}      # 선석별 다음 처리 위치
    berth_free = {b: t0 for b in s1["sequence"]}     # 선석이 비는 시각
    running    = []                                   # (종료시각, vid, 크레인수)
    free_q     = Q
    start, end = {}, {}
    now = t0

    while len(end) < len(V):
        # 지금 시작 가능한 후보 (선석별 맨 앞 배만)
        cand = []
        for b, seq in s1["sequence"].items():
            if ptr[b] >= len(seq):
                continue
            vid = seq[ptr[b]]
            if berth_free[b] <= now + EPS and arrival[vid] <= now + EPS:
                cand.append((arrival[vid], vid, b))
        cand.sort()

        started = False
        for _, vid, b in cand:
            q = s1["cranes"][vid]
            if q <= free_q:
                h = handling_hours(workload[vid], q, rate, now, rec)
                start[vid] = now
                end[vid]   = now + h
                running.append((now + h, vid, q))
                free_q -= q
                ptr[b] += 1
                berth_free[b] = now + h
                started = True
        if started:
            continue

        # 아무것도 못 시작하면 다음 사건으로 시간을 넘긴다
        nxt = []
        if running:
            nxt.append(min(r[0] for r in running))
        for b, seq in s1["sequence"].items():
            if ptr[b] < len(seq):
                vid = seq[ptr[b]]
                nxt.append(max(arrival[vid], berth_free[b], t0))
        nxt = [t for t in nxt if t > now + EPS]
        if not nxt:                      # 진행 불가 — 1단계가 잘못됐다는 뜻
            return {"feasible": False, "start_h": start, "end_h": end, "wait_h": {}}
        now = min(nxt)
        done = [r for r in running if r[0] <= now + EPS]
        for _, _, q in done:
            free_q += q
        running = [r for r in running if r[0] > now + EPS]

    wait = {vid: start[vid] - arrival[vid] for vid in V}
    return {"feasible": True, "start_h": start, "end_h": end, "wait_h": wait}
