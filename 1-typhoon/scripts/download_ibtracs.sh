#!/usr/bin/env bash
# IBTrACS 서태평양(WP) 베스트트랙을 내려받는다. 약 110MB, 가입 불필요.
# 파일이 커서 git에 올리지 않으므로 각자 한 번 실행한다.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=data/ibtracs.WP.list.v04r01.csv
URL="https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.WP.list.v04r01.csv"
mkdir -p data
if [ -f "$OUT" ]; then echo "이미 있음: $OUT"; exit 0; fi
echo "내려받는 중... (약 110MB)"
curl -# -o "$OUT" "$URL"
echo "완료: $OUT  ($(wc -l < "$OUT") 행)"
