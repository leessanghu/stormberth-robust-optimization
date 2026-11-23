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
    q_base = max(1, inst["cranes"]["total"] // len(berths))

    # 4. 도착시간이 빠른 선박부터 처리
    for v in vessels:
        possible = [
            b for b in berths
            if v["loa_m"] <= b["length_m"]
            and v["q_min"] <= min(v["q_max"], b["q_max"])
        ]

        if not possible:
            raise ValueError(f"{v['id']}: 배정 가능한 선석이 없습니다.")

        # 배정된 선박 수가 가장 적은 선석 선택
        berth = min(
            possible,
            key=lambda b: (len(sequence[b["id"]]), b["id"])
        )

        # 허용 범위 내에서 크레인 수 결정
        q_max = min(v["q_max"], berth["q_max"])
        q = max(v["q_min"], min(q_base, q_max))

        sequence[berth["id"]].append(v["id"])
        cranes[v["id"]] = q

    return {
        "sequence": sequence,
        "cranes": cranes
    }

