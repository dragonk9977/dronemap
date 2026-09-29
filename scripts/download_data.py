#!/usr/bin/env python3
"""브이월드에서 드론 비행구역 GeoJSON을 내려받아 data/ 폴더에 저장합니다.

사용법:
    export VWORLD_KEY="발급받은_키"          # Windows PowerShell: $env:VWORLD_KEY="..."
    python scripts/download_data.py           # 없는 파일만 받기
    python scripts/download_data.py --force   # 전부 다시 받기

키는 코드에 적지 말고 환경변수(또는 --key)로만 넘기세요.
"""
import argparse
import json
import os
import sys
import time

import requests

API_URL = "https://api.vworld.kr/req/data"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

LAYERS = {
    "sigg.geojson": "LT_C_ADSIGG_INFO",        # 시/군/구 행정계
    "airspace.geojson": "LT_C_AISPRHC",        # 비행금지구역
    "restricted.geojson": "LT_C_AISRESC",      # 비행제한구역
    "controlled.geojson": "LT_C_AISCTRC",      # 관제권
}


def round_coords(obj, ndigits=5):
    """좌표를 소수점 5자리(약 1m)로 줄여 파일 크기를 절약합니다."""
    if isinstance(obj, list):
        if obj and isinstance(obj[0], (int, float)):
            return [round(v, ndigits) for v in obj]
        return [round_coords(o, ndigits) for o in obj]
    return obj


def fetch_all(dataset, key, domain, bbox, size=1000):
    features, page = [], 1
    while True:
        params = {
            "service": "data", "request": "GetFeature", "data": dataset,
            "key": key, "domain": domain, "format": "json", "errorformat": "json",
            "size": size, "page": page, "crs": "EPSG:4326",
            "geomFilter": f"BOX({bbox})",
        }
        for attempt in range(3):
            try:
                r = requests.get(API_URL, params=params, timeout=60,
                                 headers={"Referer": domain})
                r.raise_for_status()
                resp = r.json().get("response", {})
                break
            except (requests.RequestException, ValueError) as e:
                if attempt == 2:
                    raise
                print(f"   재시도 중... ({e})")
                time.sleep(2)

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default=os.environ.get("VWORLD_KEY"), help="브이월드 API 키")
    ap.add_argument("--domain", default=os.environ.get("VWORLD_DOMAIN", "http://localhost:8000"),
                    help="키 발급 시 등록한 도메인 (기본 http://localhost:8000)")
    ap.add_argument("--bbox", default="124.0,33.0,132.0,39.0", help="minx,miny,maxx,maxy")
    ap.add_argument("--force", action="store_true", help="이미 있는 파일도 다시 받기")
    args = ap.parse_args()

    if not args.key:
        sys.exit("VWORLD_KEY 환경변수를 설정하거나 --key 로 키를 넘겨주세요.")

    os.makedirs(DATA_DIR, exist_ok=True)
    failed = []
    for filename, dataset in LAYERS.items():
        path = os.path.join(DATA_DIR, filename)
        if os.path.exists(path) and not args.force:
            print(f"✅ {filename} 이미 있음 (다시 받으려면 --force)")
            continue
        print(f"⬇️  {filename} ({dataset})")
        try:
            fc = fetch_all(dataset, args.key, args.domain, args.bbox)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(fc, f, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, path)          # 실패해도 깨진 파일이 남지 않게
            print(f"✅ {filename} 저장 완료 ({len(fc['features'])}건)")
        except Exception as e:
            print(f"❌ {filename} 실패: {e}")
            failed.append(filename)

    if failed:
        sys.exit(f"\n실패한 파일: {', '.join(failed)}")
    print("\n모두 완료! 이제 `python -m http.server 8000` 으로 확인하세요.")


if __name__ == "__main__":
    main()
