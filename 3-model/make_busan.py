"""부산 태풍 에피소드 인스턴스 생성 — 2단계 실측을 그대로 꽂는다.

실행:  python 3-model/make_busan.py

출처
----
도착 수·시점 : 2-port/output/busan_event_trend.csv 의 **실제 일별 기항 수**
               (태풍별로 폐쇄일과 반등일이 관측값 그대로 들어온다)
폐쇄 구간    : 기항 0척인 날
불확실성     : config.yaml 의 uncertainty 절

가정 (실측 아님 — 민감도 대상)
------------------------------
터미널 점유율 SHARE : 부산항 전체 기항 중 이 터미널 몫
선석 구성 / 크레인  : 제원 미수집. 조사되면 BERTHS·Q_TOTAL 을 교체한다
kappa               : 재개 직후 크레인 생산성

불확실성 두 가지를 반드시 구분한다 (make_samples.py 와 동일)
  이질성 CV 1.00 : 선박 크기 차이. 터미널이 **미리 안다**  -> 인스턴스에만
  예측오차 CV 0.20: 부킹 대비 실제. 터미널이 **모른다**    -> 실현에만
  섞으면 어떤 최적화도 FCFS 를 못 이긴다.

  주의: workload_calibration.csv 의 CV 0.237 은 **일별 기항당 평균**의 변동이지
  선박 사이의 변동이 아니다. 그 값을 이질성에 쓰면 모든 배가 똑같아져서
  선석 배정 자체가 의미를 잃는다.
"""
from __future__ import annotations
import csv, json, math, pathlib, random, collections

HERE  = pathlib.Path(__file__).resolve().parent
OUT   = HERE / "instances"
TREND = HERE.parent / "2-port" / "output" / "busan_event_trend.csv"

W_MED   = 10297.0     # 기항당 작업량 중앙값 (t) — 2-port/output/workload_calibration.csv
RATE    = 390.0       # t/h, 크레인 1기            [가정]
SHARE   = 0.23        # 터미널 점유율. 평년일 가동률 rho=0.70 이 되도록 맞춤  [가정]
Q_TOTAL = 12          # 안벽크레인 수              [가정]
KAPPA   = 0.75        # 재개 직후 생산성           [가정]
BERTHS  = [{"id": f"B{i+1}", "length_m": L, "q_max": 4}
           for i, L in enumerate([400, 400, 350, 300])]      # [가정]
LOA     = [200, 250, 294, 330]                               # [가정]
HORIZON = 72.0


def load_cfg() -> dict:
    import yaml
    return yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))


def lognorm(rnd: random.Random, cv: float) -> float:
    """변동계수 cv, 평균 1 인 로그정규 난수. cv 를 sigma 자리에 넣으면 안 된다."""
    s = math.sqrt(math.log(1.0 + cv * cv))
    return rnd.lognormvariate(0.0, s) * math.exp(-s * s / 2.0)


def load_trend() -> dict:
    """에피소드별 {상대일: 기항 수}."""
    ep: dict[str, dict[int, float]] = collections.defaultdict(dict)
    with open(TREND, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            try:
                ep[r["event"]][int(r["offset"])] = float(r["calls"])
            except (ValueError, KeyError, TypeError):
                continue
    return dict(ep)


def window(days: dict[int, float]) -> tuple[int, list[float]]:
    """마지막 폐쇄일(기항 0척)을 찾아 [C, C+2] 72시간 창을 돌려준다."""
    zeros = [k for k, v in days.items() if v == 0 and -3 <= k <= 6]
    c = max(zeros) if zeros else 0
    return c, [days.get(c + d, 0.0) for d in (0, 1, 2)]


def make(name: str, days: dict[int, float], seed: int, cv_het: float) -> dict:
    rnd = random.Random(seed * 7001 + sum(map(ord, name)))
    c, calls = window(days)
    vessels = []
    for d, k in enumerate(calls):
        for _ in range(int(round(k * SHARE))):
            i = len(vessels) + 1
            vessels.append({
                "id": f"V{i:02d}",
                "arrival_h":  round(d * 24.0 + rnd.uniform(0.0, 24.0), 2),
                "loa_m":      rnd.choice(LOA),
                "workload_t": round(W_MED * lognorm(rnd, cv_het), 1),
                "q_min": 1, "q_max": 4,
            })
    vessels.sort(key=lambda v: v["arrival_h"])
    for i, v in enumerate(vessels, 1):
        v["id"] = f"V{i:02d}"

    tag = name.split()[0]
    return {
        "id": f"busan{tag}_s{seed}",
        "meta": {"episode": name, "closure_offset": c,
                 "calls_observed": calls, "share": SHARE,
                 "source": "2-port/output/busan_event_trend.csv"},
        "berths": BERTHS,
        "cranes": {"total": Q_TOTAL, "rate_tph": RATE},
        "vessels": vessels,
        "recovery": {"t_reopen_h": 24.0 * sum(1 for k in calls if k == 0),
                     "kappa": KAPPA, "kappa_recover_h": 12.0},
        "horizon_h": HORIZON,
    }


def realizations(inst: dict, n: int, seed: int, cv_err: float, jit: float) -> list[dict]:
    """평가용 실현. 인스턴스와 같이 커밋해서 재현을 보장한다."""
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

    cfg = load_cfg()
    unc = cfg["uncertainty"]
    cv_het, cv_err = unc["workload_cv_hetero"], unc["workload_cv_error"]
    jit = unc["arrival_jitter_h"]
    n_real = int(cfg["run"]["n_realization"])

    OUT.mkdir(parents=True, exist_ok=True)
    trend = load_trend()
    if not trend:
        raise SystemExit("기항 자료를 못 읽었습니다: %s" % TREND)

    print("부산 에피소드 %d개  (실현 %d개, 이질성 CV %.2f, 예측오차 CV %.2f)"
          % (len(trend), n_real, cv_het, cv_err))
    for name in sorted(trend):
        c, calls = window(trend[name])
        print("  %-18s 폐쇄 D%+d  관측 기항 %s  ->  터미널 %d척"
              % (name, c, "/".join("%.0f" % x for x in calls),
                 round(sum(calls) * SHARE)))
        for sd in (1, 2, 3):
            inst = make(name, trend[name], sd, cv_het)
            validate_instance(inst)
            (OUT / f"{inst['id']}.json").write_text(
                json.dumps(inst, ensure_ascii=False, indent=1), encoding="utf-8")
            (OUT / f"{inst['id']}.real.json").write_text(
                json.dumps(realizations(inst, n_real, sd, cv_err, jit),
                           ensure_ascii=False), encoding="utf-8")
            print("    %-18s %2d척  재개 %.0fh" % (inst["id"], len(inst["vessels"]),
                                                   inst["recovery"]["t_reopen_h"]))
