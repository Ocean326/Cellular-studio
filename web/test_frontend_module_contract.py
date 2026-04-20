from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path


CORE_JS_PATH = Path(__file__).resolve().parent / "app" / "features" / "studio_admin" / "studio_management_core.js"


@unittest.skipUnless(shutil.which("node"), "node is required for frontend module contract checks")
class FrontendModuleContractTest(unittest.TestCase):
	def test_studio_management_core_exports_runtime_contract(self) -> None:
		node_script = f"""
const path = {json.dumps(str(CORE_JS_PATH))};
global.window = globalThis;
global.TrajectoryStudioModules = {{}};
require(path);
const core = global.TrajectoryStudioModules.studioAdminCore;
if (!core) throw new Error("missing studioAdminCore export");
const required = [
  "getFormatSpec",
  "buildHelpHtml",
  "getStatusClass",
  "resolveActor",
  "normalizeUpload",
  "parseRawPayload",
  "createUploadRecord",
  "fetchActor",
  "fetchUploads",
  "uploadBlob"
];
for (const name of required) {{
  if (typeof core[name] !== "function") throw new Error(`missing runtime function: ${{name}}`);
}}
const signalSpec = core.getFormatSpec("signal6");
if (!signalSpec.rules.some(rule => rule.includes("北京范围"))) {{
  throw new Error("signal6 format spec lost Beijing validation rule");
}}
if (!signalSpec.rules.some(rule => rule.includes("proceduereEndTime"))) {{
  throw new Error("signal6 format spec lost expanded time alias guidance");
}}
if (!signalSpec.fields.some(field => field.key === "t_in")) {{
  throw new Error("signal6 format spec lost canonical t_in field key");
}}
const normalized = core.normalizeUpload(
  {{
    upload_id: "upload-demo",
    status: "published",
    visibility_scope: "public",
    annotation_mode: "annotatable",
    display_name: "Demo Upload",
    original_name: "demo.csv",
    size_bytes: 128,
  }},
  {{
    formatVisibilityScope: value => `v:${{value}}`,
    formatAnnotationMode: value => `a:${{value}}`,
  }}
);
if (normalized.uploadId !== "upload-demo") throw new Error("normalizeUpload lost upload id");
if (normalized.statusClass !== "status-published") throw new Error("normalizeUpload lost status class");
if (normalized.visibilityLabel !== "v:public") throw new Error("normalizeUpload lost visibility formatter");
if (normalized.annotationModeLabel !== "a:annotatable") throw new Error("normalizeUpload lost annotation formatter");
const parsed = core.parseRawPayload("not-json");
if (parsed.raw !== "not-json") throw new Error("parseRawPayload fallback changed unexpectedly");
const helpHtml = core.buildHelpHtml(core.getFormatSpec("trajectory4"));
if (!helpHtml.includes("Format Guide")) throw new Error("help renderer lost shell title");
if (!helpHtml.includes("多个 uid")) throw new Error("help renderer lost trajectory guidance");
if (!core.buildHelpHtml(signalSpec).includes("兼容头")) throw new Error("help renderer lost alias chip section");
console.log(JSON.stringify({{ ok: true, ruleCount: signalSpec.rules.length }}));
"""
		result = subprocess.run(
			["node", "-e", node_script],
			check=True,
			capture_output=True,
			text=True,
		)
		payload = json.loads(result.stdout.strip())
		self.assertTrue(payload["ok"])
		self.assertGreaterEqual(payload["ruleCount"], 3)


if __name__ == "__main__":
	unittest.main()
