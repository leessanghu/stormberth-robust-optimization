"""robust — Γ-예산 불확실성의 최악을 최소화 (min-max).

제약은 nominal 과 **똑같다**. 다른 건 둘뿐이다.
  · 시나리오가 1개가 아니라 불확실성 집합의 '꼭짓점' 여러 개
  · 목적이 평균이 아니라 **최댓값**  (epigraph:  min θ  s.t.  θ >= f(s) ∀s)

[내가 쓸 것 1 — 꼭짓점 만들기]  ← 이 파일에서 제일 중요한 부분
  Bertsimas-Sim 예산: "동시에 최악이 되는 선박은 많아야 Γ척"이라고 본다.
  Γ척을 고르는 경우의 수가 C(n,Γ) 라 전부는 못 넣는다. **표본**을 쓴다.

      · 명목값에서 출발
      · 무작위로 Γ척을 골라 그 배만 악화시킨다
          arrival_h  += late_h        (더 늦게 온다)
          workload_t *= heavy_mult    (더 무겁다)
      · 이걸 n_vertex 번 되풀이해 리스트로 반환

  Γ, n_vertex, late_h, heavy_mult 는 **cfg["scenario"] 에서 읽는다.**
  난수 시드도 cfg["run"]["seed"] 에서 읽어야 재현된다.

  >> 전부가 아니라 표본이므로 이건 엄밀한 Γ-로버스트가 아니라 **근사**다.
  >> 보고서에 '근사 Γ-로버스트'라고 **반드시** 밝힐 것.

[내가 쓸 것 2 — 목적함수]
      s1, _ = local_search(inst, verts, agg=max, ...)     # 평균이 아니라 max

[확인]  python 3-model/run_all.py --only robust
"""
from __future__ import annotations
import random
from core.planutil import local_search, nominal_scenario


def gamma_vertices(inst, gamma, n, seed, late_h, heavy):
    """Γ-예산 불확실성 집합의 꼭짓점 표본."""
    raise NotImplementedError("담당자가 구현합니다")


def plan(inst, cfg, real=None):
    raise NotImplementedError("담당자가 구현합니다 — tasks/robust/README.md 참조")
