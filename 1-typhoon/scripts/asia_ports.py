"""아시아 주요 컨테이너 항만의 최근 태풍 노출 계산."""
import sys, pandas as pd, numpy as np
sys.path.insert(0, "1-typhoon/scripts")
import ike_exposure as ie

ie.PORTS = {
    # 한국
    "부산":(35.10,129.04), "울산":(35.50,129.38), "광양":(34.90,127.70), "인천":(37.45,126.60),
    # 일본
    "도쿄":(35.62,139.78), "요코하마":(35.45,139.65), "나고야":(35.05,136.87),
    "오사카":(34.65,135.43), "고베":(34.68,135.21), "하카타":(33.60,130.40),
    "기타큐슈":(33.90,130.88), "시미즈":(35.02,138.52), "가고시마":(31.58,130.56),
    "나하":(26.21,127.67),
    # 대만
    "가오슝":(22.61,120.28), "지룽":(25.13,121.74), "타이중":(24.29,120.52),
    # 중국·홍콩
    "상하이":(30.63,122.07), "닝보":(29.87,121.95), "칭다오":(36.07,120.32),
    "샤먼":(24.48,118.07), "선전":(22.58,114.27), "홍콩":(22.30,114.12),
}

df = ie.load("1-typhoon/data/ibtracs.WP.list.v04r01.csv", season_min=2019)
df["IKE_TJ"] = df.apply(ie.ike_row, axis=1)

rows=[]
for sid, g in df.groupby("SID", sort=False):
    g=g.reset_index(drop=True)
    dt=g["ISO_TIME"].diff().dt.total_seconds().div(3600).bfill().fillna(6.0).to_numpy()
    name=str(g["NAME"].dropna().iloc[0]) if g["NAME"].notna().any() else "UNNAMED"
    for pname,(plat,plon) in ie.PORTS.items():
        res=[ie.wind_at_port(g.loc[i],plat,plon) for i in range(len(g))]
        u=np.array([r[0] for r in res]); d=np.array([r[1] for r in res])
        ring=np.array([r[2] for r in res])
        if ring.max()==0: continue
        rows.append(dict(SID=sid,season=int(g.SEASON.iloc[0]),name=name,port=pname,
            t0=g.loc[int(d.argmin()),"ISO_TIME"], dist=float(d.min()),
            h34=float(dt[ring>=34].sum()), h50=float(dt[ring>=50].sum()),
            h64=float(dt[ring>=64].sum()),
            IKE=float(g.IKE_TJ.max()), vmax=float(g.USA_WIND.max())))
out=pd.DataFrame(rows)
out.to_csv("1-typhoon/output/asia_port_exposure.csv",index=False)
pd.set_option("display.width",220); pd.set_option("display.unicode.east_asian_width",True)
print(f"2019년 이후 항만-태풍 노출 조합: {len(out)}건\n")
print("=== 노출시간(34kt) 상위 25 ===")
t=out.sort_values(["h34","h50"],ascending=False).head(25)
print(t[["season","name","port","t0","dist","h34","h50","h64","vmax","IKE"]].round(0).to_string(index=False))
