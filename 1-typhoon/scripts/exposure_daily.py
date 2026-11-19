"""항만 × 날짜 단위 태풍 노출 패널을 만든다.

asia_port_exposure.csv는 '태풍 1개 × 항만 1개 = 1행'이라 회귀에 바로 못 쓴다.
여기서는 6시간 간격 베스트트랙을 날짜로 접어서
  (항만, 날짜) -> 그날 34/50/64kt 반경 안에 있던 시간, 최대풍속, 태풍 IKE
를 만든다. 이게 PortWatch 일별 기항수와 결합되는 단위다.

사용:  python 1-typhoon/scripts/exposure_daily.py
출력:  1-typhoon/output/exposure_daily.csv
"""
import sys, pathlib, pandas as pd, numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "1-typhoon" / "scripts"))
import ike_exposure as ie
from asia_ports_def import PORTS          # 항만 좌표 단일 출처

SEASON_MIN = 2018                          # PortWatch(2019-)보다 1년 앞까지
SRC = ROOT / "1-typhoon" / "data" / "ibtracs.WP.list.v04r01.csv"
OUT = ROOT / "1-typhoon" / "output" / "exposure_daily.csv"

def main():
    ie.PORTS = PORTS
    df = ie.load(str(SRC), season_min=SEASON_MIN)
    df["IKE_TJ"] = df.apply(ie.ike_row, axis=1)

    rows = []
    for sid, g in df.groupby("SID", sort=False):
        g = g.reset_index(drop=True)
        # 각 관측이 대표하는 시간(h): 앞뒤 간격의 절반씩
        t = g["ISO_TIME"]
        dt = t.diff().dt.total_seconds().div(3600)
        dur = (dt.shift(-1).fillna(6.0) + dt.fillna(6.0)) / 2.0
        name = str(g["NAME"].dropna().iloc[0]) if g["NAME"].notna().any() else "UNNAMED"
        ike_max = float(g.IKE_TJ.max())
        vmax = float(g.USA_WIND.max()) if g.USA_WIND.notna().any() else np.nan

        for pname, (plat, plon) in PORTS.items():
            res = [ie.wind_at_port(g.loc[i], plat, plon) for i in range(len(g))]
            ring = np.array([r[2] for r in res], dtype=float)
            if ring.max() == 0:
                continue
            u = np.array([r[0] for r in res]); d = np.array([r[1] for r in res])
            sub = pd.DataFrame({"date": t.dt.date, "dur": dur.to_numpy(),
                                "ring": ring, "u": u, "d": d})
            sub = sub[sub.ring >= 34]
            for day, gg in sub.groupby("date"):
                rows.append(dict(
                    port=pname, date=day, SID=sid, storm=name,
                    h34=float(gg.dur[gg.ring >= 34].sum()),
                    h50=float(gg.dur[gg.ring >= 50].sum()),
                    h64=float(gg.dur[gg.ring >= 64].sum()),
                    u_max=float(gg.u.max()), dist_min=float(gg.d.min()),
                    IKE=ike_max, vmax=vmax))

    out = pd.DataFrame(rows)
    # 같은 날 두 태풍이 겹치면 합산(시간)·최대(강도)
    out = (out.groupby(["port", "date"], as_index=False)
              .agg(h34=("h34", "sum"), h50=("h50", "sum"), h64=("h64", "sum"),
                   u_max=("u_max", "max"), dist_min=("dist_min", "min"),
                   IKE=("IKE", "max"), vmax=("vmax", "max"),
                   storm=("storm", lambda s: "+".join(sorted(set(s)))),
                   n_storm=("SID", "nunique")))
    out.to_csv(OUT, index=False)
    print(f"노출일 {len(out)}건 / 항만 {out.port.nunique()}개 / "
          f"{out.date.min()} ~ {out.date.max()}")
    print(f"저장: {OUT}\n")
    print("항만별 34kt 노출일수")
    print(out.groupby("port").size().sort_values(ascending=False).to_string())

if __name__ == "__main__":
    main()
