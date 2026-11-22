"""실측 태풍 에피소드 인스턴스 생성 — 아시아 21개 항만 x 2019~ 태풍 전수.

실행:  python 3-model/make_episodes.py

무엇을 하나
-----------
PortWatch 일별 기항 수에서 **기항이 실제로 끊긴 날**을 찾고, 그 시점에 34kt
이상 바람이 있던 태풍과 맞춘다. 그렇게 걸러진 에피소드마다 인스턴스 1개.

거르는 기준 두 개 (둘 다 연구 질문에서 바로 나온다)
  반등 >= MIN_PEAK : 폐쇄만 되고 반등이 없으면 backlog 가 없다. 우리 문제가 아니다.
  평년 >= MIN_BASE : 터미널 몫으로 나누면 1~2척이라 배정할 게 없다.

터미널을 어떻게 잡나
--------------------
항만마다 터미널 제원이 다르지만 **아무 데도 공개돼 있지 않다.** 그래서 모든
항만에 **같은 가상 터미널**(선석 4개, 크레인 12기)을 두고, 점유율만 항만별로
"평년 가동률 RHO_BASE 가 되도록" 맞춘다.

  => 인스턴스 사이의 차이는 **도착 패턴 하나**에서만 온다. 통제된 비교다.
  => "가오슝 터미널을 재현했다"가 아니라 "가오슝에서 관측된 도착 패턴을 썼다".

불확실성 두 가지를 반드시 구분한다 (make_samples.py 와 동일)
  이질성 CV   : 선박 크기 차이. 터미널이 **미리 안다**  -> 인스턴스에만
  예측오차 CV : 부킹 대비 실제. 터미널이 **모른다**     -> 실현에만
  섞으면 어떤 최적화도 FCFS 를 못 이긴다.

  주의: workload_calibration.csv 의 CV 0.237 은 **일별 기항당 평균**의 변동이지
  선박 사이의 변동이 아니다. 이질성에 쓰면 모든 배가 똑같아져 배정이 무의미해진다.
"""
from __future__ import annotations
import csv, json, math, pathlib, random, datetime as dt

HERE   = pathlib.Path(__file__).resolve().parent
ROOT   = HERE.parent
OUT    = HERE / "instances"
CALLS  = ROOT / "2-port" / "data" / "portwatch" / "daily_ports.csv"
EXPO   = ROOT / "1-typhoon" / "output" / "asia_port_exposure.csv"

# ── 거르는 기준 ──────────────────────────────────────────────────────────
MIN_PEAK  = 1.30     # 폐쇄 후 3일 안에 평년의 이 배수 이상으로 반등해야 backlog 다
MIN_BASE  = 20.0     # 평년 기항 수 (척/일). 이보다 작으면 터미널 몫이 너무 적다
CLOSED_R  = 0.15     # 평년 대비 이 비율 이하인 날을 '폐쇄'로 본다
MAX_DIST  = 600.0    # 태풍 중심까지 거리 상한 (km)
BASE_WIN  = 43       # 기준선 중앙값 창 (중심 롤링, 일)

# ── 가정 (실측 아님 — 전부 민감도 대상) ─────────────────────────────────
W_MED     = 10297.0  # 기항당 작업량 중앙값 (t) — 2-port/output/workload_calibration.csv
RATE      = 390.0    # t/h, 크레인 1기
Q_TOTAL   = 12       # 안벽크레인 수
KAPPA     = 0.75     # 재개 직후 생산성
RHO_BASE  = 0.70     # 평년 가동률. 항만별 점유율을 여기에 맞춘다
BERTHS    = [{"id": f"B{i+1}", "length_m": L, "q_max": 4}
             for i, L in enumerate([400, 400, 350, 300])]
LOA       = [200, 250, 294, 330]
HORIZON   = 72.0

PORT_KO = {  # PortWatch 표기 -> asia_port_exposure.csv 표기
    "Busan": "부산", "Gwangyang (Kwangyang)": "광양", "Incheon": "인천", "Ulsan": "울산",
    "Hakata": "하카타", "Kagoshima": "가고시마", "Kitakyushu (Wakamatsu)": "기타큐슈",
    "Kobe": "고베", "Nagoya": "나고야", "Naha": "나하", "Osaka": "오사카", "Tokyo": "도쿄",
    "Yokohama": "요코하마", "Kaohsiung": "가오슝", "Keelung": "지룽", "Taichung": "타이중",
    "Hong Kong": "홍콩", "Ningbo": "닝보", "Qingdao Port": "칭다오", "Shanghai": "상하이",
    "Shekou (Shenzhen)": "선전", "Xiamen": "샤먼",
}
ROMAN = {v: k.split(" (")[0].replace(" ", "") for k, v in PORT_KO.items()}


def load_cfg() -> dict:
    import yaml
    return yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))


def lognorm(rnd: random.Random, cv: float) -> float:
    """변동계수 cv, 평균 1 인 로그정규 난수. cv 를 sigma 자리에 넣으면 안 된다."""
    s = math.sqrt(math.log(1.0 + cv * cv))
    return rnd.lognormvariate(0.0, s) * math.exp(-s * s / 2.0)


def median(xs: list[float]) -> float:
    xs = sorted(xs); n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def load_calls() -> dict[str, dict[dt.date, float]]:
    """항만별 {날짜: 기항 수}."""
    out: dict[str, dict[dt.date, float]] = {}
    with open(CALLS, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            ko = PORT_KO.get(r["portname"])
            if ko is None:
                continue
            try:
                d = dt.datetime.strptime(r["date"], "%Y/%m/%d").date()
                out.setdefault(ko, {})[d] = float(r["portcalls"])
            except (ValueError, KeyError):
                continue
    return out


def baseline(series: dict[dt.date, float], day: dt.date) -> float:
    """전후 BASE_WIN//2 일의 중앙값."""
    h = BASE_WIN // 2
    xs = [series[day + dt.timedelta(days=k)] for k in range(-h, h + 1)
          if day + dt.timedelta(days=k) in series]
    return median(xs) if len(xs) >= 15 else float("nan")


def find_episodes() -> list[dict]:
    calls = load_calls()
    expo = []
    with open(EXPO, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            try:
                if float(r["h34"]) <= 0 or float(r["dist"]) >= MAX_DIST:
                    continue
                expo.append({"port": r["port"], "season": int(r["season"]),
                             "name": r["name"],
                             "t0": dt.datetime.fromisoformat(r["t0"]).date(),
                             "h34": float(r["h34"]), "IKE": float(r["IKE"]),
                             "dist": float(r["dist"])})
            except (ValueError, KeyError):
                continue

    seen, eps = set(), []
    for e in expo:
        ser = calls.get(e["port"])
        if not ser:
            continue
        # 상륙 +-2일 안에서 폐쇄일을 찾는다
        closure = None
        for k in range(-2, 3):
            day = e["t0"] + dt.timedelta(days=k)
            if day not in ser:
                continue
            b = baseline(ser, day)
            if b == b and b > 0 and ser[day] / b <= CLOSED_R:
                closure = day
                break
        if closure is None or (e["port"], closure) in seen:
            continue

        win = [closure + dt.timedelta(days=d) for d in (0, 1, 2)]
        if any(d not in ser for d in win):
            continue
        bases = [baseline(ser, d) for d in win]
        if any(b != b for b in bases):
            continue
        base = sum(bases) / 3.0
        obs = [ser[d] for d in win]
        peak = max(o / b for o, b in zip(obs, bases))
        if base < MIN_BASE or peak < MIN_PEAK:
            continue

        seen.add((e["port"], closure))
        eps.append({**e, "closure": closure, "calls": obs, "base": base,
                    "peak": peak, "n_closed": sum(1 for o, b in zip(obs, bases)
                                                  if o / b <= CLOSED_R)})
    eps.sort(key=lambda x: (x["port"], x["closure"]))
    return eps


def make(ep: dict, seed: int, cv_het: float) -> dict:
    """평년 가동률 RHO_BASE 가 되도록 점유율을 맞춘 가상 터미널 인스턴스."""
    rnd = random.Random(seed * 7001 + hash(ep["port"]) % 9973)
    per_ch   = W_MED / RATE                       # 선박 1척당 크레인·시간
    n_target = RHO_BASE * Q_TOTAL * 24.0 / per_ch  # 평년 하루에 이만큼 받는 터미널
    share    = n_target / ep["base"]

    vessels = []
    for d, k in enumerate(ep["calls"]):
        for _ in range(int(round(k * share))):
            vessels.append({
                "arrival_h":  round(d * 24.0 + rnd.uniform(0.0, 24.0), 2),
                "loa_m":      rnd.choice(LOA),
                "workload_t": round(W_MED * lognorm(rnd, cv_het), 1),
                "q_min": 1, "q_max": 4,
            })
    vessels.sort(key=lambda v: v["arrival_h"])
    for i, v in enumerate(vessels, 1):
        v["id"] = f"V{i:02d}"

    iid = "ep_%s%d%s_s%d" % (ROMAN.get(ep["port"], ep["port"]), ep["season"],
                             ep["name"].replace("-", "").title()[:6], seed)
    return {
        "id": iid,
        "meta": {"port": ep["port"], "season": ep["season"], "storm": ep["name"],
                 "closure": str(ep["closure"]), "calls_observed": ep["calls"],
                 "base_calls": round(ep["base"], 1), "peak_ratio": round(ep["peak"], 2),
                 "share": round(share, 3), "h34": ep["h34"], "IKE": round(ep["IKE"]),
                 "dist_km": round(ep["dist"]),
                 "source": "PortWatch daily_ports.csv + 1-typhoon/output/asia_port_exposure.csv"},
        "berths": BERTHS,
        "cranes": {"total": Q_TOTAL, "rate_tph": RATE},
        "vessels": vessels,
        "recovery": {"t_reopen_h": 24.0 * ep["n_closed"],
                     "kappa": KAPPA, "kappa_recover_h": 12.0},
        "horizon_h": HORIZON,
    }


def realizations(inst: dict, n: int, seed: int, cv_err: float, jit: float) -> list[dict]:
    out = []
    for k in range(n):
        rnd = random.Random(seed * 1000 + k)
        out.append({
            "id": f"{inst['id']}_r{k:02d}",
            "arrival_h":  {v["id"]: round(max(0.0, v["arrival_h"] + rnd.uniform(-jit, jit)), 2)
                           for v in inst["vessels"]},
            "workload_t": {v["id"]: round(v["workload_t"] * lognorm(rnd, cv_err), 1)
                           for v in inst["vessels"]},
        })
    return out


if __name__ == "__main__":
    from core.schema import validate_instance

    cfg = load_cfg(); unc = cfg["uncertainty"]
    cv_het, cv_err = unc["workload_cv_hetero"], unc["workload_cv_error"]
    jit, n_real = unc["arrival_jitter_h"], int(cfg["run"]["n_realization"])

    OUT.mkdir(parents=True, exist_ok=True)
    eps = find_episodes()
    print("기항이 끊긴 에피소드 %d건 / 항만 %d개  (반등>=%.2f, 평년>=%.0f척)"
          % (len(eps), len({e["port"] for e in eps}), MIN_PEAK, MIN_BASE))
    print("실현 %d개, 이질성 CV %.2f, 예측오차 CV %.2f\n" % (n_real, cv_het, cv_err))
    print("  %-26s %-4s %-10s %-11s %5s %5s %5s" %
          ("인스턴스", "척", "관측기항", "태풍", "반등", "점유", "폐쇄h"))
    for i, ep in enumerate(eps, 1):
        inst = make(ep, 1, cv_het)
        if len(inst["vessels"]) < 6:
            print("  (건너뜀, 선박 %d척) %s %s" % (len(inst["vessels"]), ep["port"], ep["name"]))
            continue
        validate_instance(inst)
        (OUT / f"{inst['id']}.json").write_text(
            json.dumps(inst, ensure_ascii=False, indent=1), encoding="utf-8")
        (OUT / f"{inst['id']}.real.json").write_text(
            json.dumps(realizations(inst, n_real, i, cv_err, jit), ensure_ascii=False),
            encoding="utf-8")
        m = inst["meta"]
        print("  %-26s %3d  %-10s %-11s %5.2f %5.2f %5.0f"
              % (inst["id"], len(inst["vessels"]),
                 "/".join("%.0f" % x for x in m["calls_observed"]),
                 m["storm"][:11], m["peak_ratio"], m["share"],
                 inst["recovery"]["t_reopen_h"]))
