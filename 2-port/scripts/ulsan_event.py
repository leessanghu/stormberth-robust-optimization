"""울산 선석배정 일별 건수로 태풍 전후 dip-and-spike 경향 확인.

정제 규칙:
  - 완전중복 제거
  - 사후입력 레코드 제거: 선석배정일자가 접안예정일자보다 한참 뒤인 행은
    접안예정일자가 기본값으로 찍힌 오염 데이터로 간주 (lead < -7)
  - 2020년은 시스템 가동 초기로 9월 중순 이전 자료가 없어 분석에서 제외
"""
import pandas as pd, numpy as np

df = pd.read_csv("2-port/data/ulsan/ulsan_berth_allocation_20260527.csv", encoding="euc-kr")
for c in ["접안예정일자","선석배정일자","등록일자","수정일자"]:
    df[c] = pd.to_datetime(df[c], errors="coerce")
df = df.drop_duplicates()
df["lead"] = (df.접안예정일자 - df.선석배정일자).dt.days

n0 = len(df)
df = df[df.lead.between(-7, 30)]
print(f"정제: {n0:,} -> {len(df):,}행 (사후입력 {n0-len(df):,}행 제거)")

v = df[(df.접안예정일자>="2020-10-01") & (df.접안예정일자<="2026-05-27")]
daily = v.groupby(v.접안예정일자).size()
idx = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
daily = daily.reindex(idx, fill_value=0)
print(f"분석구간 {daily.index.min().date()} ~ {daily.index.max().date()}, 일평균 {daily.mean():.1f}건")

EVENTS = {"2022-09 힌남노":"2022-09-06", "2022-09 난마돌":"2022-09-19", "2023-08 카눈":"2023-08-10"}
CTRL = [2021, 2024, 2025]

def baseline(date, half=3):
    vs = []
    for y in CTRL:
        try: a = date.replace(year=y)
        except ValueError: continue
        w = daily.loc[a-pd.Timedelta(days=half): a+pd.Timedelta(days=half)]
        if len(w): vs.append(w.mean())
    return np.mean(vs) if vs else np.nan

rows = []
for label, d0 in EVENTS.items():
    d0 = pd.Timestamp(d0)
    print(f"\n{'='*66}\n{label}  (기준일 {d0.date()})\n{'='*66}")
    print(f"{'off':>5} {'날짜':>12} {'건수':>5} {'기준':>6} {'비율':>6}")
    for k in range(-10, 15):
        d = d0 + pd.Timedelta(days=k)
        if d not in daily.index: continue
        a = daily.loc[d]; b = baseline(d); r = a/b if b and b>0 else np.nan
        print(f"{k:>+5} {d.date()!s:>12} {a:>5} {b:>6.1f} {r:>6.2f}  "
              f"{'#'*int(round(r*10)) if np.isfinite(r) else ''}{' <<<' if k==0 else ''}")
        rows.append(dict(event=label, offset=k, date=d.date(), actual=a, baseline=b, ratio=r))

out = pd.DataFrame(rows); out.to_csv("2-port/output/event_trend_ulsan.csv", index=False)
PHASES = {"사전(-10~-4)":(-10,-4), "직전(-3~-1)":(-3,-1), "충격(0~+1)":(0,1),
          "회복초(+2~+4)":(2,4), "회복중(+5~+9)":(5,9), "정상화(+10~+14)":(10,14)}
summ = []
for label in EVENTS:
    g = out[out.event==label]; r = {"event":label}
    for p,(a,b) in PHASES.items():
        s = g[(g.offset>=a)&(g.offset<=b)]
        r[p] = s.actual.sum()/s.baseline.sum() if s.baseline.sum()>0 else np.nan
    summ.append(r)
s = pd.DataFrame(summ).set_index("event")
pd.set_option("display.width",200); pd.set_option("display.unicode.east_asian_width",True)
print(f"\n{'='*66}\n구간 요약 (1.00 = 평년 수준)\n{'='*66}")
print(s.round(2).to_string())
s.to_csv("2-port/output/event_phase_summary.csv")
