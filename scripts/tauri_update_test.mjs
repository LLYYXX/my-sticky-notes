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
  const result = await checkGithubRelease("0.3.0-alpha.0", async () => response([
    { tag_name: "v0.2.3", assets: [{ name: "My Sticky Notes_0.2.3_x64-setup.exe" }] },
    { tag_name: "v0.3.0-alpha.1", assets: [{ name: "My Sticky Notes_0.3.0-alpha.1_x64-setup.exe" }] },
    { draft: true, tag_name: "v9.0.0", assets: [{ name: "My Sticky Notes_9.0.0_x64-setup.exe" }] },
  ]));
  assert.equal(result.updateAvailable, true);
  assert.equal(result.latestVersion, "0.3.0-alpha.1");
  assert.equal(result.releaseTag, "v0.3.0-alpha.1");
  assert.deepEqual(result.assetNames, ["My Sticky Notes_0.3.0-alpha.1_x64-setup.exe"]);
}

await assert.rejects(
  () => checkGithubRelease("0.3.0", async () => response([
    { tag_name: "v0.4.0", assets: "not-an-asset-list" },
  ])),
  /invalid release assets/,
);

await assert.rejects(
  () => checkGithubRelease("0.3.0", async () => response([])),
  /no published release available/,
);

console.log(JSON.stringify({ result: "passed", tests: 15 }));
