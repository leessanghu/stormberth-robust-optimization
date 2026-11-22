# robust — 2단계 로버스트 최적화 (우리 연구의 본체)

> 공통 안내 → [`../../START.md`](../../START.md)

## 내가 할 일

**운이 나빠도 크게 망하지 않는 배정**을 찾습니다.
배가 언제 올지 정확히 모르는 상태에서 선석·순서·크레인을 미리 확정해야 합니다.

## 왜 "2단계"인가

```
1단계  배가 오기 전에 확정   선석 x_ib, 순서 y_ij, 크레인 q_i
         ↓  (여기서 실제 도착이 드러남)
2단계  그 결과로 정해짐     시작 S_i, 종료 D_i, 대기 W_i
```

1단계는 되돌릴 수 없습니다. 그래서 **"어떤 도착 패턴이 와도 견디는"** 1단계를 찾는 게 과제입니다.

## 불확실성을 어떻게 잡나

도착 시각이 명목값에서 ±`arrival_jitter_h` 안에서 흔들린다고 봅니다.
단, **전부 동시에 최악으로 흔들리지는 않는다**고 가정합니다 — 그러면 지나치게 보수적이 됩니다.

동시에 흔들리는 배의 수를 **Γ개로 제한**합니다 (Bertsimas–Sim 예산).

```
Γ = 0   아무도 안 흔들림  -> nominal 과 같아짐
Γ = 3   최대 3척까지 최악으로 흔들림   (config.yaml 기본값)
Γ = n   전부 흔들림  -> 지나치게 보수적
```

**Γ를 0부터 키우면서 결과가 어떻게 변하는지**가 주요 실험 중 하나입니다.

## 이번 학기 범위

기간이 짧아 아래는 **잘라냅니다.** 보고서에 "향후 과제"로 적습니다.

- 행 생성(row generation) → 시나리오 집합 + 꼭짓점 열거로 대체
- 조정 가능 recourse 전체 → 정책 제한 recourse로 고정
- 대규모 인스턴스 → 선박 20~30척, 선석 4~6개

## 내가 만들어야 공통 코드가 돌아갑니다

**공용 코드는 이미 올라와 있습니다.**
곧바로 자기 `plan.py` 부터 시작하면 됩니다.

```
core/milp.py       제약을 한 곳에 모은 MILP 코어
                   build(inst, scenarios, mode) 형태로
                   mode = "mean" | "minmax"
core/arrivals.py   실측 계수 -> 도착 시각 생성
```

`core/milp.py`·`core/planutil.py` 둘 다 올라와 있으므로 네 명이 동시에 착수할 수 있습니다.

## 목적함수가 다를 뿐 제약은 같습니다

```
nominal    시나리오 1개        목적 = 그 비용
로버스트    불확실성 집합 꼭짓점  목적 = 최악
```

그래서 코어 하나로 셋 다 커버됩니다.

## 확인

```bash
python 3-model/run_all.py --only robust
```

## 참고

→ [Robust Metaheuristics under Uncertainty for BAP and QCA: A Review](https://arxiv.org/abs/2608.19214)

2026년 리뷰입니다. min-max(MMRO)·기댓값(ERO)·2단계(TSRO)를 비교하는데,
**우리가 TSRO 자리**입니다. 벤치마크 생성 방식과 평가 지표가 정리돼 있습니다.

→ [The Price of Robustness (Bertsimas & Sim)](https://www.researchgate.net/publication/220244391_The_Price_of_Robustness)

Γ 예산 개념의 원전입니다.
