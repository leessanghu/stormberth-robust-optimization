"""★ 공용 제약 (1단계 MILP). MODEL.md 의 C1~C10 이 여기 한 번만 구현돼 있다.

**제약은 모든 방법이 똑같다. 다른 건 목적함수와 시나리오 집합뿐이다.**
그래서 담당자는 이 파일을 고치지 않는다. 고치면 모든 방법의 결과가 같이 바뀐다.
수정 권한: 이상후만.

담당자가 하는 일은 두 줄이다.

    sc = 내_시나리오_만들기(inst)              # 어떤 상황을 상정하는가
    model = build(inst, sc, mode="mean")      # mean = 평균, minmax = 최악
    return solve(model, cfg)

솔버: pulp 4.2 에는 CBC 가 없다. scipy.optimize.milp (HiGHS 백엔드) 를 쓴다.
      scipy 가 이미 깔려 있으므로 추가 설치가 필요 없다.

[한계 — 반드시 알고 쓸 것]
  · big-M 이접제약(C6) + 시간분할 변수(C7,C8) 때문에 **6척에서도 240초 안에
    최적성을 증명하지 못한다** (실측). 20~29척 실제 인스턴스는 못 푼다.
  · 그래서 본 실험은 core/planutil.local_search (휴리스틱) 로 돌린다.
    이 파일은 (a) 보고서 수식과 코드를 1:1로 맞추고 (b) 작은 인스턴스에서
    휴리스틱이 최적에서 얼마나 떨어지는지 재는 데 쓴다.
  · MILP 는 κ 를 상수로 본다. recourse 는 kappa_recover_h 에 걸쳐 회복시킨다.
    따라서 **모형 목적값 != recourse 평가값**. 비교는 언제나 평가값으로만 한다.
"""
from __future__ import annotations
import numpy as np
from scipy.optimize import milp as _milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix, vstack


def nominal_scenario(inst: dict) -> dict:
    """명목 시나리오 = 인스턴스에 적힌 값 그대로."""
    return {"arrival_h":  {v["id"]: v["arrival_h"]  for v in inst["vessels"]},
            "workload_t": {v["id"]: v["workload_t"] for v in inst["vessels"]}}


def build(inst: dict, scenarios: list[dict], mode: str = "mean", dt: float = 2.0) -> dict:
    """MODEL.md C1~C10 을 그대로 세운다.

    scenarios : [{"arrival_h": {vid: h}, "workload_t": {vid: t}}, ...]
    mode      : "mean"   -> min (1/|S|) Σ_s f(s)      nominal · SAA · 완전정보
                "minmax" -> min θ  s.t. θ >= f(s) ∀s  로버스트 (epigraph)
    dt        : 시간 구간 길이 Δ. 작을수록 정확하고 느리다.
    """
    if mode not in ("mean", "minmax"):
        raise ValueError("mode 는 'mean' 또는 'minmax'")
    if not scenarios:
        raise ValueError("시나리오가 비었다")

    V, B = inst["vessels"], inst["berths"]
    n, nb, ns = len(V), len(B), len(scenarios)
    Q, rate = inst["cranes"]["total"], inst["cranes"]["rate_tph"]
    rec = inst["recovery"]; t0, kap = rec["t_reopen_h"], rec["kappa"]
    Hor = inst["horizon_h"]; M = Hor * 1.5
    T = int(np.ceil((Hor - t0) / dt))

    qcap = max(b["q_max"] for b in B)
    Kopt = [list(range(max(1, v["q_min"]), min(v["q_max"], qcap) + 1)) for v in V]
    FIT  = [[j for j, b in enumerate(B) if v["loa_m"] <= b["length_m"]] for v in V]   # (C2)
    for i, f in enumerate(FIT):
        if not f:
            raise ValueError("선박 %s 가 들어갈 선석이 없다 (C2 위반)" % V[i]["id"])

    # ── 변수 배치 ──────────────────────────────────────────────────────────
    pos = {}; p = 0
    def alloc(name, cnt):
        nonlocal p
        pos[name] = p; p += cnt
    alloc("x", n * nb)                                   # x_ib
    PAIR = [(i, j) for i in range(n) for j in range(i + 1, n)]
    pid = {pr: k for k, pr in enumerate(PAIR)}
    alloc("z", len(PAIR))                                # z_ij
    uoff, c1 = [0] * n, 0
    for i in range(n): uoff[i] = c1; c1 += len(Kopt[i])
    alloc("u", c1)                                       # u_ik
    alloc("S", n * ns); alloc("D", n * ns)               # S_i^s, D_i^s
    alloc("sg", n * T * ns)                              # sigma_it^s
    voff, c2 = [0] * n, 0
    for i in range(n): voff[i] = c2; c2 += len(Kopt[i]) * T
    alloc("v", c2 * ns)                                  # v_ikt^s
    alloc("th", 1 if mode == "minmax" else 0)            # theta
    N = p

    X  = lambda i, b: pos["x"] + i * nb + b
    Z  = lambda i, j: pos["z"] + pid[(i, j)]
    U  = lambda i, k: pos["u"] + uoff[i] + k
    SS = lambda i, s: pos["S"] + s * n + i
    DD = lambda i, s: pos["D"] + s * n + i
    SG = lambda i, t, s: pos["sg"] + s * n * T + i * T + t
    VV = lambda i, k, t, s: pos["v"] + s * c2 + voff[i] + k * T + t
    TH = lambda: pos["th"]

    integ = np.zeros(N); lb = np.zeros(N); ub = np.full(N, np.inf)
    for i in range(n):
        for b in range(nb):
            integ[X(i, b)] = 1
            ub[X(i, b)] = 1.0 if b in FIT[i] else 0.0        # (C2) 전처리 고정
        for k in range(len(Kopt[i])):
            integ[U(i, k)] = 1; ub[U(i, k)] = 1
        for s in range(ns):
            lb[SS(i, s)] = max(scenarios[s]["arrival_h"][V[i]["id"]], t0)   # (C5)
            ub[DD(i, s)] = Hor                                              # (C10)
            for t in range(T):
                integ[SG(i, t, s)] = 1; ub[SG(i, t, s)] = 1
                for k in range(len(Kopt[i])): ub[VV(i, k, t, s)] = 1
    for pr in PAIR:
        integ[Z(*pr)] = 1; ub[Z(*pr)] = 1

    rows, lo, hi = [], [], []
    def add(d, l, h):
        r = lil_matrix((1, N))
        for kk, val in d.items(): r[0, kk] = r[0, kk] + val
        rows.append(r); lo.append(l); hi.append(h)

    for i in range(n):
        add({X(i, b): 1 for b in FIT[i]}, 1, 1)                             # (C1)
        add({U(i, k): 1 for k in range(len(Kopt[i]))}, 1, 1)                # (C3)
        d = {U(i, k): Kopt[i][k] for k in range(len(Kopt[i]))}
        for b in FIT[i]: d[X(i, b)] = d.get(X(i, b), 0) - B[b]["q_max"]
        add(d, -np.inf, 0)                                                  # (C3) 선석 상한
        for s in range(ns):
            w = scenarios[s]["workload_t"][V[i]["id"]]
            d = {DD(i, s): 1, SS(i, s): -1}
            for k, q in enumerate(Kopt[i]): d[U(i, k)] = -w / (rate * kap * q)
            add(d, 0, 0)                                                    # (C4) D = S + H
            d = {SG(i, t, s): -dt for t in range(T)}
            for k, q in enumerate(Kopt[i]): d[U(i, k)] = w / (rate * kap * q)
            add(d, -np.inf, 0)                                              # (C8) 구간 수 하한
            for t in range(T):
                tt = t0 + t * dt
                # (C8) '포함'이 아니라 '겹침'. 포함으로 걸면 H_i 가 dt 배수가 아닐 때
                #      위 구간수 하한과 충돌해 모형이 실행불가가 된다 (MODEL.md 참조).
                #      겹침은 크레인 점유를 과대계상하므로 (C7) 방향으로 보수적 = 안전.
                add({SS(i, s): 1, SG(i, t, s): M}, -np.inf, tt + dt + M)
                add({DD(i, s): -1, SG(i, t, s): M}, -np.inf, M - tt)
                for k in range(len(Kopt[i])):                               # (C7) 선형화
                    add({VV(i, k, t, s): 1, U(i, k): -1}, -np.inf, 0)
                    add({VV(i, k, t, s): 1, SG(i, t, s): -1}, -np.inf, 0)
                    add({VV(i, k, t, s): -1, U(i, k): 1, SG(i, t, s): 1}, -np.inf, 1)

    for s in range(ns):                                                     # (C7) 크레인 총량
        for t in range(T):
            d = {}
            for i in range(n):
                for k, q in enumerate(Kopt[i]): d[VV(i, k, t, s)] = q
            add(d, -np.inf, Q)

    for (i, j) in PAIR:                                                     # (C6) 비중첩
        for b in range(nb):
            if b not in FIT[i] or b not in FIT[j]: continue
            for s in range(ns):
                add({DD(i, s): 1, SS(j, s): -1, Z(i, j): M, X(i, b): M, X(j, b): M}, -np.inf, 3 * M)
                add({DD(j, s): 1, SS(i, s): -1, Z(i, j): -M, X(i, b): M, X(j, b): M}, -np.inf, 2 * M)

    cvec = np.zeros(N)
    if mode == "mean":
        for s in range(ns):
            for i in range(n): cvec[DD(i, s)] += 1.0 / ns
    else:
        cvec[TH()] = 1.0
        for s in range(ns):                                                 # epigraph
            d = {TH(): -1.0}
            for i in range(n): d[DD(i, s)] = 1.0
            add(d, -np.inf, 0)

    # 목적함수는 Σ D 이고 MODEL.md 는 Σ(D - a) 다. a 는 상수라 argmin 이 같다.
    # 보고서에 쓸 값은 recourse 평가값이므로 이 상수는 신경쓰지 않는다.
    return {"A": vstack(rows).tocsc(), "lo": np.array(lo), "hi": np.array(hi),
            "c": cvec, "integrality": integ, "lb": lb, "ub": ub,
            "_meta": {"inst": inst, "X": X, "U": U, "SS": SS, "Kopt": Kopt,
                      "n": n, "nb": nb, "mode": mode, "nvar": N, "ncon": len(rows)}}


def solve(model: dict, cfg: dict | None = None, verbose: bool = False):
    """푼다. 반환은 run_all 이 받는 1단계 형식 {"sequence", "cranes"}.

    cfg["run"]["time_limit_s"] 를 그대로 쓴다. 코드에 박지 말 것.
    시간초과로 최적성이 증명 안 되면 **경고를 찍는다** — 보고서에 반드시 밝혀야 한다.
    """
    run = (cfg or {}).get("run", {})
    tl  = float(run.get("time_limit_s", 60))
    gap = float(run.get("mip_rel_gap", 1e-4))
    res = _milp(c=model["c"],
                constraints=LinearConstraint(model["A"], model["lo"], model["hi"]),
                integrality=model["integrality"],
                bounds=Bounds(model["lb"], model["ub"]),
                options={"time_limit": tl, "mip_rel_gap": gap, "disp": verbose})
    m = model["_meta"]
    if res.x is None:
        raise RuntimeError("MILP 해 없음: %s" % res.message)
    if "Optimal" not in str(res.message):
        print("  ! MILP 최적성 미증명 (%s) — 보고서에 '시간제한 내 최선해'라고 밝힐 것"
              % res.message.split(".")[0])
    x, inst = res.x, m["inst"]
    V, B = inst["vessels"], inst["berths"]
    order = {b["id"]: [] for b in B}
    for i in range(m["n"]):
        b = int(np.argmax([x[m["X"](i, bb)] for bb in range(m["nb"])]))
        order[B[b]["id"]].append((x[m["SS"](i, 0)], V[i]["id"]))
    seq = {b: [vid for _, vid in sorted(vs)] for b, vs in order.items()}
    cranes = {}
    for i in range(m["n"]):
        k = int(np.argmax([x[m["U"](i, kk)] for kk in range(len(m["Kopt"][i]))]))
        cranes[V[i]["id"]] = m["Kopt"][i][k]
    return {"sequence": seq, "cranes": cranes}
