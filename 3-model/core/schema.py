"""인스턴스와 1단계 결정의 스키마 + 검증.

모든 planner는 여기 정의된 모양만 주고받는다. 모양이 다르면 run_all이 거부한다.
"""
from __future__ import annotations
import json, hashlib, pathlib

# ── 인스턴스 ───────────────────────────────────────────────────────────────
# {
#   "id": "grid_rho075_close24_s01",
#   "meta":    {"rho": 0.75, "t_close_h": 24, "seed": 1},
#   "berths":  [{"id":"B1","length_m":400,"q_max":4}, ...],
#   "cranes":  {"total": 12, "rate_tph": 390.0},
#   "vessels": [{"id":"V01","arrival_h":0.0,"loa_m":294,
#                "workload_t":10300.0,"q_min":1,"q_max":4}, ...],
#   "recovery":{"t_reopen_h":24.0,"kappa":0.7,"kappa_recover_h":12.0},
#   "horizon_h": 72
# }
#
# ── 1단계 결정 (stage1) ────────────────────────────────────────────────────
# {
#   "sequence": {"B1": ["V01","V05"], "B2": ["V02"], ...},   # 선석별 접안 순서
#   "cranes":   {"V01": 3, "V02": 2, ...}                    # 선박별 크레인 수
# }
# 시작 시각 S_i 는 여기 들어가지 않는다. 그건 2단계(recourse)의 결과다.

REQ_INSTANCE = ("id", "berths", "cranes", "vessels", "recovery", "horizon_h")

def load_instance(path) -> dict:
    p = pathlib.Path(path)
    inst = json.loads(p.read_text(encoding="utf-8"))
    validate_instance(inst)
    inst["_sha"] = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    return inst

def validate_instance(inst: dict) -> None:
    for k in REQ_INSTANCE:
        if k not in inst:
            raise ValueError(f"인스턴스에 '{k}' 없음")
    ids = [v["id"] for v in inst["vessels"]]
    if len(ids) != len(set(ids)):
        raise ValueError("선박 id 중복")
    for v in inst["vessels"]:
        if not (1 <= v["q_min"] <= v["q_max"]):
            raise ValueError(f"{v['id']}: 크레인 하한/상한 이상")

def validate_stage1(inst: dict, s1: dict) -> None:
    """1단계 결정이 말이 되는지. planner가 뭘 내든 여기서 걸러진다."""
    if set(s1) != {"sequence", "cranes"}:
        raise ValueError("stage1은 'sequence'와 'cranes'만 가진다")
    vessels = {v["id"]: v for v in inst["vessels"]}
    berths  = {b["id"]: b for b in inst["berths"]}

    placed = [v for seq in s1["sequence"].values() for v in seq]
    if sorted(placed) != sorted(vessels):
        raise ValueError("모든 선박이 정확히 한 번씩 배정돼야 함")
    for b, seq in s1["sequence"].items():
        if b not in berths:
            raise ValueError(f"없는 선석: {b}")
        for vid in seq:                       # 선박이 선석에 물리적으로 들어가나
            if vessels[vid]["loa_m"] > berths[b]["length_m"]:
                raise ValueError(f"{vid}가 {b}보다 김")
    for vid, q in s1["cranes"].items():
        v = vessels[vid]
        b = next(b for b, seq in s1["sequence"].items() if vid in seq)
        if not (v["q_min"] <= q <= min(v["q_max"], berths[b]["q_max"])):
            raise ValueError(f"{vid}: 크레인 {q}대가 범위 밖")
        if q > inst["cranes"]["total"]:
            raise ValueError(f"{vid}: 크레인 수가 전체보다 많음")
