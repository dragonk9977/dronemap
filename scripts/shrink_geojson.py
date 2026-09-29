#!/usr/bin/env python3
"""GeoJSON 좌표를 솎아내서 파일 크기를 줄입니다 (행정계처럼 '보기용' 레이어에 적합).

사용법:
    python scripts/shrink_geojson.py data/sigg.geojson
    python scripts/shrink_geojson.py data/sigg.geojson --tol 0.0005   # 더 많이 줄이기

기본 tol=0.0003 (약 30m). 이보다 가까운 연속 좌표는 하나로 합쳐요.
원본이 필요하면 download_data.py --force 로 다시 받으면 됩니다.
"""
import argparse
import json
import os


def decimate_ring(ring, tol, min_points):
    if len(ring) <= min_points:
        return ring
    kept = [ring[0]]
    for pt in ring[1:-1]:
        if abs(pt[0] - kept[-1][0]) >= tol or abs(pt[1] - kept[-1][1]) >= tol:
            kept.append(pt)
    kept.append(ring[-1])
    if len(kept) < min_points:      # 너무 작은 링은 원본 유지
        return ring
    return kept


def process_coords(coords, tol, depth):
    # depth: Polygon=링 배열(2) / MultiPolygon=폴리곤 배열(3)
    if depth == 1:
        return decimate_ring(coords, tol, 4)
    return [process_coords(c, tol, depth - 1) for c in coords]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--tol", type=float, default=0.0003)
    args = ap.parse_args()

    before = os.path.getsize(args.path)
    with open(args.path, encoding="utf-8") as f:
        fc = json.load(f)

    for feat in fc.get("features", []):
        g = feat.get("geometry")
        if not g:
            continue
        if g["type"] == "Polygon":
            g["coordinates"] = process_coords(g["coordinates"], args.tol, 2)
        elif g["type"] == "MultiPolygon":
            g["coordinates"] = process_coords(g["coordinates"], args.tol, 3)

    tmp = args.path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, args.path)

    after = os.path.getsize(args.path)
    print(f"{before/1e6:.1f}MB -> {after/1e6:.1f}MB")


if __name__ == "__main__":
    main()
