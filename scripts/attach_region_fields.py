"""Attach Singapore planning-area attributes to building GeoJSON features."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd


REGION_COLUMNS = ["region_id", "region_name", "region_group", "region_group_code"]


def load_geojson(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_geojson(data, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def region_mapping(buildings_path: Path, regions_path: Path) -> dict[int, dict[str, str]]:
    buildings = gpd.read_file(buildings_path)
    regions = gpd.read_file(regions_path)

    if buildings.crs is None:
        buildings = buildings.set_crs("EPSG:4326")
    elif buildings.crs.to_epsg() != 4326:
        buildings = buildings.to_crs("EPSG:4326")

    if regions.crs is None:
        regions = regions.set_crs("EPSG:4326")
    elif regions.crs.to_epsg() != 4326:
        regions = regions.to_crs("EPSG:4326")

    points = buildings[["objectid", "geometry"]].copy()
    points["geometry"] = points.geometry.representative_point()
    joined = gpd.sjoin(
        points,
        regions[REGION_COLUMNS + ["geometry"]],
        how="left",
        predicate="within",
    )

    mapping: dict[int, dict[str, str]] = {}
    for row in joined.itertuples(index=False):
        if row.region_id is None:
            continue
        mapping[int(row.objectid)] = {
            "planning_area_code": str(row.region_id),
            "planning_area_name": str(row.region_name),
            "major_region": str(row.region_group),
            "major_region_code": str(row.region_group_code),
        }
    return mapping


def attach_fields(buildings, mapping: dict[int, dict[str, str]]) -> int:
    missing = 0
    for feature in buildings.get("features", []):
        props = feature.setdefault("properties", {})
        object_id = props.get("objectid")
        region_props = mapping.get(int(object_id)) if object_id is not None else None
        if not region_props:
            missing += 1
            props["planning_area_code"] = None
            props["planning_area_name"] = None
            props["major_region"] = None
            props["major_region_code"] = None
            continue
        props.update(region_props)
    return missing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--buildings", required=True, type=Path)
    parser.add_argument("--regions", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    mapping = region_mapping(args.buildings, args.regions)
    buildings = load_geojson(args.buildings)
    missing = attach_fields(buildings, mapping)
    dump_geojson(buildings, args.out)

    print(
        json.dumps(
            {
                "building_features": len(buildings.get("features", [])),
                "matched_buildings": len(mapping),
                "missing_buildings": missing,
                "out": str(args.out),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
