"""기항당 하역 물동량 분포를 뽑는다 — 모형의 처리시간 H_i 보정용.

PortWatch는 선박별 타임스탬프가 없지만 일별 물동량/기항수는 있다.
그 비(比)가 '기항 1건당 평균 작업량'이고, 이 분포가 H_i 생성의 근거가 된다.

사용:  python 2-port/scripts/workload_calib.py
"""
import csv, datetime, pathlib, statistics

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "portwatch" / "daily_ports.csv"
OUT = ROOT / "output" / "workload_calibration.csv"
BUSAN = "port1065"
EPISODES = {  # 상륙일
    "2019 타파": "2019-09-22", "2020 마이삭+하이선": "2020-09-02",
    "2021 오마이스+찬투": "2021-08-23", "2022 힌남노+난마돌": "2022-09-05",
    "2023 카눈": "2023-08-10",
}

def num(r, k):
    v = r.get(k, "")
    return float(v) if v not in ("", "NaN", None) else 0.0

def main():
    rd = csv.DictReader(open(SRC, encoding="utf-8-sig"))
    dkey = rd.fieldnames[0]
    rows = []
    for r in rd:
        if r["portid"] != BUSAN:
            continue
        calls = num(r, "portcalls_container")
        if calls <= 0:
            continue
        tons = num(r, "import_container") + num(r, "export_container")
        rows.append((datetime.datetime.strptime(r[dkey].split()[0], "%Y/%m/%d").date(),
                     calls, tons / calls))

    allv = [w for _, _, w in rows]
    recov = set()
    for d0 in EPISODES.values():
        b = datetime.date.fromisoformat(d0)
        recov |= {b + datetime.timedelta(days=k) for k in range(1, 8)}
    rv = [w for d, _, w in rows if d in recov]

    def stat(name, v):
        q = statistics.quantiles(v, n=4)
        return {"구분": name, "일수": len(v), "중앙값": round(statistics.median(v)),
                "Q1": round(q[0]), "Q3": round(q[2]),
                "변동계수": round(statistics.pstdev(v) / statistics.mean(v), 3)}

    recs = [stat("전체", allv), stat("태풍 재개 직후 D+1~D+7", rv)]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(recs[0]))
        w.writeheader(); w.writerows(recs)

    print("기항 1건당 컨테이너 물동량 (톤)")
    for r in recs:
        print(f"  {r['구분']:<22} n={r['일수']:>5}  중앙 {r['중앙값']:>6}  "
              f"Q1-Q3 {r['Q1']}-{r['Q3']}  CV {r['변동계수']}")
    print(f"\n저장: {OUT}")

if __name__ == "__main__":
    main()
