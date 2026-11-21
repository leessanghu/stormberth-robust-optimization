"""태풍 직후 부산항에 배가 얼마나 몰렸나 — 에피소드별 표.

평년 수준은 요일효과를 제거한 뒤 상륙 45~15일 전 구간의 중앙값으로 잡는다.
사용:  python 2-port/scripts/busan_surge.py
출력:  2-port/output/busan_surge.csv
"""
import pathlib, pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
PANEL = ROOT / "2-port" / "output" / "panel.parquet"
OUT = ROOT / "2-port" / "output" / "busan_surge.csv"

EV = {"2019 타파": "2019-09-22", "2020 마이삭+하이선": "2020-09-02",
      "2021 오마이스+찬투": "2021-08-23", "2022 힌남노": "2022-09-05",
      "2023 카눈": "2023-08-10"}

def main():
    d = pd.read_parquet(PANEL)
    s = d[d.portname == "Busan"].set_index("date").sort_index().portcalls_container
    f = s.groupby(s.index.day_of_week).median() / s.median()   # 요일효과
    adj = s / s.index.day_of_week.map(f)

    rows = []
    for nm, d0 in EV.items():
        t0 = pd.Timestamp(d0)
        base = adj[(adj.index >= t0 - pd.Timedelta(days=45)) &
                   (adj.index <= t0 - pd.Timedelta(days=15))].median()
        win = s[(s.index >= t0 - pd.Timedelta(days=1)) & (s.index <= t0 + pd.Timedelta(days=7))]
        lo = win.min()
        post = s[(s.index > t0) & (s.index <= t0 + pd.Timedelta(days=7))]
        peak_d = int((post.idxmax() - t0).days); peak = post.max()
        top3 = post.nlargest(3)
        rows.append({
            "에피소드": nm, "상륙일": d0, "평년(척/일)": round(base),
            "최저기항": int(lo), "최저비율": round(lo / base, 2),
            "최대반등일": f"D+{peak_d}", "최대반등": int(peak),
            "최대반등배수": round(peak / base, 2),
            "재개후3일합": int(top3.sum()), "평소3일": round(base * 3),
            "초과분(척)": round(top3.sum() - base * 3),
        })
    t = pd.DataFrame(rows)
    OUT.parent.mkdir(exist_ok=True)
    t.to_csv(OUT, index=False, encoding="utf-8-sig")
    pd.set_option("display.unicode.east_asian_width", True)
    print(t.to_string(index=False))
    print(f"\n합계 초과분 {t['초과분(척)'].sum():.0f}척 / 5개 에피소드")
    print(f"저장: {OUT}")

if __name__ == "__main__":
    main()
