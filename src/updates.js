export const RELEASES_API_URL = "https://api.github.com/repos/LLYYXX/my-sticky-notes/releases/latest";
const PROJECT_RELEASE_PREFIX = "/LLYYXX/my-sticky-notes/releases/";
const MAX_RESPONSE_BYTES = 1_000_000;

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
  const payload = await response.json();
  const latestVersion = normalizeVersion(payload?.tag_name);
  const releaseUrl = validateReleaseUrl(payload?.html_url);
  return {
    latestVersion,
    releaseUrl,
    updateAvailable: compareVersions(latestVersion, currentVersion) > 0,
  };
}

export function compareVersions(candidate, current) {
  const left = parseVersion(candidate);
  const right = parseVersion(current);
  for (let index = 0; index < 3; index += 1) {
    if (left[index] !== right[index]) return left[index] > right[index] ? 1 : -1;
  }
  if (left[3] !== right[3]) return left[3] > right[3] ? 1 : -1;
  return 0;
}

export function normalizeVersion(value) {
  const match = /^v?(\d+)\.(\d+)\.(\d+)([-+][0-9A-Za-z.-]+)?$/.exec(String(value || "").trim());
  if (!match) throw new Error("invalid release version");
  return `${match[1]}.${match[2]}.${match[3]}${match[4] || ""}`;
}

function parseVersion(value) {
  const normalized = normalizeVersion(value);
  const match = /^(\d+)\.(\d+)\.(\d+)([-+].+)?$/.exec(normalized);
  return [Number(match[1]), Number(match[2]), Number(match[3]), match[4] ? 0 : 1];
}

function validateReleaseUrl(value) {
  const url = new URL(String(value || ""));
  if (
    url.protocol !== "https:"
    || url.hostname.toLowerCase() !== "github.com"
    || !url.pathname.startsWith(PROJECT_RELEASE_PREFIX)
  ) {
    throw new Error("invalid release URL");
  }
  return url.toString();
}
