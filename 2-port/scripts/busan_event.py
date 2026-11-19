"""부산항 태풍 전후 병목 분석 (PortWatch 일별 기항).

파생변수
  ratio(t)    = 실제 / 베이스라인           — 상대 활동량
  deficit(t)  = 베이스라인 - 실제           — 당일 미처리분
  CD(t)       = Σ deficit                   — 누적 적체 (제안서의 backlog)
  해소일수     = CD가 0 이하로 복귀한 첫 t   — Backlog Clearance Time
  peak CD      = 최대 누적 적체              — 적체 규모

베이스라인: 요일효과를 제거한 뒤, 이벤트 창을 뺀 전후 도넛 구간
            [t-45,t-15] ∪ [t+15,t+45]의 중앙값. 추세·계절을 국소적으로 흡수하고
            이벤트 자체는 포함하지 않는다.
"""
import pandas as pd, numpy as np

METRIC = "portcalls_container"

d = pd.read_csv("2-port/data/portwatch/daily_ports.csv")
d.columns = [c.strip().lstrip("﻿") for c in d.columns]
d["date"] = pd.to_datetime(d["date"], errors="coerce", utc=True).dt.tz_localize(None)
b = d[d.portid == "port1065"].sort_values("date").set_index("date")
s = b[METRIC].astype(float)
imp = b["import"].astype(float)

EVENTS = {   # 중첩 이벤트는 첫 태풍을 t=0으로 두고 둘째를 표시
    "2019 타파":        ("2019-09-22", ["2019-09-22"]),
    "2020 마이삭+하이선": ("2020-09-02", ["2020-09-02","2020-09-07"]),
    "2022 힌남노+난마돌": ("2022-09-05", ["2022-09-05","2022-09-19"]),
    "2023 카눈":        ("2023-08-10", ["2023-08-10"]),
}

def dow_factor(x):
    """요일 효과: 전체 기간 기준 요일별 중앙값 / 전체 중앙값."""
    f = x.groupby(x.index.dayofweek).median() / x.median()
    return f

def baseline(x, t0, half_in=15, half_out=45):
    """이벤트 창을 제외한 도넛 구간에서 요일보정 수준을 추정."""
    f = dow_factor(x)
    adj = x / x.index.dayofweek.map(f)          # 요일 제거
    lo = pd.Timestamp(t0)
    donut = adj[((adj.index >= lo - pd.Timedelta(days=half_out)) & (adj.index <= lo - pd.Timedelta(days=half_in))) |
                ((adj.index >= lo + pd.Timedelta(days=half_in))  & (adj.index <= lo + pd.Timedelta(days=half_out)))]
    level = donut.median()
    return level, f

rows = []
for label, (t0, marks) in EVENTS.items():
    t0 = pd.Timestamp(t0)
    lvl, f = baseline(s, t0)
    lvl_i, f_i = baseline(imp, t0)
    for k in range(-14, 29):
        dt = t0 + pd.Timedelta(days=k)
        if dt not in s.index: continue
        base = lvl * f[dt.dayofweek]
        base_i = lvl_i * f_i[dt.dayofweek]
        rows.append(dict(event=label, offset=k, date=dt, dow=dt.dayofweek,
                         calls=s[dt], base=base, ratio=s[dt]/base,
                         deficit=base - s[dt],
                         imp=imp[dt], imp_base=base_i, imp_ratio=imp[dt]/base_i))
t = pd.DataFrame(rows)
# 누적 적체는 이벤트 3일 전부터 누적 시작
t["CD"] = t.groupby("event").apply(
    lambda g: g.assign(c=np.where(g.offset>=-3, g.deficit, 0.0))["c"].cumsum(), include_groups=False
).reset_index(level=0, drop=True)
t.to_csv("2-port/output/busan_event_trend.csv", index=False)

pd.set_option("display.width",200); pd.set_option("display.unicode.east_asian_width",True)
for label in EVENTS:
    g = t[t.event==label]
    print(f"\n{'='*76}\n{label}   (베이스라인 일평균 {g.base.mean():.1f}척)\n{'='*76}")
    print(f"{'off':>4} {'날짜':>11} {'기항':>5} {'기준':>6} {'비율':>6} {'누적적체':>8}")
    for _,r in g.iterrows():
        if not (-8 <= r.offset <= 21): continue
        bar = "#"*int(round(min(r.ratio,2.5)*10))
        mk = " <<<" if str(r.date.date()) in EVENTS[label][1] else ""
        print(f"{r.offset:>+4} {r.date.date()!s:>11} {r.calls:>5.0f} {r.base:>6.1f} {r.ratio:>6.2f} {r.CD:>8.1f}  {bar}{mk}")
