#!/usr/bin/env python3
"""브이월드에서 드론 비행구역 GeoJSON을 내려받아 data/ 폴더에 저장합니다.

사용법:
    set VWORLD_KEY=발급받은_키                    (PowerShell: $env:VWORLD_KEY="...")
    python scripts/download_data.py               # 없는 파일만 받기
    python scripts/download_data.py --force       # 전부 다시 받기
    python scripts/download_data.py --probe       # 데이터셋 ID가 실제로 응답하는지만 점검 (저장 안 함)
    python scripts/download_data.py --only ua,temp --force   # 지정한 레이어만

* 필수 레이어(행정계/금지/제한/관제권)는 실패하면 오류로 종료합니다.
* 선택 레이어는 실패해도 건너뛰고 계속 진행합니다 (해당 ID가 브이월드 데이터API에 없을 수 있음).
* 키는 코드에 적지 말고 환경변수(또는 --key)로만 넘기세요.
"""
import argparse
import json
import os
import sys
import time

import requests

API_URL = "https://api.vworld.kr/req/data"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

# (저장 이름, 브이월드 데이터셋 ID, 표시 이름, 필수 여부)
LAYERS = [
    ("sigg",       "LT_C_ADSIGG_INFO",  "시/군/구 행정계",        True),
    ("airspace",   "LT_C_AISPRHC",      "비행금지구역",           True),
    ("restricted", "LT_C_AISRESC",      "비행제한구역",           True),
    ("controlled", "LT_C_AISCTRC",      "관제권",                 True),
    # 아래는 선택 레이어 (있으면 지도에 자동으로 나타납니다)
    ("ua",         "LT_C_AISUAC",       "초경량비행장치 허용공역", False),
    ("atz",        "LT_C_AISATZC",      "비행장교통구역",         False),
    ("danger",     "LT_C_AISDNGC",      "위험구역",               False),
    ("acm",        "LT_C_AISACMC",      "공중전투기동훈련장",     False),
    ("temp",       "LT_C_AISTEMP",      "임시비행금지구역",       False),
    ("dronezone",  "LT_C_AISDRONEZONE", "드론시범사업구역",       False),
]


def round_coords(obj, ndigits=5):
    """좌표를 소수점 5자리(약 1m)로 줄여 파일 크기를 절약합니다."""
    if isinstance(obj, list):
        if obj and isinstance(obj[0], (int, float)):
            return [round(v, ndigits) for v in obj]
        return [round_coords(o, ndigits) for o in obj]
    return obj


def request_page(dataset, key, domain, bbox, page, size):
    params = {
        "service": "data", "request": "GetFeature", "data": dataset,
        "key": key, "domain": domain, "format": "json", "errorformat": "json",
        "size": size, "page": page, "crs": "EPSG:4326",
        "geomFilter": f"BOX({bbox})",
    }
    for attempt in range(3):
        try:
            r = requests.get(API_URL, params=params, timeout=60, headers={"Referer": domain})
            r.raise_for_status()
            return r.json().get("response", {})
        except (requests.RequestException, ValueError) as e:
            if attempt == 2:
                raise
            print(f"   재시도 중... ({e})")
            time.sleep(2)


def fetch_all(dataset, key, domain, bbox, size=1000):
    features, page = [], 1
    while True:
        resp = request_page(dataset, key, domain, bbox, page, size)
        status = resp.get("status")
        if status == "NOT_FOUND":
            break
        if status != "OK":
            raise RuntimeError(f"API 오류: {resp.get('error') or resp}")
        fc = resp["result"]["featureCollection"]
        features.extend(fc.get("features", []))
        total_pages = int(resp.get("page", {}).get("total", 1))
        print(f"   {page}/{total_pages} 페이지 (누적 {len(features)}건)")
        if page >= total_pages:
            break
        page += 1

    for f in features:
        if f.get("geometry"):
            f["geometry"]["coordinates"] = round_coords(f["geometry"]["coordinates"])
    return {"type": "FeatureCollection", "features": features}


def probe(name, dataset, label, key, domain, bbox):
    try:
        resp = request_page(dataset, key, domain, bbox, 1, 1)
    except Exception as e:
        print(f"❌ {name:<11} {dataset:<20} {label} → 요청 실패: {e}")
        return False
    status = resp.get("status")
    if status == "OK":
        feats = resp["result"]["featureCollection"].get("features", [])
        props = sorted((feats[0].get("properties") or {}).keys()) if feats else []
        total = resp.get("record", {}).get("total", "?")
        print(f"✅ {name:<11} {dataset:<20} {label} → 응답 OK (전체 약 {total}건)")
        print(f"      속성: {', '.join(props)}")
        return True
    if status == "NOT_FOUND":
        print(f"⚠️  {name:<11} {dataset:<20} {label} → 데이터셋은 있으나 해당 범위에 데이터 없음")
        return True
    print(f"❌ {name:<11} {dataset:<20} {label} → {resp.get('error') or resp}")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default=os.environ.get("VWORLD_KEY"), help="브이월드 API 키")
    ap.add_argument("--domain", default=os.environ.get("VWORLD_DOMAIN", "http://localhost:8000"),
                    help="키 발급 시 등록한 도메인 (기본 http://localhost:8000)")
    ap.add_argument("--bbox", default="124.0,33.0,132.0,39.0", help="minx,miny,maxx,maxy")
    ap.add_argument("--force", action="store_true", help="이미 있는 파일도 다시 받기")
    ap.add_argument("--probe", action="store_true", help="데이터셋 응답 여부만 점검(저장 안 함)")
    ap.add_argument("--only", default="", help="쉼표로 구분한 레이어 이름만 처리 (예: ua,temp)")
    args = ap.parse_args()

    if not args.key:
        sys.exit("VWORLD_KEY 환경변수를 설정하거나 --key 로 키를 넘겨주세요.")

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    targets = [l for l in LAYERS if not only or l[0] in only]
    if not targets:
        sys.exit("--only 에 알 수 없는 이름이 있어요. 사용 가능: " + ", ".join(l[0] for l in LAYERS))

    if args.probe:
        for name, dataset, label, _ in targets:
            probe(name, dataset, label, args.key, args.domain, args.bbox)
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    failed_required, failed_optional = [], []
    for name, dataset, label, required in targets:
        filename = "airspace.geojson" if name == "airspace" else f"{name}.geojson"
        path = os.path.join(DATA_DIR, filename)
        if os.path.exists(path) and not args.force:
            print(f"✅ {filename} 이미 있음 (다시 받으려면 --force)")
            continue
        print(f"⬇️  {filename} ({dataset} · {label})")
        try:
            fc = fetch_all(dataset, args.key, args.domain, args.bbox)
            if not fc["features"] and not required:
                print(f"⚠️  {filename}: 데이터 0건이라 저장하지 않았어요")
                failed_optional.append(filename)
                continue
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(fc, f, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, path)          # 실패해도 깨진 파일이 남지 않게
            print(f"✅ {filename} 저장 완료 ({len(fc['features'])}건)")
        except Exception as e:
            print(f"{'❌' if required else '⚠️ '} {filename} 실패: {e}")
            (failed_required if required else failed_optional).append(filename)

    if failed_optional:
        print(f"\n건너뛴 선택 레이어: {', '.join(failed_optional)}")
        print("→ `--probe` 로 데이터셋 ID가 응답하는지 확인해 보세요.")
    if failed_required:
        sys.exit(f"\n필수 레이어 실패: {', '.join(failed_required)}")
    print("\n완료! 이제 `python -m http.server 8000` 으로 확인하세요.")


if __name__ == "__main__":
    main()
