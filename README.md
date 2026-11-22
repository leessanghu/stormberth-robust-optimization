# Robust Berth & Quay Crane Scheduling for Post-Typhoon Port Recovery

태풍 이후 밀린 선박(backlog)을 가장 빨리 해소하는 **선석·크레인 통합 스케줄링** 연구입니다.
태풍이 항만을 얼마나 오래 멈추는지를 실측해 운영 시나리오를 만들고,
그 시나리오들의 최악 상황에서도 총 체류시간이 크게 늘지 않는 배정을 찾습니다.

제안서: [`proposal/항만최적화_Proposal.pdf`](proposal/)

---

## 지금 어디까지 왔나

```
[1] 태풍 영향 정량화   ████████████  완료
[2] 전제 검증          ████████████  완료 — 19개항 이중차분으로 입증
[3] 최적화 모형        ░░░░░░░░░░░░  수식 확정, 구현 전
```

**핵심 결과**

> 태풍에 노출된 항만은 상륙일 컨테이너 기항이 **−83.7%** 떨어지고,
> 사흘 뒤 **+16.3%** 로 몰립니다. (19개항 × 2,874일 이중차분, 항만FE+날짜FE)

**세기보다 지속시간이 중요합니다.** 잠깐 스친 태풍은 다음 날 바로 정상(+0.6%)이지만,
오래 머문 태풍은 이튿날까지 −74.5%로 끌려갑니다.
가짜 태풍일을 심으면 효과가 사라집니다(플라시보 ±4%).
제안서가 전제한 **정지 → Vessel Bunching** 구조가 데이터로 확인됐습니다.

→ 자세히: [`docs/findings.md`](docs/findings.md)

---

## 폴더 구조

두 갈래로 나뉩니다. 번호 순서가 파이프라인 순서입니다.

| 폴더 | 내용 | 안내 |
|---|---|---|
| [`1-typhoon/`](1-typhoon/) | **태풍 쪽** — 항만이 강풍에 노출된 시간 계산 | [README](1-typhoon/README.md) |
| [`2-port/`](2-port/) | **항만 쪽** — 23개항 패널 이중차분으로 태풍 전후 병목 추정 | [README](2-port/README.md) |
| [`3-model/`](3-model/) | **모형 쪽** — 선석·크레인 배정 최적화 (구현 중) | [README](3-model/README.md) |
| [`docs/`](docs/) | 결과 요약, 수집 명세 | [findings](docs/findings.md) |
| [`proposal/`](proposal/) | 제안서 PDF | |

1·2단계 폴더는 `scripts/`(코드) · `data/`(원본) · `output/`(결과 CSV)로 같은 모양입니다.

---

## 빠르게 돌려보기

```bash
# 1. 환경
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. 큰 원본 2개 받기 (git에 없음)
bash 1-typhoon/scripts/download_ibtracs.sh      # 약 110MB, 1분
python 2-port/scripts/download_portwatch.py     # 약 10MB, 수 분

# 3. 분석 (저장소 루트에서 실행)
python 1-typhoon/scripts/exposure_daily.py      # 항만×날짜 노출 패널
python 2-port/scripts/panel_build.py            # 패널 결합
python 2-port/scripts/panel_did.py              # 이중차분     ← 주 결과
```

> 모든 스크립트는 **저장소 루트에서** 실행합니다. 경로가 루트 기준으로 쓰여 있습니다.

---

## 데이터 출처

| 데이터 | 출처 | 가입 | git 포함 |
|---|---|---|---|
| 태풍 베스트트랙 | [IBTrACS v04r01 (NOAA)](https://www.ncei.noaa.gov/products/international-best-track-archive) | 불필요 | ✗ 110MB |
| 일별 항만활동 | [IMF PortWatch](https://portwatch.imf.org) | 불필요 | ✗ 스크립트로 |
| ~~울산 선석배정~~ | [공공데이터포털 15121258](https://www.data.go.kr/data/15121258/fileData.do) | 불필요 | ✗ 사용 중단 |

수집하려다 막힌 경로와 그 이유는 [`docs/collection-spec.md`](docs/collection-spec.md)에 정리돼 있습니다.
**BPA 본선작업현황 API는 폐기됐고, PORT-MIS는 2년치만 조회됩니다.** 같은 길을 다시 파지 마세요.

---

## 팀원에게

- **모형을 구현하려면 → [`3-model/START.md`](3-model/START.md)**
- 결과만 보고 싶으면 → [`docs/findings.md`](docs/findings.md)
- 태풍 지표를 고치고 싶으면 → [`1-typhoon/README.md`](1-typhoon/README.md)
- 항만 분석을 늘리고 싶으면 → [`2-port/README.md`](2-port/README.md)
- 데이터를 더 모아야 하면 → [`docs/collection-spec.md`](docs/collection-spec.md)

이슈나 질문은 GitHub Issues에 남겨주세요.
