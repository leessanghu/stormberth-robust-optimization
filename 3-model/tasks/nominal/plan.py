"""nominal — 결정론 최적화. 명목 시나리오 1개 (확률계획 용어로 EEV).

배가 인스턴스에 적힌 시각(arrival_h)에 오고, 적힌 작업량(workload_t)만큼
일한다고 **믿고**, 그 한 시나리오에서 총 재항시간 Σ(D−a)가 가장 작은
1단계 결정(선석 배정 · 선석별 순서 · 크레인 수)을 찾는다.
    MODEL.md:  S = { s₀ },  min f(s₀)

다른 방법과의 관계
  · 로버스트에서 Γ=0 으로 둔 것과 같다      -> 로버스트 Γ 실험의 기준점
  · SAA(RP)와 짝지으면 VSS = EEV − RP      -> 불확실성을 모형에 넣는 가치
  · FCFS 보다 나쁠 수 있다. 명목 시나리오에 과적합하기 때문이다.
    run_all.py 도 'nominal <= FCFS 는 정리가 아니다'로 취급한다. 버그가 아니라 결과다.

지키는 규칙 (3-model/README.md)
  ① 시작 시각은 계산하지 않는다            -> core/recourse.py 가 모든 방법에 같은 규칙으로
  ② 탐색은 공용 core.planutil.local_search -> 탐색 엔진이 같아야 방법끼리 비교가 성립
  ③ 시드·반복수·재시작 수는 cfg 에서만 읽는다
  · real(실현값)은 완전정보 전용이라 읽지 않는다
  · core/milp.py 는 쓰지 않는다. 20~29척 실제 인스턴스는 못 푼다 (milp.py 머리말)

일부러 하지 않는 것
  명목 시나리오만 보는 것이 이 방법의 정의다. 도착 흔들림에 대비하는 장치
  (여유 시간, 도착 순서 역전 금지 등)를 넣으면 로버스트와 구분이 사라지고
  EEV 기준선이 오염된다. 과적합은 여기서 고치지 않고 결과에서 **측정**한다.

확인
  python 3-model/tests/selfcheck.py nominal
  python 3-model/run_all.py --only nominal
"""
from __future__ import annotations
from core.planutil import local_search, nominal_scenario

# config.yaml 을 못 읽었을 때만 쓰는 값. config.yaml 의 run 절과 똑같이 둔다.
# 다르게 두면 pyyaml 이 없는 환경에서 nominal 만 예산이 달라져 비교가 불공정해진다.
_DEFAULT_SEED     = 20261119
_DEFAULT_ITERS    = 1000
_DEFAULT_RESTARTS = 8


def _mean(vals: list[float]) -> float:
    """시나리오 집계 함수. 시나리오가 1개라 평균 = 그 값이다.
    SAA 와 같은 꼴(평균)로 두어, 두 방법의 차이가 '시나리오 집합'에서만 나오게 한다."""
    return sum(vals) / len(vals)


def _budget(cfg: dict | None) -> tuple[int, int, int]:
    """탐색 예산 (시드, 반복수, 재시작 수). 다섯 방법이 같은 값을 보도록 cfg 에서만 꺼낸다."""
    run = (cfg or {}).get("run") or {}
    seed     = int(run.get("seed", _DEFAULT_SEED)) % 100000      # START.md 와 같은 변환
    iters    = int(run.get("search_iters", _DEFAULT_ITERS))
    restarts = int(run.get("restarts", _DEFAULT_RESTARTS))
    return seed, iters, restarts


def plan(inst, cfg, real=None):
    """명목 시나리오 1개에서 총 재항시간을 최소화하는 1단계 결정.

    입력
        inst : 인스턴스 (core/schema.py 형식)
        cfg  : config.yaml 을 읽은 dict. run.seed / run.search_iters / run.restarts 를 쓴다
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
    scenarios = [nominal_scenario(inst)]        # arrival_h, workload_t = 인스턴스 값 그대로
    s1, _ = local_search(inst, scenarios, agg=_mean,
                         iters=iters, seed=seed, restarts=restarts)
    return s1
