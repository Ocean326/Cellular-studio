"""为 data/result 生成 manifest.json（含预计算状态标签），供前端读取 UID 列表并加速筛选。"""
import json
from pathlib import Path

from pipeline_utils.utils import compute_manifest_states_for_uid


def main():
	base = Path(__file__).resolve().parent.parent
	result_dir = base / "data" / "result"
	od_dir = base / "data" / "OD"
	if not result_dir.exists():
		print("data/result 不存在")
		return
	uids = sorted(p.name for p in result_dir.iterdir() if p.is_dir())
	states_map = {}
	for uid in uids:
		states_map[uid] = compute_manifest_states_for_uid(result_dir / uid, od_dir)
	manifest = {
		"uids": uids,
		"layers": ["raw", "snap", "od", "fmm", "line"],
		"states": states_map,
	}
	out = result_dir / "manifest.json"
	with open(out, "w", encoding="utf-8") as f:
		json.dump(manifest, f, indent=2, ensure_ascii=False)
	states_out = result_dir / "states_index.json"
	with open(states_out, "w", encoding="utf-8") as f:
		json.dump(states_map, f, ensure_ascii=False)
	print(f"Saved {out} and {states_out} with {len(uids)} uids and states index")


if __name__ == "__main__":
	main()
