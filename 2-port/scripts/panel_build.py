"""항만 × 날짜 패널을 만든다 (PortWatch 기항 + 태풍 노출).

출력 단위: (portid, date) 1행.
  y        : portcalls_container  일별 컨테이너선 기항수
  exposed  : 그날 34kt 반경 안이었나 (0/1)
  ev_time  : 노출 에피소드 시작일 기준 상대일 (-7 ~ +21), 비노출이면 결측
사용:  python 2-port/scripts/panel_build.py
"""
import pathlib, pandas as pd, numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
PW   = ROOT / "2-port" / "data" / "portwatch" / "daily_ports.csv"
EXP  = ROOT / "1-typhoon" / "output" / "exposure_daily.csv"
OUT  = ROOT / "2-port" / "output" / "panel.parquet"

# 한글 항만명 -> PortWatch portid. 시미즈는 PortWatch 미수집, 양산은 상하이와 동일 해역.
PORTID = {
    "부산":["port1065"], "울산":["port1338"], "광양":["port432"], "인천":["port494"],
    "가오슝":["port541"], "지룽":["port238"], "타이중":["port1252"],
    "나하":["port2040"], "가고시마":["port528"], "하카타":["port439"],
    "기타큐슈":["port1378"], "오사카":["port862"], "고베":["port581"],
    "도쿄":["port1305"], "요코하마":["port1417"], "나고야":["port786"],
    "상하이":["port1188","port2027"], "닝보":["port824"], "칭다오":["port1069"],
    "샤먼":["port1404"], "선전":["port1189"], "홍콩":["port474"],
}
GAP = 3      # 노출일 간격이 이 이하면 같은 에피소드
PRE, POST = 7, 21

def main():
    d = pd.read_csv(PW)
    dk = d.columns[0]
    d["date"] = pd.to_datetime(d[dk].str.split().str[0], format="%Y/%m/%d")
    d = d[["date","portid","portname","country","portcalls_container",
           "portcalls","portcalls_tanker","import_container","export_container"]]

    e = pd.read_csv(EXP, parse_dates=["date"])
    e["portid"] = e.port.map(PORTID)
    miss = e[e.portid.isna()].port.unique()
    e = e.explode("portid").dropna(subset=["portid"])

    p = d.merge(e.drop(columns=["port"]), on=["portid","date"], how="left")
    p["exposed"] = p.h34.notna().astype(int)
    p[["h34","h50","h64"]] = p[["h34","h50","h64"]].fillna(0.0)

    # 에피소드 식별 + 상대일
    p = p.sort_values(["portid","date"]).reset_index(drop=True)
    p["ev_time"] = np.nan; p["ep_id"] = pd.NA
    for pid, g in p.groupby("portid", sort=False):
        ex = g.loc[g.exposed == 1, "date"]
        if ex.empty: continue
        starts = [ex.iloc[0]]
        for a, b in zip(ex[:-1], ex[1:]):
            if (b - a).days > GAP: starts.append(b)
        for k, s in enumerate(starts):
            w = g[(g.date >= s - pd.Timedelta(days=PRE)) &
                  (g.date <= s + pd.Timedelta(days=POST))]
            p.loc[w.index, "ev_time"] = (w.date - s).dt.days.to_numpy()
            p.loc[w.index, "ep_id"] = f"{pid}_{k}"

    p["doy"] = p.date.dt.day_of_year
    p["dow"] = p.date.dt.day_of_week
    p["ym"]  = p.date.dt.to_period("M").astype(str)
    p["ly"]  = np.log1p(p.portcalls_container)
    med = p.groupby("portid").portcalls_container.transform("median")
    p["ratio"] = p.portcalls_container / med
    p["tanker_share"] = p.portcalls_tanker / p.portcalls.replace(0, np.nan)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    p.to_parquet(OUT, index=False)
    print(f"패널 {len(p):,}행 = 항만 {p.portid.nunique()}개 × 날짜 {p.date.nunique():,}일")
    print(f"노출일 {int(p.exposed.sum())}건, 에피소드 {p.ep_id.nunique()}개")
    if len(miss): print(f"매핑 없어 제외: {list(miss)}")
    print(f"\n항만별 노출일수 (상위/하위)")
    s = p.groupby("portname").exposed.sum().sort_values(ascending=False)
    print(pd.concat([s.head(6), s.tail(6)]).to_string())
    print(f"\n저장: {OUT}")

if __name__ == "__main__":
    main()
