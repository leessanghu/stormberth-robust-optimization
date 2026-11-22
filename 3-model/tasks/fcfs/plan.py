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
    raise NotImplementedError
