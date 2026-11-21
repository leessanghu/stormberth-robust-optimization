# 모든 담당자 공통 — 먼저 읽으세요

## 준비 (한 번만)

```bash
git clone https://github.com/leessanghu/stormberth-robust-optimization.git
cd stormberth-robust-optimization
git checkout -b 내이름                      # 각자 브랜치
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python 3-model/tests/golden.py              # OK 3개 나오면 준비 끝
```

## 내가 채울 것은 함수 하나입니다

내 폴더의 `plan.py` 안에 있습니다.

```python
def plan(inst, cfg):
    return {"sequence": {...}, "cranes": {...}}
```

**이것 말고는 아무것도 건드리지 않습니다.** 특히 `3-model/core/`는 절대 수정 금지입니다.

## 입력 — `inst`에 뭐가 들어있나

```python
inst["berths"]    # [{"id":"B1", "length_m":400, "q_max":4}, ...]        선석 4개
inst["cranes"]    # {"total":12, "rate_tph":390.0}                       크레인 12기
inst["vessels"]   # [{"id":"V01", "arrival_h":0.0, "loa_m":294,
                  #   "workload_t":10300.0, "q_min":1, "q_max":4}, ...]
inst["recovery"]  # {"t_reopen_h":24.0, "kappa":0.75, "kappa_recover_h":12.0}
inst["horizon_h"] # 72
```

- `arrival_h` : 배가 오는 시각 (시간 단위, 0 = 기준시점)
- `workload_t`: 그 배의 작업량 (톤). 크레인 1기가 시간당 `rate_tph`톤 처리
- `loa_m`     : 배 길이. 선석 `length_m`보다 길면 못 들어감
- `t_reopen_h`: 항만이 다시 열리는 시각. 이 전에는 아무도 시작 못 함
- `kappa`     : 재개 직후 크레인 효율 (0.75 = 평소의 75%)

## 출력 — 정확히 이 모양

```python
{
  "sequence": {"B1": ["V01", "V05"], "B2": ["V02"], "B3": [], "B4": ["V03","V04"]},
  "cranes":   {"V01": 3, "V02": 2, "V03": 4, "V04": 1, "V05": 2}
}
```

- `sequence` : 선석마다 **붙일 순서대로** 배 id를 나열. 모든 배가 정확히 한 번씩 들어가야 함
- `cranes`   : 배마다 크레인 몇 대. `q_min ≤ 값 ≤ min(q_max, 선석 q_max)`

**시작 시각은 반환하지 않습니다.** 그건 `core/recourse.py`가 계산합니다.
각자 계산하면 "배정이 좋아서 이긴 건지 계산 방식이 달라서 이긴 건지" 구분이 안 됩니다.

## 확인

```bash
python 3-model/run_all.py --only 내방법
```

숫자가 나오면 성공입니다. 형식이 틀리면 `validate_stage1`이 뭐가 틀렸는지 알려줍니다.

## 하지 말 것

| 금지 | 이유 |
|---|---|
| `core/` 수정 | 모든 방법이 공유. 여기 바뀌면 전체 결과가 바뀜 |
| 시작 시각 반환 | 2단계는 공용 코드 몫 |
| `time_limit`·시드를 코드에 박기 | `cfg`에서 읽어 쓸 것. 안 그러면 비교 불공정 |
| 자기 스크립트로 숫자 뽑아 보고 | `run_all.py` 출력만 보고서에 씀 |

막히면 혼자 2시간 넘기지 말고 공유하세요.
