"""saa — 표본평균근사 (Sample Average Approximation, RP).

불확실성의 **분포를 안다**고 보고, 거기서 K개를 뽑아 **평균**을 최소화한다.
    MODEL.md:  min (1/K) Σ_k f(s_k),   s_k ~ 참 분포

로버스트와 짝을 이룬다. 둘 다 같은 불확실성을 다루지만 가정이 다르다.
  · 로버스트: "최악이 이 범위" (집합) 을 가정하고 **max** 를 줄인다
  · SAA     : "분포가 이럴 것"  (확률) 을 가정하고 **평균** 을 줄인다
이 둘을 나란히 놓아야 "로버스트가 좋다/나쁘다"를 말할 근거가 생긴다.

다른 방법과의 관계
  · nominal 은 K=1, 시나리오가 명목값 하나인 SAA 다  -> 차이는 '시나리오 집합'뿐
  · VSS = EEV(nominal) - RP(SAA)                    -> 불확실성을 모형에 넣는 가치
  · 완전정보(WS) <= SAA(RP) 는 Birge & Louveaux 의 하한이다. 깨지면 하네스 버그다.
  · 주의: SAA <= nominal 은 **정리가 아니다.** 우리는 국소탐색을 쓰고, SAA 는
    표본 K개로 세운 계획을 본 적 없는 실현으로 평가받는다. 지는 건이 섞이는 게 정상.

지키는 규칙 (3-model/README.md)
  ① 시작 시각은 계산하지 않는다            -> core/recourse.py 가 모든 방법에 같은 규칙으로
  ② 탐색은 공용 core.planutil.local_search -> 탐색 엔진이 같아야 방법끼리 비교가 성립
  ③ 시드·반복수·재시작 수는 cfg 에서만 읽는다
  · real(실현값)은 완전정보 전용이라 읽지 않는다

확인
  python 3-model/tests/selfcheck.py saa
  python 3-model/run_all.py --only saa
"""
from __future__ import annotations
import math, random
from core.planutil import local_search

# config.yaml 을 못 읽었을 때만 쓰는 값. config.yaml 과 똑같이 둔다.
# 다르게 두면 pyyaml 이 없는 환경에서 saa 만 예산이 달라져 비교가 불공정해진다.
_DEFAULT_SEED       = 20261119
_DEFAULT_ITERS      = 1000
_DEFAULT_RESTARTS   = 8
_DEFAULT_K          = 15
_DEFAULT_CV_ERROR   = 0.20
_DEFAULT_JITTER_H   = 4.0

# 평가용 실현과 시드가 겹치지 않게 띄우는 간격.
# make_episodes.py:205 는 실현을 random.Random(i*1000 + k) 로 만든다
# (에피소드 i < 100, 실현 k < 100 이므로 최대 10만 미만).
# 그 구간을 통째로 피하려고 1,000,000 을 더한다. 겹치면 SAA 가 자기 답안지를
# 보고 푸는 셈이 되어 부당하게 좋아진다.
_SCENARIO_SEED_OFFSET = 1_000_000


def _mean(vals: list[float]) -> float:
    """시나리오 집계 함수. nominal 의 _mean 과 같은 꼴로 두어,
    두 방법의 차이가 '시나리오 집합'에서만 나오게 한다."""
    return sum(vals) / len(vals)


def _budget(cfg: dict | None) -> tuple[int, int, int]:
    """탐색 예산 (시드, 반복수, 재시작 수). 다섯 방법이 같은 값을 보도록 cfg 에서만 꺼낸다."""
    run = (cfg or {}).get("run") or {}
    seed     = int(run.get("seed", _DEFAULT_SEED)) % 100000      # START.md 와 같은 변환
    iters    = int(run.get("search_iters", _DEFAULT_ITERS))
    restarts = int(run.get("restarts", _DEFAULT_RESTARTS))
    return seed, iters, restarts


def _lognorm_unit(rnd: random.Random, cv: float) -> float:
    """평균 1, 변동계수 cv 인 로그정규 난수.

    ★ 함정: cv 를 로그정규의 sigma 에 그대로 넣으면 안 된다. 둘은 다른 값이다.
        sigma = sqrt(ln(1 + cv^2))          <- 변환
        exp(-sigma^2/2) 를 곱해 평균 1 보존
    그냥 넣으면 cv 0.2 에서는 티가 안 나다가 cv 1.8 에서 작업량 평균이 5배가 된다.
    그러면 모든 방법의 숫자가 같이 부풀어 '혼잡할수록 최적화가 유리하다' 같은
    가짜 결론이 나온다. make_samples.py / make_episodes.py 의 lognorm 과 같은 식이다.
    """
    if cv <= 0.0:
        return 1.0
    s = math.sqrt(math.log(1.0 + cv * cv))
    return rnd.lognormvariate(0.0, s) * math.exp(-s * s / 2.0)


def saa_scenarios(inst: dict, k: int, seed: int,
                  cv_error: float, jitter_h: float) -> list[dict]:
    """참 분포에서 K개 표본.

    make_episodes.py:206-211 의 실현 생성과 **같은 분포**를 쓴다.
        arrival_h  : 명목 + uniform(-jitter_h, +jitter_h),  음수는 0 으로
        workload_t : 명목 x 로그정규(cv = cv_error), 평균 보존

    분포만 같고 **시드는 다르다**. 같은 난수열을 쓰면 계획 표본과 평가 실현이
    겹쳐 SAA 만 부당하게 좋아진다 (_SCENARIO_SEED_OFFSET 참조).
    """
    rnd = random.Random(seed)
    vessels = inst["vessels"]
    out = []
    for _ in range(max(1, int(k))):
        out.append({
            "arrival_h":  {v["id"]: max(0.0, v["arrival_h"] + rnd.uniform(-jitter_h, jitter_h))
                           for v in vessels},
            "workload_t": {v["id"]: v["workload_t"] * _lognorm_unit(rnd, cv_error)
                           for v in vessels},
        })
    return out


def plan(inst, cfg, real=None):
    """참 분포 표본 K개에서 총 재항시간의 **평균**을 최소화하는 1단계 결정.

    입력
        inst : 인스턴스 (core/schema.py 형식)
        cfg  : config.yaml 을 읽은 dict
               run.seed / run.search_iters / run.restarts
               scenario.n_scenario_saa  (= K)
               uncertainty.workload_cv_error / arrival_jitter_h
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
    sc  = (cfg or {}).get("scenario") or {}
    unc = (cfg or {}).get("uncertainty") or {}
    k        = int(sc.get("n_scenario_saa", _DEFAULT_K))
    cv_error = float(unc.get("workload_cv_error", _DEFAULT_CV_ERROR))
    jitter_h = float(unc.get("arrival_jitter_h", _DEFAULT_JITTER_H))

    scenarios = saa_scenarios(inst, k, seed + _SCENARIO_SEED_OFFSET, cv_error, jitter_h)
    s1, _ = local_search(inst, scenarios, agg=_mean,
                         iters=iters, seed=seed, restarts=restarts)
    return s1
