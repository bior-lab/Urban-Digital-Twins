const fs = require("fs");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..");
const searchPath = path.join(repoRoot, "data", "search_index.json");
const lczPath = path.join(repoRoot, "data", "lcz_grid_stats.json");
const outputPath = path.join(repoRoot, "data", "building_type_region_counts.json");

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function increment(target, key) {
  if (!key) return;
  target.counts[key] = (target.counts[key] || 0) + 1;
  target.total += 1;
}

function sortObjectByKey(input) {
  return Object.fromEntries(Object.entries(input).sort(([a], [b]) => a.localeCompare(b)));
}

const searchIndex = readJson(searchPath);
const lczStats = readJson(lczPath);

const buildingFields = searchIndex.buildingFields || [];
const buildingTypeIndex = buildingFields.indexOf("building_type");
const buildingGridIndex = buildingFields.indexOf("grid_id");
if (buildingTypeIndex < 0 || buildingGridIndex < 0) {
  throw new Error("search_index.json must include building_type and grid_id fields.");
}

const gridFields = lczStats.grid?.fields || [];
const gridIdIndex = gridFields.indexOf("grid_id");
const regionIdIndex = gridFields.indexOf("region_id");
const regionNameIndex = gridFields.indexOf("region_name");
if (gridIdIndex < 0 || regionIdIndex < 0) {
  throw new Error("lcz_grid_stats.json must include grid_id and region_id fields.");
}

const gridRegion = new Map();
const regionNames = {};
(lczStats.grid?.rows || []).forEach((row) => {
  const gridId = row[gridIdIndex];
  const regionId = String(row[regionIdIndex] || "");
  if (!gridId || !regionId) return;
  gridRegion.set(String(gridId), regionId);
  if (regionNameIndex >= 0 && row[regionNameIndex]) regionNames[regionId] = row[regionNameIndex];
});

const regions = {};
const totalCounts = {};
const missingRegion = { total: 0, counts: {} };

(searchIndex.buildings || []).forEach((row) => {
  const type = String(row[buildingTypeIndex] || "");
  if (!type) return;
  const gridId = row[buildingGridIndex];
  const regionId = gridRegion.get(String(gridId));

  totalCounts[type] = (totalCounts[type] || 0) + 1;
  if (!regionId) {
    increment(missingRegion, type);
    return;
  }
  if (!regions[regionId]) regions[regionId] = { total: 0, counts: {} };
  increment(regions[regionId], type);
});

const sortedRegions = Object.fromEntries(
  Object.entries(regions)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([regionId, record]) => [
      regionId,
      {
        name: regionNames[regionId] || "",
        total: record.total,
        counts: sortObjectByKey(record.counts)
      }
    ])
);

const output = {
  generated_at: new Date().toISOString(),
  source_files: ["data/search_index.json", "data/lcz_grid_stats.json"],
  join_key: "grid_id",
  note:
    "Building type counts are joined from building grid_id to 500 m grid region_id for UI summaries.",
  total: searchIndex.buildings?.length || 0,
  total_counts: sortObjectByKey(totalCounts),
  regions: sortedRegions,
  missing_region: {
    total: missingRegion.total,
    counts: sortObjectByKey(missingRegion.counts)
  }
};

fs.writeFileSync(outputPath, `${JSON.stringify(output)}\n`, "utf8");
console.log(`Wrote ${path.relative(repoRoot, outputPath)} with ${Object.keys(sortedRegions).length} regions.`);
