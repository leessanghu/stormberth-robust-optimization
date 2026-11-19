"""부산 태풍 에피소드별 병목 파생지표 요약."""
import warnings; warnings.filterwarnings("ignore")
import pandas as pd, numpy as np

d=pd.read_csv("2-port/data/portwatch/daily_ports.csv")
d.columns=[c.strip().lstrip("﻿") for c in d.columns]
d["date"]=pd.to_datetime(d["date"],utc=True,errors="coerce").dt.tz_localize(None)
b=d[d.portid=="port1065"].sort_values("date").set_index("date")
s=b.portcalls_container.astype(float)

EV={ "2019 타파":        ("2019-09-22",1,24),
     "2020 마이삭+하이선":("2020-09-02",2,12),
     "2021 오마이스+찬투":("2021-08-23",2,None),
     "2022 힌남노+난마돌":("2022-09-05",2,18),
     "2023 카눈":        ("2023-08-10",1,12) }

f = s.groupby(s.index.day_of_week).median()/s.median()
adj = s/ s.index.day_of_week.map(f)

def base_series(t0):
    lo=pd.Timestamp(t0)
    donut=adj[((adj.index>=lo-pd.Timedelta(days=45))&(adj.index<=lo-pd.Timedelta(days=15)))|
              ((adj.index>=lo+pd.Timedelta(days=30))&(adj.index<=lo+pd.Timedelta(days=60)))]
    return donut.median()

rows=[]
for lab,(t0,ntyph,h34) in EV.items():
    t0=pd.Timestamp(t0); lvl=base_series(t0)
    idx=pd.date_range(t0-pd.Timedelta(days=5), t0+pd.Timedelta(days=28))
    act=s.reindex(idx); bas=lvl*pd.Series(idx.day_of_week,index=idx).map(f)
    ratio=act/bas; defi=bas-act
    cd=defi.cumsum()
    clear=[i for i,(dt,v) in enumerate(cd.items()) if v<=0 and dt>t0]
    days_clear = (cd.index[clear[0]]-t0).days if clear else None
    rows.append(dict(에피소드=lab, 태풍수=ntyph, h34=h34,
        정지일수=int((act<=5).sum()), 최저비율=round(ratio.min(),2),
        최대회복=round(ratio[ratio.index>t0].max(),2),
        최대적체=round(cd.max(),0), 해소일수=days_clear,
        D21잔량=round(cd.get(t0+pd.Timedelta(days=21),np.nan),0),
        기준일평균=round(bas.mean(),1)))
r=pd.DataFrame(rows)
pd.set_option("display.width",220); pd.set_option("display.unicode.east_asian_width",True)
print("="*96); print("부산항 태풍 에피소드별 병목 지표  (PortWatch 일별 컨테이너선 기항)"); print("="*96)
print(r.to_string(index=False))
r.to_csv("2-port/output/busan_episode_summary.csv",index=False)
print("""
정지일수  = 기항 5척 이하인 날 수 (평년 33척)
최저비율  = 베이스라인 대비 최저 활동량
최대회복  = 태풍 이후 최대 활동량 배수 (Vessel Bunching 강도)
최대적체  = 누적 미처리 선박 수 최댓값 (척) = Backlog 규모
해소일수  = 누적 적체가 0으로 복귀한 날 (None = 28일 내 미해소)
D21잔량   = 태풍 21일 후에도 남은 적체 (척)""")
