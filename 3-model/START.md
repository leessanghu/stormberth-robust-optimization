# 시작하기

데이터셋과 제약은 레포에 있습니다. 각자 담당 파일은 아래와 같습니다.

| 역할 | 채울 파일 |
|---|---|
| FCFS | `3-model/tasks/fcfs/plan.py` |
| nominal | `3-model/tasks/nominal/plan.py` |
| 완전정보 | `3-model/tasks/perfect/plan.py` |

---

## 1. 받기

**Colab**

```python
!git clone https://github.com/leessanghu/stormberth-robust-optimization.git
%cd stormberth-robust-optimization
!pip install -q pyyaml
!python 3-model/tests/golden.py        # OK 3개 나오면 정상
```

**로컬**

```bash
git clone https://github.com/leessanghu/stormberth-robust-optimization.git
cd stormberth-robust-optimization
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python 3-model/tests/golden.py
```

각자 브랜치에서 작업합니다. `git checkout -b 내이름`

---

## 2. 데이터

`3-model/instances/` 에 **태풍 에피소드 38개**가 들어 있습니다. 받으면 바로 있습니다.

```
ep_Busan2019Tapah_s1.json        인스턴스 (선박·선석·크레인)
ep_Busan2019Tapah_s1.real.json   평가용 실현 60개
```

아시아 12개 항만 × 2019~2026 태풍 중 **실제로 기항이 끊긴 사건**만 골랐습니다.
도착 수와 폐쇄 시점은 PortWatch 실측입니다.

---

## 3. 반환 형식

```python
def plan(inst, cfg, real=None):
    return {
        "sequence": {"B1": ["V01", "V05"], "B2": ["V02"], "B3": [], "B4": ["V03", "V04"]},
        "cranes":   {"V01": 3, "V02": 2, "V03": 4, "V04": 1, "V05": 2},
    }
```

- `sequence` : 선석마다 **붙일 순서대로** 선박 id
- `cranes` : 선박마다 크레인 몇 대
- **시작 시각은 반환하지 않습니다.** `core/recourse.py` 가 계산합니다

### 입력 `inst`

```python
inst["berths"]    # [{"id":"B1", "length_m":400, "q_max":4}, ...]
inst["cranes"]    # {"total":12, "rate_tph":390.0}
inst["vessels"]   # [{"id":"V01", "arrival_h":0.0, "loa_m":294,
                  #   "workload_t":10300.0, "q_min":1, "q_max":4}, ...]
inst["recovery"]  # {"t_reopen_h":24.0, "kappa":0.75, "kappa_recover_h":12.0}
inst["horizon_h"] # 72
```

`t_reopen_h` 전에는 아무도 시작 못 합니다. `kappa` 는 재개 직후 크레인 효율입니다.

`real` 은 완전정보만 씁니다. 나머지 둘은 무시하세요.

---

## 4. 제약

```
C1   모든 선박이 정확히 한 번씩 배정된다
C2   선박 loa_m  <=  그 선석의 length_m
C3   q_min  <=  크레인 수  <=  min(선박 q_max, 선석 q_max)
```

`run_all.py` 가 `validate_stage1` 로 검사하고, 어긋나면 어디가 어긋났는지 출력합니다.

시작 시각·크레인 총량·선석 비중첩은 `core/recourse.py` 에서 처리합니다.

---

## 5. 돌리기

```bash
python 3-model/tests/selfcheck.py 내역할   # 혼자 점검
python 3-model/run_all.py --only 내역할    # 내 것만
python 3-model/run_all.py                 # 전부 (다 들어온 뒤)
```

---

## 6. 규칙 넷

**① `core/` · `config.yaml` · `instances/` 는 건드리지 않습니다.**
다섯 방법이 공유합니다. 여기가 바뀌면 전체 결과가 바뀌어서 비교가 무의미해집니다.

**② 시드·반복수를 코드에 박지 않습니다.** `cfg` 에서 읽으세요.

```python
run   = (cfg or {}).get("run", {})
seed  = int(run.get("seed", 20261119)) % 100000
iters = int(run.get("search_iters", 1000))
```

박아두면 방법마다 탐색 예산이 달라져 비교가 불공정해집니다.

**③ 보고서 숫자는 `run_all.py` 출력만 씁니다.** 각자 스크립트로 뽑은 건 안 씁니다.

**④ 무엇으로 어떻게 풀었는지 커밋 메시지에 한 줄 남깁니다.**
MILP 인지 국소탐색인지 그리디인지에 따라 해의 품질이 달라지는데, 기록이 없으면
나중에 "방법 차이"와 "푸는 방식 차이"를 구분할 수 없습니다.
