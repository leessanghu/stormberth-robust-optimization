# 3. 최적화 모형

태풍 후 밀린 배를 선석·크레인에 어떻게 배정할지 푼다.
전제 검증([`docs/findings.md`](../docs/findings.md))에서 나온 실측값이 여기 파라미터로 들어간다.

---

## 핵심 규칙 3개

이 셋이 깨지면 방법 간 비교 자체가 성립하지 않는다.

**① 1단계와 2단계를 섞지 않는다.**

```
1단계 (사전 확정)   선석 배정 x_ib, 접안 순서 y_ij, 크레인 수 q_i   ← planner가 정함
2단계 (사후 결과)   시작 S_i, 종료 D_i, 대기 W_i                  ← recourse가 정함
```

`plan()`은 **순서와 크레인 수만** 반환한다. 시작 시각은 반환하지 않는다.
2단계는 `core/recourse.py` **한 곳**에서만 계산한다.

**② 숫자는 `run_all.py`에서만 나온다.**
각자 스크립트로 뽑은 수치는 보고서에 못 쓴다.

**③ 설정은 `config.yaml`에만 둔다.**
`time_limit`, `seed`, `gamma`를 planner 안에 하드코딩하지 않는다.

---

## 구조

```
config.yaml           공유 설정 (time limit, 시드, Γ, 격자)
core/
  schema.py           인스턴스·stage1 스키마 + 검증
  recourse.py    ★    공용 복구 규칙 — 팀원 A만 수정
  evaluate.py         지표 계산
  milp.py        ★    공용 MILP 코어 — 제약은 여기 한 곳에만
  arrivals.py         도착 과정 생성 (실측 계수 -> 도착 시각)
planners/
  fcfs.py             팀원 B
  nominal.py          팀원 C
  saa.py              팀원 D
  robust.py           팀원 A
  perfect.py          팀원 A
instances/            인스턴스 + 실현 시나리오 (같이 커밋)
tests/golden.py       손으로 푼 답과 대조
run_all.py            전부 동일 조건으로 실행
make_samples.py       1주차용 샘플 인스턴스
```

---

## 환경 만들기

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt       # pandas, numpy, pulp, pyyaml
```

솔버는 **PuLP + CBC**를 쓴다. `pip install pulp` 하면 CBC가 같이 깔려서 따로 설치할 게 없다.
느리면 나중에 HiGHS(`pip install highspy`)나 Gurobi 학생 라이선스로 갈아끼운다.
모델 코드는 그대로 두고 솔버만 바꾸면 된다.

---

## 돌려보기

```bash
python 3-model/tests/golden.py        # ① 복구 규칙이 맞나 (제일 먼저)
python 3-model/make_samples.py        # ② 샘플 인스턴스 3개
python 3-model/run_all.py --demo      # ③ 하네스 자체 점검
python 3-model/run_all.py             # ④ 진짜 실행
python 3-model/run_all.py --only fcfs # 내 것만
```

`--demo`는 임시 planner로 파이프라인만 확인한다. 결과 보고에는 쓰지 않는다.

지금 `--demo`를 돌리면 이렇게 나온다 — 혼잡할수록 재항시간이 커지는 게 보인다.

```
sample_rho60_close24_s1  (20척)   평균  519.0   최악  586.7
sample_rho75_close24_s2  (25척)   평균  810.6   최악  903.4
sample_rho90_close48_s3  (29척)   평균 1457.6   최악 1648.8
```

---

## MILP 세 개는 사실 하나다

nominal · SAA · 로버스트는 **제약이 전부 같다.** 다른 건 목적함수뿐이다.

```
nominal   시나리오 1개(명목)      목적 = 그 시나리오의 비용
SAA       시나리오 K개            목적 = 평균
로버스트   불확실성 집합의 꼭짓점    목적 = 최악
```

그래서 제약은 `core/milp.py` **한 곳**에만 쓴다. 팀원 A가 만든다.

```python
# core/milp.py — A가 작성
def build(inst, scenarios, aggregate):
    """scenarios: 실현값 리스트.  aggregate: "nominal" | "mean" | "max"""
    ...
    return model, vars
```

C·D는 이걸 호출만 한다.

```python
# planners/nominal.py — C
return solve(build(inst, [nominal_scenario(inst)], "nominal"))

# planners/saa.py — D
return solve(build(inst, sample(inst, cfg["scenario"]["n_scenario_saa"]), "mean"))
```

**MILP를 처음부터 짜는 사람은 A 한 명이다.** C·D는 시나리오를 만들어 넘기는 일을 한다.
제약이 한 곳에 있으니 "누가 어떤 제약을 빠뜨렸나"를 따질 일도 없어진다.

---

## 도착 과정 — 실측을 어떻게 꽂나

이게 이 연구의 차별점이다. 기존 robust BAP는 변동폭을 임의로 잡지만, 여기선 관측값으로 잡는다.
다만 **DiD 결과는 일별 집계 효과**이고 모형이 필요한 건 **선박별 도착 시각**이라 변환이 필요하다.

**1단계 — 강도 함수.** DiD 계수를 일별 도착 강도의 배수로 읽는다.

```
m(D−1)=0.37   m(D0)=0.16   m(D+1)=0.56   m(D+2)=1.08
m(D+3)=1.16   m(D+4)=1.14  m(D+5~)=1.00
                                (m = 1 + 효과%/100)
```

**2단계 — 수준.** 기저 도착률 λ₀는 ρ 격자가 정한다.
실측 일평균 33척은 **항만 전체**값이라 터미널 하나에는 그대로 쓰지 않는다.
대신 "총 선박 수 n = ρ × 용량 ÷ 척당 작업량"으로 역산하고, 그 n을 위 강도 비율로 배분한다.

> **형태는 데이터가, 수준은 격자가 정한다.** 이 분리가 중요하다.

**3단계 — 이연과 소멸.** 폐쇄 중 못 온 배가 전부 나중에 오는 게 아니다.
누적 분석에서 **반등이 손실의 약 20%만 회복**시켰다.

```
폐쇄 중 미도착분 D  →  φ·D 만 재개 후로 이연 (φ ≈ 0.2)
                       나머지는 타 항만으로 이탈하거나 소멸
```

φ는 민감도 대상이다. φ=1.0(전부 이연)로 두면 backlog를 과대평가하게 된다.

**4단계 — 불확실성.** 위 과정이 *명목* 시나리오다.
로버스트의 불확실성 집합은 여기서 각 선박 도착을 ±`arrival_jitter_h` 안에서 흔들되,
동시에 흔들리는 선박 수를 Γ개로 제한한다 (Bertsimas–Sim 예산).

---

## 내가 짤 함수

딱 이것 하나다. 파일 안의 주석에 규칙이 적혀 있다.

```python
def plan(inst: dict, cfg: dict) -> dict:
    return {
        "sequence": {"B1": ["V01", "V05"], "B2": ["V02"], ...},  # 선석별 접안 순서
        "cranes":   {"V01": 3, "V02": 2, ...},                   # 선박별 크레인 수
    }
```

모양이 틀리면 `run_all`이 `validate_stage1`에서 바로 잡아낸다.
전부 배정됐는지, 선박이 선석에 들어가는지, 크레인 수가 범위 안인지 확인한다.

### 인스턴스에 뭐가 들어있나

```python
inst["berths"]    # [{"id":"B1","length_m":400,"q_max":4}, ...]
inst["cranes"]    # {"total":12, "rate_tph":390.0}
inst["vessels"]   # [{"id":"V01","arrival_h":0.0,"loa_m":294,
                  #   "workload_t":10300.0,"q_min":1,"q_max":4}, ...]
inst["recovery"]  # {"t_reopen_h":24.0,"kappa":0.75,"kappa_recover_h":12.0}
```

처리시간은 `workload_t / (q * rate_tph * 효율)`로 나온다.
효율은 재개 직후 `kappa`에서 시작해 `kappa_recover_h`에 걸쳐 1.0으로 회복한다.

### MILP 쓰는 사람 (B·C)용 PuLP 뼈대

```python
import pulp

m = pulp.LpProblem("nominal", pulp.LpMinimize)
x = pulp.LpVariable.dicts("x", (V, B), cat="Binary")      # 선박 i를 선석 b에
S = pulp.LpVariable.dicts("S", V, lowBound=0)             # 시작 시각
m += pulp.lpSum(S[i] - a[i] for i in V)                   # 총 대기 최소화
for i in V:
    m += pulp.lpSum(x[i][b] for b in B) == 1              # 한 선석에만
m.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=cfg["run"]["time_limit_s"]))

# ★ 중요: S는 모형 안에서만 쓰고, 반환할 땐 순서로 바꿔서 낸다
order = {b: sorted([i for i in V if x[i][b].value() > 0.5],
                   key=lambda i: S[i].value()) for b in B}
return {"sequence": order, "cranes": q}
```

MILP 안에서 시작 시각을 써도 되지만, **반환은 순서와 크레인 수뿐**이다.
실제 시각은 `recourse()`가 다시 계산한다. 그래야 모든 방법이 같은 잣대로 평가된다.

---

## 자가 점검

`run_all.py`가 끝나면 이 순서를 자동으로 확인한다.

```
완전정보 ≤ SAA ≤ nominal      (평균 기준)
```

**이건 정리다. 깨지면 코드 버그다.** 실행할 때마다 확인하고 넘어간다.

단 **완전정보를 "절대 하한"이라고 쓰면 안 된다.** 2단계가 고정 규칙이므로,
여기서 말하는 완전정보는 *"실현값을 다 알고 1단계를 최적으로 골랐을 때, 그 규칙 하의 최선"* 이다.
규칙 자체가 최적이 아니므로 진짜 최적해는 이보다 낮을 수 있다.
순서 점검은 세 방법이 같은 규칙을 쓰므로 그대로 유효하다.
`로버스트 vs SAA`는 순서가 없다 — 최악 기준이면 로버스트가, 평균 기준이면 SAA가 이긴다.
그 거래(price of robustness)를 보고하는 게 이 연구의 논점이다.

---

## 실험 설계

**격자 (주 결과)** — 혼잡도 × 폐쇄시간

```
ρ          0.60 / 0.75 / 0.90      가동률 = 해야 할 크레인·시간 / 쓸 수 있는 크레인·시간
t_close    12h / 24h / 48h         용량-반응 3등급 (실측)
```

9칸 × 실현 20개 × 방법 5개 = 900회. 1회 60초면 15시간.

**에피소드 (사례 연구)** — 실제 태풍 5개 조건을 재현

```
2019 타파 / 2020 마이삭+하이선 / 2021 오마이스+찬투 / 2022 힌남노 / 2023 카눈
```

재현한 인스턴스이지 실제 운영 기록이 아니다.
"실제보다 나았다"가 아니라 **"같은 조건에서 FCFS보다 나았다"** 까지만 주장한다.
