export const RELEASES_API_URL = "https://api.github.com/repos/LLYYXX/my-sticky-notes/releases?per_page=20";
const MAX_RESPONSE_BYTES = 1_000_000;
const MAX_RELEASE_ASSETS = 50;
const VERSION_PATTERN = /^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$/;

export async function checkGithubRelease(currentVersion, fetchImpl = globalThis.fetch) {
  if (typeof fetchImpl !== "function") throw new Error("fetch is unavailable");
  const response = await fetchImpl(RELEASES_API_URL, {
    headers: {
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });
  if (!response?.ok) throw new Error(`release lookup failed: ${response?.status ?? "network"}`);
  const contentLength = Number(response.headers?.get?.("content-length") || 0);
  if (Number.isFinite(contentLength) && contentLength > MAX_RESPONSE_BYTES) {
    throw new Error("release response is too large");
  }
  const release = selectNewestRelease(await response.json());
  const releaseTag = String(release.tag_name || "").trim();
  const latestVersion = normalizeVersion(releaseTag);
  return {
    latestVersion,
    releaseTag,
    assetNames: normalizeReleaseAssets(release.assets),
    updateAvailable: compareVersions(latestVersion, currentVersion) > 0,
  };
}

function selectNewestRelease(value) {
  if (!Array.isArray(value)) throw new Error("invalid release list");
  const candidates = value
    .filter((release) => release && release.draft !== true)
    .flatMap((release) => {
      try {
        return [{ release, version: normalizeVersion(release.tag_name) }];
      } catch {
        return [];
      }
    });
  if (!candidates.length) throw new Error("no published release available");
  return candidates.reduce((newest, candidate) => (
    compareVersions(candidate.version, newest.version) > 0 ? candidate : newest
  )).release;
}

function normalizeReleaseAssets(value) {
  if (!Array.isArray(value) || value.length > MAX_RELEASE_ASSETS) {
    throw new Error("invalid release assets");
  }
  return value
    .map((asset) => String(asset?.name || "").trim())
    .filter(Boolean);
}

export function compareVersions(candidate, current) {
  const left = parseVersion(candidate);
  const right = parseVersion(current);
  for (let index = 0; index < 3; index += 1) {
    if (left.core[index] !== right.core[index]) return left.core[index] > right.core[index] ? 1 : -1;
  }
  return comparePrereleases(left.prerelease, right.prerelease);
}

export function normalizeVersion(value) {
  const match = VERSION_PATTERN.exec(String(value || "").trim());
  if (!match) throw new Error("invalid release version");
  return `${match[1]}.${match[2]}.${match[3]}${match[4] ? `-${match[4]}` : ""}${match[5] ? `+${match[5]}` : ""}`;
}

function parseVersion(value) {
  const match = VERSION_PATTERN.exec(normalizeVersion(value));
  return {
    core: [Number(match[1]), Number(match[2]), Number(match[3])],
    prerelease: match[4]?.split(".") || [],
  };
}

function comparePrereleases(left, right) {
  if (!left.length || !right.length) {
    if (left.length === right.length) return 0;
    return left.length ? -1 : 1;
  }
  const length = Math.min(left.length, right.length);
  for (let index = 0; index < length; index += 1) {
    const comparison = comparePrereleaseIdentifier(left[index], right[index]);
    if (comparison) return comparison;
  }
  return left.length === right.length ? 0 : (left.length > right.length ? 1 : -1);
}

function comparePrereleaseIdentifier(left, right) {
  if (left === right) return 0;
  const leftNumeric = /^\d+$/.test(left);
  const rightNumeric = /^\d+$/.test(right);
  if (leftNumeric && rightNumeric) return Number(left) > Number(right) ? 1 : -1;
  if (leftNumeric !== rightNumeric) return leftNumeric ? -1 : 1;
  return left > right ? 1 : -1;
}
