"""항만 × 날짜 패널 이중차분 (two-way fixed effects).

  log(1+기항수)_it = Σ_k β_k·1[상대일=k] + 항만FE_i + 날짜FE_t + ε_it

날짜FE가 "그날 전 세계가 조용했다"를, 항만FE가 "홍콩이 부산보다 크다"를 흡수한다.
남는 β_k가 태풍 효과. 표준오차는 항만 클러스터(G=19, 소표본이라 보수적으로 읽을 것).

사용:  python 2-port/scripts/panel_did.py
"""
import pathlib, numpy as np, pandas as pd

ROOT  = pathlib.Path(__file__).resolve().parents[2]
PANEL = ROOT / "2-port" / "output" / "panel.parquet"
OUTD  = ROOT / "2-port" / "output"
BASE, KS = -7, list(range(-7, 22))
MIN_CONT = 5        # 컨테이너항 기준: 일별 기항 중앙값
RNG = np.random.default_rng(20260519)

# ---------- 추정 엔진 ----------
def absorb(X, fes, tol=1e-10, maxit=300):
    """교대 투영으로 다중 고정효과 흡수 (within 변환)."""
    X = np.asarray(X, float).copy()
    pre = [(c, np.bincount(c).astype(float)) for c in fes]
    for _ in range(maxit):
        d = 0.0
        for c, cnt in pre:
            for j in range(X.shape[1]):
                m = np.bincount(c, weights=X[:, j], minlength=len(cnt)) / cnt
                adj = m[c]; X[:, j] -= adj
                d = max(d, np.abs(adj).max())
        if d < tol: break
    return X

def cluster_ols(y, X, g, names):
    XtXi = np.linalg.pinv(X.T @ X)
    b = XtXi @ (X.T @ y); u = y - X @ b
    meat = np.zeros((X.shape[1],) * 2)
    for gi in np.unique(g):
        m = g == gi; s = X[m].T @ u[m]; meat += np.outer(s, s)
    G, (n, k) = len(np.unique(g)), X.shape
    V = XtXi @ meat @ XtXi * (G / (G - 1)) * ((n - 1) / (n - k))
    se = np.sqrt(np.clip(np.diag(V), 0, None))
    return pd.DataFrame({"term": names, "coef": b, "se": se,
                         "t": b / np.where(se > 0, se, np.nan)})

def event_study(d, label="", ycol="ly", extra_fe=None, evcol="ev_time"):
    d = d.copy()
    d["k"] = d[evcol].where(d[evcol].between(min(KS), max(KS)))
    names = [f"D{k:+d}" for k in KS if k != BASE]
    X = np.column_stack([(d.k == k).to_numpy(float) for k in KS if k != BASE])
    keep = X.any(axis=0)
    X, names = X[:, keep], [n for n, kp in zip(names, keep) if kp]
    fes = [pd.factorize(d.portid)[0], pd.factorize(d.date)[0]]
    if extra_fe is not None: fes.append(pd.factorize(extra_fe.loc[d.index])[0])
    M = absorb(np.column_stack([d[ycol].to_numpy(float), X]), fes)
    r = cluster_ols(M[:, 0], M[:, 1:], pd.factorize(d.portid)[0], names)
    r.insert(0, "spec", label)
    r["k"] = [int(t[1:]) for t in r.term]
    if ycol == "ly":
        for c, s in (("pct", 0), ("lo", -1.96), ("hi", 1.96)):
            r[c] = (np.exp(r.coef + s * r.se) - 1) * 100
    else:
        r["pct"], r["lo"], r["hi"] = r.coef * 100, (r.coef - 1.96*r.se)*100, (r.coef + 1.96*r.se)*100
    return r

def pk(r):
    """반등 구간 D+2~D+6에서 최대 효과와 그 날."""
    w = r.reindex([2, 3, 4, 5, 6]).dropna()
    return w

def bar(v, lo=-100, hi=60, w=42):
    z = round((0 - lo) / (hi - lo) * w); x = round((min(max(v, lo), hi) - lo) / (hi - lo) * w)
    s = [" "] * (w + 1)
    for i in range(min(z, x), max(z, x) + 1): s[i] = "#"
    s[z] = "|"; return "".join(s)

def show(r, lo=-7, hi=10, title=""):
    if title: print(title)
    print(f"{'상대일':>5} {'효과%':>8} {'95%CI':>18} {'t':>6}")
    for _, x in r.sort_values("k").iterrows():
        if not (lo <= x.k <= hi): continue
        st = "*" if abs(x.t) > 1.96 else " "
        print(f"{x.k:>+5d} {x.pct:>+8.1f} [{x.lo:>+6.1f},{x.hi:>+6.1f}] {x.t:>6.2f}{st} {bar(x.pct)}")

# ---------- 분석 ----------
def main():
    p = pd.read_parquet(PANEL)
    med = p.groupby("portname").portcalls_container.median()
    cont = med[med >= MIN_CONT].index
    drop = med[med < MIN_CONT]
    s = p[p.portname.isin(cont)].copy()

    print(f"패널 {len(p):,}행 · 항만 {p.portid.nunique()}개 · "
          f"{p.date.min():%Y-%m-%d}~{p.date.max():%Y-%m-%d}")
    print(f"\n[표본] 컨테이너 기항 중앙값 {MIN_CONT}척 이상인 {len(cont)}개 항만만 사용")
    print(f"  제외 {len(drop)}개: " + ", ".join(f"{i}({v:.0f}척)" for i, v in drop.items()))
    print(f"  제외 항만이 갖고 있던 노출일 {int(p[~p.portname.isin(cont)].exposed.sum())}건"
          f" / 전체 {int(p.exposed.sum())}건 — 컨테이너 신호를 희석시키던 부분")
    print(f"  분석 표본 {len(s):,}행, 노출일 {int(s.exposed.sum())}건,"
          f" 에피소드 {s.ep_id.nunique()}개\n")

    # [0] 조정 전
    a = s[s.exposed == 1].portcalls_container.mean()
    b = s[(s.exposed == 0) & s.ev_time.isna()].portcalls_container.mean()
    print(f"[0] 고정효과 없는 단순 비교: 노출일 {a:.1f}척 vs 평시 {b:.1f}척 ({a/b-1:+.0%})")
    print("    항만 규모·계절·세계 경기가 전부 섞인 숫자 — 이걸 걷어내는 게 아래다\n")

    # [1] 주 사양
    m = event_study(s, "main")
    show(m, -7, 10, "[1] 이벤트 스터디 (기준 D−7, 항만FE+날짜FE, 항만 클러스터 G=%d)" % s.portid.nunique())
    g = m.set_index("k")
    print(f"\n    상륙일 {g.pct[0]:+.0f}%, 이튿날 {g.pct[1]:+.0f}% → "
          f"D+{int(pk(g.pct).idxmax())}에 {pk(g.pct).max():+.0f}%로 반등")

    # [2] 강건성
    print("\n[2] 강건성 — D0/D+1이 거의 안 움직이면 결과가 사양에 안 기댄다는 뜻")
    specs = {"주 사양": m,
             "항만×월 FE 추가": event_study(s, "pm", extra_fe=s.portid + s.date.dt.month.astype(str)),
             "항만×연 FE 추가": event_study(s, "py", extra_fe=s.portid + s.date.dt.year.astype(str)),
             "비율(평년=1) 종속": event_study(s, "ratio", ycol="ratio"),
             "전체기항 종속":   event_study(s.assign(ly=np.log1p(s.portcalls)), "allcalls"),
             "대만·중국 제외":  event_study(s[~s.country.isin(["Taiwan Province of China","China"])], "nocn"),
             "부산 제외":       event_study(s[s.portname != "Busan"], "nobusan")}
    print(f"{'사양':<20}{'D−1':>8}{'D0':>8}{'D+1':>8}{'D+3':>8}{'D+4':>8}")
    for nm, r in specs.items():
        gg = r.set_index("k").pct
        print(f"{nm:<20}" + "".join(f"{gg.get(k, np.nan):>+8.1f}" for k in (-1, 0, 1, 3, 4)))

    # [3] 플라시보
    print("\n[3] 플라시보 — 가짜 태풍일을 무작위로 심으면 효과가 사라져야 한다")
    ph = []
    real = s.loc[s.exposed == 1, ["portid", "date"]]
    for it in range(200):
        fake = s[["portid", "date"]].sample(len(real), random_state=int(RNG.integers(1e9)))
        t = s.merge(fake.assign(f=1), on=["portid", "date"], how="left")
        t["ev"] = np.nan
        idx = t.index[t.f == 1]
        for i in idx:
            pid, d0 = t.at[i, "portid"], t.at[i, "date"]
            w = t.index[(t.portid == pid) & t.date.between(d0 - pd.Timedelta(days=7), d0 + pd.Timedelta(days=21))]
            t.loc[w, "ev"] = (t.loc[w, "date"] - d0).dt.days.to_numpy()
        if it >= 20: break
        ph.append(event_study(t, "ph", evcol="ev").set_index("k").pct.get(0, np.nan))
    ph = np.array([x for x in ph if np.isfinite(x)])
    print(f"    무작위 20회 D0 효과: 중앙 {np.median(ph):+.1f}%, "
          f"범위 [{ph.min():+.1f}, {ph.max():+.1f}]  vs  실제 {g.pct[0]:+.1f}%")
    print(f"    → 실제값이 플라시보 분포 {'밖' if g.pct[0] < ph.min() else '안'}에 있다")

    # [4] 용량-반응
    print("\n[4] 용량-반응 — 34kt 노출시간이 길수록 더 멈추나")
    ep = (s[s.exposed == 1].groupby("ep_id")
            .agg(h34=("h34", "sum"), port=("portname", "first")).dropna())
    cut = ep.h34.quantile([0, .33, .66, 1.0]).to_numpy()
    rows = []
    for i, nm in enumerate(["약(하위1/3)", "중", "강(상위1/3)"]):
        ids = ep.index[(ep.h34 >= cut[i]) & (ep.h34 <= cut[i+1])]
        sub = s[s.ep_id.isin(ids) | s.ev_time.isna()]
        r = event_study(sub, nm).set_index("k").pct
        rows.append((nm, f"{cut[i]:.0f}-{cut[i+1]:.0f}h", len(ids), r.get(0), r.get(1), pk(r).max()))
    print(f"{'강도':<12}{'34kt시간':>10}{'에피소드':>8}{'D0':>9}{'D+1':>9}{'최대반등':>9}")
    for nm, h, n, d0, d1, peak in rows:
        print(f"{nm:<12}{h:>10}{n:>8}{d0:>+9.1f}{d1:>+9.1f}{peak:>+9.1f}")

    # [5] 항만 유형별 이질성
    print("\n[5] 유형별 — 컨테이너 집약 vs 탱커 집약")
    ts = s.groupby("portname").tanker_share.median()
    hi = ts[ts >= ts.median()].index
    for nm, idx in [("탱커비중 높은 절반", hi), ("탱커비중 낮은 절반", ts.index.difference(hi))]:
        r = event_study(s[s.portname.isin(idx)], nm).set_index("k").pct
        print(f"  {nm:<18} D0 {r.get(0):+6.1f}%  D+1 {r.get(1):+6.1f}%  "
              f"최대반등 {pk(r).max():+5.1f}% (D+{int(pk(r).idxmax())})")

    # [6] 부산 단독 vs 패널
    print("\n[6] 부산 단독 vs 패널 평균")
    rb = event_study(s[(s.portname == "Busan") | s.ev_time.isna()], "busan").set_index("k").pct
    print(f"  부산        D0 {rb.get(0):+6.1f}%  D+1 {rb.get(1):+6.1f}%  최대반등 {rb[2:6].max():+5.1f}%")
    print(f"  패널 평균    D0 {g.pct[0]:+6.1f}%  D+1 {g.pct[1]:+6.1f}%  최대반등 {pk(g.pct).max():+5.1f}%")

    # [7] 누적 손실/회복
    print("\n[7] 누적 — 상륙 전후 기항이 얼마나 사라졌다 돌아오나 (평년 대비 척·일)")
    base_lvl = s.groupby("portid").portcalls_container.median().mean()
    cum = 0.0
    for k in range(-3, 15):
        v = g.pct.get(k, 0.0) / 100 * base_lvl
        cum += v
        if k in (-1, 0, 1, 2, 3, 5, 7, 10, 14):
            print(f"   D{k:>+3d}  일별 {v:>+6.1f}척   누적 {cum:>+7.1f}척")

    pd.concat(specs.values()).to_csv(OUTD / "did_robustness.csv", index=False)
    m.to_csv(OUTD / "did_event_study.csv", index=False)
    print(f"\n저장: {OUTD/'did_event_study.csv'}, {OUTD/'did_robustness.csv'}")

if __name__ == "__main__":
    main()
