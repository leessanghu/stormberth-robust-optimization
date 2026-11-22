"""saa — 표본평균근사 (Sample Average Approximation, RP).

불확실성의 **분포를 알고 있다**고 보고, 거기서 K개를 뽑아 **평균**을 최소화한다.

로버스트와 비교해 보면 차이가 분명하다.
  · 로버스트: "최악이 이 정도일 것" (집합) 을 가정하고 **max** 를 줄인다
  · SAA     : "분포가 이럴 것"      (확률) 을 가정하고 **평균** 을 줄인다

[내가 쓸 것 1 — 시나리오 K개 뽑기]  ← 이 파일의 핵심
  make_samples.py 가 '실현'을 만드는 방식과 **같은 분포**에서 뽑는다.

      arrival_h  : 명목 + uniform(-jitter, +jitter)
      workload_t : 명목 x 로그정규(CV = workload_cv_error)

  >> ★ 함정: CV 를 로그정규의 sigma 에 그대로 넣으면 안 된다. 변환이 필요하다.
  >>    sigma = sqrt(ln(1 + CV^2))
  >>    평균 보존을 위해 exp(-sigma^2/2) 를 곱한다
  >>    (그냥 넣으면 CV 0.2 에선 티가 안 나다가 CV 1.8 에서 작업량 평균이 5배가 된다.)

  >> ★ 시드: 계획에 쓴 표본과 평가에 쓰는 실현이 **겹치면 안 된다.**
  >>    겹치면 자기 답안지를 보고 푸는 셈이라 SAA 가 부당하게 좋아진다.
  >>    cfg["run"]["seed"] 에서 충분히 떨어뜨릴 것.

  K 는 cfg["scenario"]["n_scenario_saa"] 에서 읽는다.

[내가 쓸 것 2 — 목적함수]
      s1, _ = local_search(inst, scenarios, agg=평균, ...)     # max 가 아니라 평균

[정리 — 내 결과가 이 사이에 있어야 한다]
      완전정보(WS)  <=  SAA(RP)  <=  nominal(EEV)
  Birge & Louveaux. run_all.py 가 자동 점검한다. 깨지면 어딘가 버그다.

[확인]  python 3-model/run_all.py --only saa
"""
from __future__ import annotations
import math, random
from core.planutil import local_search


def saa_scenarios(inst, k, seed, cv_error, jitter_h):
    """참 분포에서 K개 표본. 평가용 실현과 시드가 겹치면 안 된다."""
    raise NotImplementedError("담당자가 구현합니다")


def plan(inst, cfg, real=None):
    raise NotImplementedError("담당자가 구현합니다 — tasks/saa/README.md 참조")
