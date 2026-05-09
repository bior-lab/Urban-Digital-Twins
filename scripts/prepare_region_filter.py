"""Convert Singapore administrative district polygons to website GeoJSON."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import geopandas as gpd


SURVEY_RE = re.compile(r"<th>SURVEY_DISTRICT</th>\s*<td>([^<]+)</td>", re.IGNORECASE)


def natural_key(value: str):
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", value)]


def extract_region_id(description: str, fallback: str) -> str:
    match = SURVEY_RE.search(description or "")
    return match.group(1).strip() if match else fallback


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shp", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    gdf = gpd.read_file(args.shp)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")

    records = []
    for row in gdf.itertuples(index=False):
        props = row._asdict()
        geometry = props.pop("geometry")
        region_id = extract_region_id(str(props.get("Descriptio", "")), str(props.get("Name", "")))
        records.append(
            {
                "type": "Feature",
                "properties": {
                    "region_id": region_id,
                    "region_name": region_id,
                },
                "geometry": json.loads(gpd.GeoSeries([geometry], crs=gdf.crs).to_json())["features"][0]["geometry"],
            }
        )

    records.sort(key=lambda feature: natural_key(feature["properties"]["region_id"]))
    feature_collection = {"type": "FeatureCollection", "features": records}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(feature_collection, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "features": len(records)}, indent=2))


if __name__ == "__main__":
    main()
