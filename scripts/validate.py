"""Check the published skill index, local links, Python syntax and calibration data."""
from pathlib import Path
import json
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def validate():
    index = json.loads((ROOT / "skill-index.json").read_text("utf-8"))
    entries = index["skills"]
    paths = set()
    names = set()
    for entry in entries:
        name = entry["name"]
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name), name
        assert name not in names, f"Duplicate skill name: {name}"
        names.add(name)
        folder = (ROOT / entry["path"]).resolve()
        assert folder.is_relative_to(ROOT / "skills"), folder
        assert folder.name == name and folder.parent.name == entry["category"], folder
        skill = folder / "SKILL.md"
        paths.add(skill)
        text = skill.read_text("utf-8")
        assert text.startswith("---\n"), skill
        front = text.split("---", 2)[1]
        assert re.search(rf"^name: {re.escape(name)}$", front, re.MULTILINE), skill
        assert re.search(r"^description: .+", front, re.MULTILINE), skill
    assert paths == {p.resolve() for p in (ROOT / "skills").rglob("SKILL.md")}, "Index differs from actual skills"

    python_count = 0
    json_count = 0
    link_count = 0
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in {".git", "outputs", "dist", "__pycache__"}
                                     for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix == ".py":
            compile(path.read_bytes(), str(path), "exec")
            python_count += 1
        elif path.suffix == ".json":
            json.loads(path.read_text("utf-8"))
            json_count += 1
        elif path.suffix == ".md":
            text = path.read_text("utf-8")
            for target in re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", text):
                target = target.strip("<>")
                if urlsplit(target).scheme or target.startswith("#"):
                    continue
                relative = unquote(target.split("#", 1)[0])
                resolved = (path.parent / relative).resolve()
                assert resolved.is_relative_to(ROOT) and resolved.exists(), f"Broken local link: {path}: {target}"
                link_count += 1

    assets = ROOT / "skills/retargeting/blender-man-girl-transfer/assets"
    profile = json.loads((assets / "man_girl_profile.json").read_text("utf-8"))
    mapping = json.loads((assets / "bone_mapping.json").read_text("utf-8"))["mapping"]
    assert len(mapping) == 164, f"Expected 164 mappings, got {len(mapping)}"
    assert len(set(mapping.values())) == len(mapping), "Duplicate mapping target"
    for side in ("source", "target"):
        bones = profile[side]
        assert len(bones) == 423, f"Unexpected {side} bone count"
        for bone, data in bones.items():
            assert data["parent"] is None or data["parent"] in bones, (side, bone)
            assert data["length"] > 0, (side, bone)
            assert len(data["matrix"]) == 4 and all(len(row) == 4 for row in data["matrix"]), (side, bone)
    assert set(mapping).issubset(profile["source"]), "Missing mapped source bone"
    assert set(mapping.values()).issubset(profile["target"]), "Missing mapped target bone"
    result = dict(skills=len(entries), categories=len({e["category"] for e in entries}),
                  python_files=python_count, json_files=json_count,
                  local_links=link_count, mapping_pairs=len(mapping),
                  profile_bones={side: len(profile[side]) for side in ("source", "target")})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    validate()
