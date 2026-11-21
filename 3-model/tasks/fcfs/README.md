# FCFS — 선착순 배정

> 공통 안내를 먼저 읽으세요 → [`../_COMMON.md`](../_COMMON.md)

## 내가 할 일

**먼저 온 배부터, 빈 선석에 차례로 넣는다.** 그게 전부입니다.
솔버도 최적화도 필요 없습니다. 순수 파이썬 30줄이면 끝납니다.

## 이게 왜 필요한가

실제 항만이 대체로 이렇게 운영합니다. 그래서 **현장 방식 기준선**입니다.
나중에 "로버스트가 현장 방식보다 얼마나 나은가"를 말할 때 이게 분모가 됩니다.

네 방법 중 **제일 나쁘게 나오는 게 정상**입니다. 그래야 다른 방법들이 의미가 생깁니다.

## 규칙

```
1. 배를 명목 도착시각(arrival_h) 순으로 줄 세운다
2. 앞에서부터 하나씩:
   - 그 배가 들어갈 수 있는 선석을 고른다  (loa_m <= length_m)
   - 그중 "가장 빨리 빌 것 같은" 곳에 붙인다
     = 지금까지 그 선석에 붙인 배들의 workload_t 합이 가장 작은 곳
   - 크레인은 받을 수 있는 최대로 준다
     q = min(배의 q_max, 선석의 q_max)
```

## 뼈대

```python
def plan(inst, cfg):
    berths = {b["id"]: b for b in inst["berths"]}
    seq    = {b: [] for b in berths}      # 선석별 순서
    load   = {b: 0.0 for b in berths}     # 선석별 누적 작업량
    cranes = {}

    for v in sorted(inst["vessels"], key=lambda x: x["arrival_h"]):
        fits = [b for b in berths.values() if v["loa_m"] <= b["length_m"]]
        best = min(fits, key=lambda b: load[b["id"]])
        seq[best["id"]].append(v["id"])
        load[best["id"]] += v["workload_t"]
        cranes[v["id"]] = min(v["q_max"], best["q_max"])

    return {"sequence": seq, "cranes": cranes}
```

거의 답이지만 그대로 돌아가는지는 직접 확인하세요.
`fits`가 빈 리스트가 되는 경우(어느 선석에도 안 들어가는 배)를 어떻게 할지도 정해야 합니다.

## 확인

```bash
python 3-model/run_all.py --only fcfs
```

인스턴스 3개에서 숫자가 나오면 끝입니다.

## 더 해볼 것 (여유 있으면)

같은 구조로 **두 가지만 더** 만들면 비교표가 풍성해집니다.

- 작업량이 **작은 배부터** (`workload_t` 오름차순)
- 작업량이 **큰 배부터** (내림차순)

도착순보다 나을 수도 있습니다. 그 자체가 결과입니다.

## 참고

→ [Berth-Scheduler (GitHub)](https://github.com/Lixiang878/Berth-Scheduler)

`FCFS | first-come-first-served greedy | baseline`로 구현돼 있습니다.
논문은 안 읽어도 됩니다. 개념이 위에 적은 게 전부입니다.
