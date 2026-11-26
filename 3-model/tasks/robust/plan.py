"""robust — Γ-예산 불확실성의 최악을 최소화 (min-max).

제약은 nominal 과 **똑같다**. 다른 건 둘뿐이다.
  · 시나리오가 1개가 아니라 불확실성 집합의 '꼭짓점' 여러 개
  · 목적이 평균이 아니라 **최댓값**  (epigraph:  min θ  s.t.  θ >= f(s) ∀s)

Bertsimas-Sim 예산 (The Price of Robustness, Oper. Res. 52(1), 2004)
    ã_i = a_i + ξ_i·δ_i,   ξ_i ∈ [0,1],   Σ_i ξ_i <= Γ
  "동시에 최악이 되는 선박은 많아야 Γ척"이라고 본다.
  Γ = 0  -> nominal 과 같아진다
  Γ = n  -> 전부 흔들림. 지나치게 보수적

  >> ★ 꼭짓점은 "ξ_i 중 최대 Γ개가 1, 나머지 0"인 0/1 벡터다.
  >>    선박 25척에 Γ=3 이면 C(25,3) = 2,300 개라 전부는 못 넣는다. **표본**을 쓴다.
  >>    따라서 이것은 엄밀한 Γ-로버스트가 아니라 **근사 Γ-로버스트**다.
  >>    보고서에 반드시 그렇게 밝힌다. 정석인 행 생성(row generation)은 향후 과제.

다른 방법과의 관계
  · SAA 와 정면으로 대비된다 — 같은 불확실성, 집합(max) 대 분포(평균)
  · Γ 를 0 부터 키우며 결과를 보는 것이 주요 실험이다 (price of robustness)

지키는 규칙 (3-model/README.md)
  ① 시작 시각은 계산하지 않는다            -> core/recourse.py 가 모든 방법에 같은 규칙으로
  ② 탐색은 공용 core.planutil.local_search -> 탐색 엔진이 같아야 방법끼리 비교가 성립
  ③ 시드·반복수·재시작 수는 cfg 에서만 읽는다
  · real(실현값)은 완전정보 전용이라 읽지 않는다
  · core/milp.py 는 쓰지 않는다. 20~29척 실제 인스턴스는 못 푼다 (milp.py 머리말)

확인
  python 3-model/tests/selfcheck.py robust
  python 3-model/run_all.py --only robust
"""
from __future__ import annotations
import random
from core.planutil import local_search, nominal_scenario

# config.yaml 을 못 읽었을 때만 쓰는 값. config.yaml 과 똑같이 둔다.
_DEFAULT_SEED     = 20261119
_DEFAULT_ITERS    = 1000
_DEFAULT_RESTARTS = 8
_DEFAULT_GAMMA    = 3
_DEFAULT_N_VERTEX = 6
_DEFAULT_LATE_H   = 4.0
_DEFAULT_HEAVY    = 1.20


def _budget(cfg: dict | None) -> tuple[int, int, int]:
    """탐색 예산 (시드, 반복수, 재시작 수). 다섯 방법이 같은 값을 보도록 cfg 에서만 꺼낸다."""
    run = (cfg or {}).get("run") or {}
    seed     = int(run.get("seed", _DEFAULT_SEED)) % 100000      # START.md 와 같은 변환
    iters    = int(run.get("search_iters", _DEFAULT_ITERS))
    restarts = int(run.get("restarts", _DEFAULT_RESTARTS))
    return seed, iters, restarts


def gamma_vertices(inst: dict, gamma: int, n_vertex: int, seed: int,
                   late_h: float, heavy_mult: float) -> list[dict]:
    """Γ-예산 집합의 꼭짓점 표본 + 명목 시나리오.

    꼭짓점 하나 = "Γ척만 최악으로 흔들리고 나머지는 명목값"
        arrival_h  += late_h       (더 늦게 온다)
        workload_t *= heavy_mult   (더 무겁다)

    명목 시나리오를 항상 포함한다. ξ = 0 도 집합의 원소이므로 ( Σξ_i <= Γ 를
    만족한다 ) 빠뜨릴 이유가 없고, Γ=0 이면 nominal 과 정확히 같아진다.

    ★ 어느 Γ척을 고르나 — 재개 시각에 가까운 배를 우선 후보로 둔다.
      우리는 **최댓값**을 근사한다. 전체에서 균등하게 뽑으면 아무 데도 안 걸리는
      꼭짓점이 섞여 max 를 과소평가하고, 그러면 방어가 헐거워진다.
      병목은 항만 재개 직후에 몰리므로 |a_i - t_reopen| 이 작은 쪽 절반을
      후보 풀로 삼는다. 균등 표본보다 치우쳤지만, 목적이 max 의 근사이므로
      더 나쁜 꼭짓점을 찾는 쪽이 맞다. 이것도 근사라는 사실은 위에 적은 대로다.

    late_h / heavy_mult 는 **평가 분포에서 유도한 값**이어야 한다 (config.yaml 주석).
    임의로 키우면 평가에서 일어나지도 않는 시나리오를 방어하느라 손해만 본다.
    """
    rnd = random.Random(seed)
    ids = [v["id"] for v in inst["vessels"]]
    t0  = inst["recovery"]["t_reopen_h"]
    nom = nominal_scenario(inst)
    out = [nom]

    g = max(0, min(int(gamma), len(ids)))
    if g == 0:
        return out                                   # Γ=0 -> nominal 과 동일

    pri  = sorted(ids, key=lambda i: (abs(nom["arrival_h"][i] - t0), i))
    pool = pri[:max(g, len(ids) // 2)]
    for _ in range(max(0, int(n_vertex))):
        hit = set(rnd.sample(pool, min(g, len(pool))))
        out.append({
            "arrival_h":  {i: nom["arrival_h"][i] + (late_h if i in hit else 0.0)
                           for i in ids},
            "workload_t": {i: nom["workload_t"][i] * (heavy_mult if i in hit else 1.0)
                           for i in ids},
        })
    return out


def plan(inst, cfg, real=None):
    """Γ-예산 꼭짓점 표본에서 총 재항시간의 **최댓값**을 최소화하는 1단계 결정.

    입력
        inst : 인스턴스 (core/schema.py 형식)
        cfg  : config.yaml 을 읽은 dict
               run.seed / run.search_iters / run.restarts
               scenario.gamma / n_vertex / late_h / heavy_mult
        real : 무시한다. 실현값을 보고 짜는 것은 완전정보(perfect)의 몫이다

    반환
        {"sequence": {선석id: [선박id, ...]},   # 선석마다 붙일 순서대로
         "cranes":   {선박id: 크레인수}}

    제약 (run_all.py 의 validate_stage1 이 검사)
        (C1) 모든 선박이 정확히 한 번씩      <- local_search 의 이동이 선박을 잃거나 복제하지 않음
        (C2) loa_m <= 그 선석의 length_m    <- 이동 대상 선석을 planutil.fits 로만 고름
        (C3) q_min <= 크레인수 <= min(q_max, 그 선석 q_max)  <- planutil.assign_cranes

    시작 시각은 반환하지 않는다. 같은 cfg 면 같은 계획이 나온다 (재현성).
    """
    seed, iters, restarts = _budget(cfg)
    sc = (cfg or {}).get("scenario") or {}
    gamma      = int(sc.get("gamma",      _DEFAULT_GAMMA))
    n_vertex   = int(sc.get("n_vertex",   _DEFAULT_N_VERTEX))
    late_h     = float(sc.get("late_h",     _DEFAULT_LATE_H))
    heavy_mult = float(sc.get("heavy_mult", _DEFAULT_HEAVY))

    verts = gamma_vertices(inst, gamma, n_vertex, seed + gamma, late_h, heavy_mult)
    s1, _ = local_search(inst, verts, agg=max,
                         iters=iters, seed=seed, restarts=restarts)
    return s1
