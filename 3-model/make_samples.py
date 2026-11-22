"""샘플 인스턴스 3개 + 실현 시나리오 생성 (팀원 A가 바로 테스트할 수 있게).

정식 생성기는 팀원 B가 만든다 — 이건 1주차용 임시 픽스처다.
실행:  python 3-model/make_samples.py
"""
from __future__ import annotations
import json, math, pathlib, random

OUT = pathlib.Path(__file__).resolve().parent / "instances"
RATE = 390.0        # t/h, 크레인 1기 (팀원 B가 확정)
W_MED = 10300.0     # 기항당 작업량 중앙값 — 부산 실측

# ── 불확실성 두 가지를 반드시 구분한다 ──────────────────────────────────────
# HET: 선박 간 이질성. 피더선과 초대형선의 크기 차이.
#      터미널이 **미리 안다** (선적계획·부킹). 인스턴스를 만들 때만 쓴다.
# ERR: 예측오차. 부킹 대비 실제가 얼마나 틀리나.
#      터미널이 **모른다**. 실현 시나리오를 만들 때만 쓴다.
# 둘을 같은 값으로 쓰면 '배가 올 때까지 크기를 모른다'는 뜻이 되어,
# 어떤 최적화도 FCFS 를 못 이긴다 (실측 확인).
W_CV_HET = 1.00     # 선박 간 이질성
W_CV_ERR = 0.20     # 작업량 예측오차
A_JIT_H  = 4.0      # 도착시각 예측오차 (±시간)

def lognorm(rnd, cv):
    """변동계수 cv, 평균 1 인 로그정규 난수.

    주의: cv 를 sigma 자리에 그대로 넣으면 안 된다. cv=1.87 이면
    실제 변동계수가 5.66 이 되고 평균이 5.75배로 뛴다.
    """
    s = math.sqrt(math.log(1.0 + cv * cv))
    return rnd.lognormvariate(0.0, s) * math.exp(-s * s / 2.0)

BERTHS = [{"id": f"B{i+1}", "length_m": L, "q_max": 4}
          for i, L in enumerate([400, 400, 350, 350])]
Q_TOTAL = 12

def make(rho: float, t_close: float, seed: int) -> dict:
    rnd = random.Random(seed)
    horizon = 72.0
    cap_ch  = Q_TOTAL * horizon                  # 쓸 수 있는 크레인·시간
    per_ch  = W_MED / RATE                       # 선박 1척당 크레인·시간
    n = max(4, round(rho * cap_ch / per_ch))

    vessels = []
    for i in range(n):
        # 폐쇄 중 쌓인 배는 재개 시각 이전에 도착(= 대기 중), 이후는 계속 들어옴
        if i < int(n * t_close / (t_close + 24)):
            a = rnd.uniform(0.0, t_close)
        else:
            a = t_close + rnd.uniform(0.0, 36.0)
        vessels.append({
            "id": f"V{i+1:02d}", "arrival_h": round(a, 2),
            "loa_m": rnd.choice([200, 250, 294, 330]),
            "workload_t": round(W_MED * lognorm(rnd, W_CV_HET), 1),
            "q_min": 1, "q_max": 4,
        })
    return {
        "id": f"sample_rho{int(rho*100)}_close{int(t_close)}_s{seed}",
        "meta": {"rho": rho, "t_close_h": t_close, "seed": seed},
        "berths": BERTHS, "cranes": {"total": Q_TOTAL, "rate_tph": RATE},
        "vessels": vessels,
        "recovery": {"t_reopen_h": t_close, "kappa": 0.75, "kappa_recover_h": 12.0},
        "horizon_h": horizon,
    }

def realizations(inst: dict, n: int, seed: int) -> list[dict]:
    """평가용 실현 시나리오. 인스턴스와 **같이 커밋**해서 재현을 보장한다."""
    out = []
    for k in range(n):
        rnd = random.Random(seed * 1000 + k)
        out.append({
            "id": f"{inst['id']}_r{k:02d}",
            "arrival_h":  {v["id"]: round(max(0.0, v["arrival_h"] + rnd.uniform(-A_JIT_H, A_JIT_H)), 2)
                           for v in inst["vessels"]},
            "workload_t": {v["id"]: round(v["workload_t"] * lognorm(rnd, W_CV_ERR), 1)
                           for v in inst["vessels"]},
        })
    return out

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for rho, tc, sd in [(0.60, 24, 1), (0.75, 24, 2), (0.90, 48, 3)]:
        inst = make(rho, tc, sd)
        (OUT / f"{inst['id']}.json").write_text(
            json.dumps(inst, ensure_ascii=False, indent=1), encoding="utf-8")
        (OUT / f"{inst['id']}.real.json").write_text(
            json.dumps(realizations(inst, 20, sd), ensure_ascii=False), encoding="utf-8")
        print(f"{inst['id']}  선박 {len(inst['vessels'])}척  실현 20개")
