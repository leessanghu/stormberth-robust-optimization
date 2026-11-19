# 1. 태풍 영향 정량화

태풍 트랙에서 **IKE(통합운동에너지)**와 **항만별 노출시간**을 계산합니다.
제안서 §5 Step 1에 해당하며, 결과는 2단계 robust 스케줄링의 시나리오 입력이 됩니다.

---

## IKE가 뭔가

최대풍속만으로는 태풍의 파괴력을 설명할 수 없습니다. 같은 등급이라도 바람이 넓게 퍼지면
피해가 훨씬 큽니다. Powell & Reinhold(2007)는 **풍속장 전체를 적분한 운동에너지**를 제안했습니다.

```
IKE = ∫ ½ ρ U² dV
```

ρ는 공기밀도, U는 풍속, V는 영향 영역입니다.

### 구현 방법

격자 바람장이 없으므로, IBTrACS가 주는 **4분면별 풍속반경**으로 동심 고리를 만들어 근사합니다.

```
       NW │ NE          각 분면마다 34 / 50 / 64 kt 반경이 주어짐
      ────┼────         → 고리 3개 (34–50, 50–64, 64–Vmax)
       SW │ SE          → 고리마다 대표풍속 × 면적 × 두께로 에너지 합산
```

고리 하나의 기여:

```python
area = (π/4) × (r_out² − r_in²)        # 4분면이므로 π/4
U    = √((lo² + hi²)/2)                # 에너지 평균이라 제곱평균
IKE += ½ × ρ × U² × area × 1m          # 표층 1m 두께 가정
```

4분면 × 3고리 = 12개를 합쳐 시점별 IKE(TJ)를 얻고, 태풍 전체는 그 최댓값을 씁니다.

### 노출시간(exposure)

IKE는 **태풍 자체의 크기**지 특정 항만이 받은 충격이 아닙니다.
경로가 멀면 IKE가 커도 영향이 없죠. 그래서 항만별로 따로 계산합니다.

각 트랙 시점마다 태풍 중심에서 항만까지의 **거리와 방위각**을 구하고,
그 방위가 속한 분면의 풍속반경과 비교해 어느 고리 안에 있는지 판정합니다.
그 지속시간을 누적한 것이 `hours_r34 / r50 / r64`입니다.

> **34kt(약 17 m/s)가 중요한 이유**: 컨테이너 크레인은 보통 15~20 m/s에서 작업을 멈춥니다.
> 즉 `hours_r34`는 "크레인이 멈췄을 시간"의 대리지표입니다.

---

## 파일

```
scripts/
  download_ibtracs.sh   IBTrACS 내려받기 (110MB, git에 없음)
  ike_exposure.py       IKE + 한국 항만 노출 계산
  asia_ports_def.py     항만 좌표 23개 (단일 출처)
  asia_ports.py         아시아 항만 태풍별 노출 집계
  exposure_daily.py     항만×날짜 노출 패널            ← 패널 분석 입력
data/
  ibtracs.WP.list.v04r01.csv   원본 (gitignore)
output/
  storms.csv                   태풍별 IKE·최대풍속·부산 최근접거리
  port_exposure.csv            태풍 × 항만 노출시간  ← 가장 많이 쓰는 파일
  asia_port_exposure.csv       2023년 이후 아시아 23개 항만
  event_study_design.csv       이벤트 스터디 설계 (처치/대조 구분)
  busan_collection_windows.csv 부산 19개 에피소드의 수집 윈도우
```

## 실행

```bash
bash 1-typhoon/scripts/download_ibtracs.sh
python 1-typhoon/scripts/ike_exposure.py \
       1-typhoon/data/ibtracs.WP.list.v04r01.csv \
       1-typhoon/output/storms.csv 1-typhoon/output/port_exposure.csv
python 1-typhoon/scripts/asia_ports.py
```

## 주요 결과

2000년 이후 **부산이 34kt 바람권에 든 태풍 27개**. 상위권이 실제 피해 사례와 일치합니다.

| 태풍 | 연도 | 노출 34kt | IKE(TJ) | 최근접 |
|---|---|---|---|---|
| TAPAH 타파 | 2019 | 24h | 399 | 140km |
| NANMADOL 난마돌 | 2022 | 18h | 235 | 210km |
| HINNAMNOR 힌남노 | 2022 | 12h | 190 | 132km |
| MAEMI 매미 | 2003 | 12h | 72 | 71km |

아시아로 넓히면 **가오슝(대만)이 압도적**입니다 — 4년간 14회, 390시간.
부산은 20년에 27회이니 밀도가 7배쯤 됩니다.

---

## 알아둘 것

**결측의 대부분은 구조적 0입니다.** `USA_R34`가 비어 있는 502개 시점 중 진짜 누락은 31개(2.5%)뿐이고,
나머지는 태풍이 34kt에 못 미쳤거나 온대저기압으로 전이된 단계입니다. 0으로 처리하는 게 맞습니다.
27개 이벤트 전부 최근접 시각 ±12h에 반경 자료가 있습니다.

**다른 기관 컬럼은 쓰기 어렵습니다.** IBTrACS에는 일본(TOKYO)·한국(KMA) 컬럼도 있지만,
장축/단축 타원 형식이라 동심 고리 근사에 바로 안 맞고, **KMA는 2015년부터만 존재**합니다.

**34kt 기준은 다소 엄격합니다.** 2021년 오마이스·찬투는 이 기준을 통과하지 못했지만
실제로 부산항을 멈췄습니다([findings](../docs/findings.md) 참조). 처치 정의를 넓힐 여지가 있습니다.
