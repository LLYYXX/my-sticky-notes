import assert from "assert";
import { checkGithubRelease, compareVersions, normalizeVersion } from "../src/updates.js";

function response(payload, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => null },
    json: async () => payload,
  };
}

assert.equal(normalizeVersion("v0.3.0-alpha.0"), "0.3.0-alpha.0");
assert.equal(compareVersions("0.3.0", "0.3.0-alpha.0"), 1);
assert.equal(compareVersions("0.4.0", "0.3.9"), 1);
assert.equal(compareVersions("0.3.0", "0.3.0"), 0);
assert.equal(compareVersions("0.3.0-beta.1", "0.3.0-alpha.9"), 1);
assert.equal(compareVersions("0.3.0-alpha.10", "0.3.0-alpha.2"), 1);
assert.equal(compareVersions("0.3.0-alpha.2", "0.3.0-alpha.10"), -1);
assert.equal(compareVersions("0.3.0-alpha", "0.3.0-alpha.1"), -1);
assert.equal(compareVersions("0.3.0+build.2", "0.3.0+build.1"), 0);
assert.throws(() => normalizeVersion("0.03.0"), /invalid release version/);

{
  const result = await checkGithubRelease("0.3.0-alpha.0", async () => response({
    tag_name: "v0.3.0",
    html_url: "https://github.com/LLYYXX/my-sticky-notes/releases/tag/v0.3.0",
  }));
  assert.equal(result.updateAvailable, true);
  assert.equal(result.latestVersion, "0.3.0");
}

await assert.rejects(
  () => checkGithubRelease("0.3.0", async () => response({
    tag_name: "v0.4.0",
    html_url: "https://example.invalid/releases/tag/v0.4.0",
  })),
  /invalid release URL/,
);

console.log(JSON.stringify({ result: "passed", tests: 12 }));
