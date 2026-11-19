"""
IBTrACS -> 태풍별 IKE + 한국 주요 항만 exposure 계산.

IKE (Powell & Reinhold 2007):
    IKE = sum over wind-field volume of (1/2) * rho * U^2 * dV
    표층 1 m 두께를 가정하고, IBTrACS가 제공하는 4분면별 34/50/64 kt
    풍속반경이 만드는 동심 고리를 단위 적분영역으로 삼아 합으로 근사한다.

Exposure:
    각 트랙 시점에서 항만이 어느 풍속 고리 안에 있었는지 판정하고,
    그 지속시간을 누적한다. (hours_r34 / r50 / r64)
    추가로 항만 위치에서의 추정 풍속 제곱을 시간적분한 'IKE_port'를 둔다.
    이것이 "그 항만이 실제로 맞은 에너지"에 해당한다.
"""
import numpy as np
import pandas as pd

RHO = 1.15          # 공기 밀도 kg/m^3
DEPTH = 1.0         # 표층 두께 m
KT2MS = 0.514444
NM2M = 1852.0
R_EARTH = 6371.0    # km

# 분석 대상 항만. 인천/평택은 남해안 태풍에 대한 플라시보 대조군 역할.
PORTS = {
    "부산":   (35.10, 129.04),
    "부산신항": (35.08, 128.80),
    "울산":   (35.50, 129.38),
    "광양":   (34.90, 127.70),
    "목포":   (34.78, 126.38),
    "포항":   (36.05, 129.40),
    "평택당진": (36.97, 126.82),
    "인천":   (37.45, 126.60),
}

WIND_COLS = [f"USA_R{t}_{q}" for t in (34, 50, 64) for q in ("NE", "SE", "SW", "NW")]
USE_COLS = ["SID", "SEASON", "NAME", "ISO_TIME", "LAT", "LON", "USA_WIND"] + WIND_COLS


def load(path, season_min=2000):
    df = pd.read_csv(path, usecols=USE_COLS, skiprows=[1], low_memory=False)
    df = df[pd.to_numeric(df["SEASON"], errors="coerce") >= season_min]
    for c in ["LAT", "LON", "USA_WIND"] + WIND_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["ISO_TIME"] = pd.to_datetime(df["ISO_TIME"], errors="coerce")
    df = df.dropna(subset=["ISO_TIME", "LAT", "LON"])
    # IBTrACS는 3시간 보간행을 포함한다. USA 관측 synoptic 시각만 사용.
    df = df[df["ISO_TIME"].dt.hour.isin([0, 6, 12, 18])]
    return df.sort_values(["SID", "ISO_TIME"]).reset_index(drop=True)


def representative_wind(lo_kt, hi_kt):
    """고리 구간의 대표 풍속(m/s). 에너지 평균이므로 제곱평균을 쓴다."""
    return np.sqrt((lo_kt**2 + hi_kt**2) / 2.0) * KT2MS


def ike_row(row):
    """한 트랙 시점의 IKE (TJ). 4분면 x 3고리 합산."""
    vmax = row["USA_WIND"]
    total = 0.0
    for q in ("NE", "SE", "SW", "NW"):
        r34, r50, r64 = (row[f"USA_R{t}_{q}"] for t in (34, 50, 64))
        # 바깥 -> 안쪽 순서로 밴드를 구성 (단위: nm)
        bands = []
        if np.isfinite(r34) and r34 > 0:
            inner = r50 if (np.isfinite(r50) and r50 > 0) else 0.0
            bands.append((inner, r34, representative_wind(34, 50)))
        if np.isfinite(r50) and r50 > 0:
            inner = r64 if (np.isfinite(r64) and r64 > 0) else 0.0
            bands.append((inner, r50, representative_wind(50, 64)))
        if np.isfinite(r64) and r64 > 0:
            # 코어: 64 kt ~ Vmax
            hi = vmax if (np.isfinite(vmax) and vmax > 64) else 80.0
            bands.append((0.0, r64, representative_wind(64, hi)))
        for r_in, r_out, u in bands:
            if r_out <= r_in:
                continue
            area = (np.pi / 4.0) * ((r_out * NM2M) ** 2 - (r_in * NM2M) ** 2)
            total += 0.5 * RHO * u**2 * area * DEPTH
    return total / 1e12  # J -> TJ


def haversine_bearing(lat1, lon1, lat2, lon2):
    """태풍 중심(1) 기준 항만(2)까지 거리(km)와 방위각(deg)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(lon2 - lon1)
    dp = p2 - p1
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    dist = 2 * R_EARTH * np.arcsin(np.sqrt(a))
    y = np.sin(dl) * np.cos(p2)
    x = np.cos(p1) * np.sin(p2) - np.sin(p1) * np.cos(p2) * np.cos(dl)
    brg = (np.degrees(np.arctan2(y, x)) + 360) % 360
    return dist, brg


def quadrant(brg):
    if brg < 90:  return "NE"
    if brg < 180: return "SE"
    if brg < 270: return "SW"
    return "NW"


def wind_at_port(row, lat_p, lon_p):
    """항만 위치의 추정 풍속(m/s)과 중심거리(km).
    해당 4분면의 풍속반경과 비교해 어느 고리에 속하는지로 판정한다."""
    dist, brg = haversine_bearing(row["LAT"], row["LON"], lat_p, lon_p)
    q = quadrant(brg)
    d_nm = dist * 1000.0 / NM2M
    r34, r50, r64 = (row[f"USA_R{t}_{q}"] for t in (34, 50, 64))
    if np.isfinite(r64) and r64 > 0 and d_nm <= r64:
        return 64 * KT2MS, dist, 64
    if np.isfinite(r50) and r50 > 0 and d_nm <= r50:
        return 50 * KT2MS, dist, 50
    if np.isfinite(r34) and r34 > 0 and d_nm <= r34:
        return 34 * KT2MS, dist, 34
    return 0.0, dist, 0


def main(path, out_storms, out_ports, radius_km=500):
    df = load(path)
    df["IKE_TJ"] = df.apply(ike_row, axis=1)

    storm_rows, port_rows = [], []
    for sid, g in df.groupby("SID", sort=False):
        g = g.reset_index(drop=True)
        # 트랙 시점 간격(시간). 마지막 점은 직전 간격을 재사용.
        dt = g["ISO_TIME"].diff().dt.total_seconds().div(3600).bfill().fillna(6.0).to_numpy()

        # 항만별 최근접 거리 먼저 계산 -> 반경 안에 든 태풍만 남긴다
        per_port, min_dist_any = {}, np.inf
        for pname, (plat, plon) in PORTS.items():
            res = [wind_at_port(g.loc[i], plat, plon) for i in range(len(g))]
            u = np.array([r[0] for r in res])
            d = np.array([r[1] for r in res])
            ring = np.array([r[2] for r in res])
            min_dist_any = min(min_dist_any, d.min())
            per_port[pname] = dict(
                min_dist_km=float(d.min()),
                closest_time=g.loc[int(d.argmin()), "ISO_TIME"],
                hours_r34=float(dt[ring >= 34].sum()),
                hours_r50=float(dt[ring >= 50].sum()),
                hours_r64=float(dt[ring >= 64].sum()),
                # 항만이 받은 에너지 노출: (1/2) rho U^2 를 시간적분 (J/m^3 * h)
                exposure=float((0.5 * RHO * u**2 * dt).sum()),
            )
        if min_dist_any > radius_km:
            continue

        name = str(g["NAME"].dropna().iloc[0]) if g["NAME"].notna().any() else "UNNAMED"
        storm_rows.append(dict(
            SID=sid, season=int(g["SEASON"].iloc[0]), name=name,
            start=g["ISO_TIME"].min(), end=g["ISO_TIME"].max(),
            vmax_kt=float(g["USA_WIND"].max()),
            IKE_peak_TJ=float(g["IKE_TJ"].max()),
            IKE_mean_TJ=float(g["IKE_TJ"].mean()),
            min_dist_busan_km=per_port["부산"]["min_dist_km"],
        ))
        for pname, v in per_port.items():
            port_rows.append(dict(SID=sid, season=int(g["SEASON"].iloc[0]),
                                  name=name, port=pname, **v))

    storms = pd.DataFrame(storm_rows).sort_values("IKE_peak_TJ", ascending=False)
    ports = pd.DataFrame(port_rows)
    storms.to_csv(out_storms, index=False)
    ports.to_csv(out_ports, index=False)
    return storms, ports


if __name__ == "__main__":
    import sys
    s, p = main(sys.argv[1], sys.argv[2], sys.argv[3])
    print(f"반경 500km 내 통과 태풍: {len(s)}개 (2000년 이후)")
