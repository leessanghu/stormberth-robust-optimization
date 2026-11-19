"""IMF PortWatch 일별 항만활동 데이터를 내려받는다 (대상 항만만 필터).

전체 데이터셋은 3.2GB이므로 portid 필터를 걸어 약 10MB로 줄인다.
ArcGIS Hub의 비동기 다운로드 API를 쓰므로 생성 완료까지 수 분 걸린다.

사용:  python 2-port/scripts/download_portwatch.py
"""
import json, time, urllib.parse, urllib.request, pathlib

ITEM_DAILY = "83b1bbc7b3354c5fb1f40673bb8f852e"   # Daily_Ports_Data
ITEM_PORTS = "acc668d199d1472abaaf2467133d4ca4"   # Ports (메타데이터)
OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "portwatch"

# 분석 대상 23개 항만 (한국·일본·대만·중국)
PORTIDS = ["port1065","port1338","port432","port494",            # 부산 울산 광양 인천
           "port541","port238","port1252",                       # 가오슝 지룽 타이중
           "port2040","port528","port439","port1378","port862",  # 나하 가고시마 하카타 기타큐슈 오사카
           "port581","port1305","port1417","port786",            # 고베 도쿄 요코하마 나고야
           "port1188","port2027","port824","port1069",           # 상하이 양산 닝보 칭다오
           "port1404","port1189","port474"]                      # 샤먼 선전 홍콩

def fetch(item, where=None, tries=60, wait=20):
    q = {"redirect": "false", "layers": "0"}
    if where: q["where"] = where
    url = f"https://hub.arcgis.com/api/download/v1/items/{item}/csv?" + urllib.parse.urlencode(q)
    for i in range(tries):
        with urllib.request.urlopen(url, timeout=60) as r:
            d = json.load(r)
        st = d.get("status")
        print(f"  [{i+1}] {st} {d.get('progressInPercent','')}")
        if st == "Completed":
            return d["resultUrl"]
        time.sleep(wait)
    raise RuntimeError("생성 시간 초과")

def save(url, path):
    with urllib.request.urlopen(url, timeout=300) as r, open(path, "wb") as f:
        f.write(r.read())
    print(f"저장: {path} ({path.stat().st_size/1e6:.1f} MB)")

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    print("항만 메타데이터...")
    save(fetch(ITEM_PORTS), OUT / "ports_database.csv")
    print("일별 활동 데이터... (수 분 소요)")
    where = "portid IN (" + ",".join(f"'{p}'" for p in PORTIDS) + ")"
    save(fetch(ITEM_DAILY, where), OUT / "daily_ports.csv")
