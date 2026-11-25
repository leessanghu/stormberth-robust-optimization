"""fcfs"""
from __future__ import annotations


def plan(inst, cfg, real=None):
    """반환:
        {"sequence": {선석id: [선박id, ...]},
         "cranes":   {선박id: 크레인수}}

    제약 (validate_stage1 이 검사):
        (C1) 모든 선박이 정확히 한 번씩
        (C2) loa_m <= 그 선석의 length_m
        (C3) q_min <= 크레인수 <= min(q_max, 그 선석의 q_max)

    시작 시각은 반환하지 않는다.
    """
    
    # 1. 선석과 선박 정보 가져오기
    berths = sorted(inst["berths"], key=lambda b: b["id"])
    vessels = sorted(
        inst["vessels"],
        key=lambda v: (v["arrival_h"], v["id"])
    )

    # 2. 배정 결과를 저장할 공간
    sequence = {b["id"]: [] for b in berths}
    cranes = {}

    # 3. 기본 크레인 배정 대수
    q_base = 4
    rate_tph = inst["cranes"]["rate_tph"] #rate_tph: 크레인 한 대의 시간당 처리
    reopen_h = inst["recovery"]["t_reopen_h"] #reopen_h: 항만이 다시 열리는 시각
    available_h = {b["id"]: reopen_h for b in berths} #처음에는 모든 선석을 항만 재개 시각부터 사용가능

    # 4. 도착시간이 빠른 선박부터 처리
    for v in vessels:
        possible = [
            b for b in berths
            if v["loa_m"] <= b["length_m"]
            and v["q_min"] <= min(v["q_max"], b["q_max"])
        ]

        if not possible:
            raise ValueError(f"{v['id']}: 배정 가능한 선석이 없습니다.")

        # 이미 배정 작업이 가장 먼저 끝나는 선석 선택
        berth = min(
            possible,
            key=lambda b: (available_h[b["id"]], b["id"]))
        berth_id = berth["id"]
        

        # 허용 범위 내에서 크레인 수 결정
        q_max = min(v["q_max"], berth["q_max"])
        q = max(v["q_min"], min(q_base, q_max))

        #선박 도착 후 선석이 비었을 때 작업 시작 가능.
        start_h = max(v["arrival_h"], avilable_h[berth_id])
        duration_h = v["workload_t"] / (q * rate_tph)
        available_h[berth_id] = start_h + duration_h

        sequence[berth["id"]].append(v["id"])
        cranes[v["id"]] = q

    return {
        "sequence": sequence,
        "cranes": cranes
    }

