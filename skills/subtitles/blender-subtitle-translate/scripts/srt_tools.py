"""Extract, assemble and verify aligned SRT translations. Python 3, no dependencies."""
import argparse
import hashlib
import json
import re
from pathlib import Path

TIME = re.compile(r"^(\d{2,}):([0-5]\d):([0-5]\d),(\d{3}) --> (\d{2,}):([0-5]\d):([0-5]\d),(\d{3})(?:[ \t]+\S.*)?$")


def read_srt(path, encoding="utf-8-sig"):
    raw = Path(path).read_bytes()
    text = raw.decode(encoding).lstrip("\ufeff")
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n[ \t]*\n", text.strip("\n"))
    cues = []
    for pos, block in enumerate(blocks, 1):
        lines = block.split("\n")
        if len(lines) < 3 or not re.fullmatch(r"[0-9]+", lines[0]):
            raise ValueError(f"Invalid SRT block at position {pos}")
        match = TIME.fullmatch(lines[1])
        if not match:
            raise ValueError(f"Invalid timecode at position {pos}: {lines[1]}")
        v = [int(n) for n in match.groups()]
        start = ((v[0] * 60 + v[1]) * 60 + v[2]) * 1000 + v[3]
        end = ((v[4] * 60 + v[5]) * 60 + v[6]) * 1000 + v[7]
        source = "\n".join(lines[2:])
        if end <= start or not source.strip():
            raise ValueError(f"Empty text or nonpositive duration at position {pos}")
        cues.append(dict(position=pos, index=lines[0], timing=lines[1], source=source))
    return dict(source_sha256=hashlib.sha256(raw).hexdigest(), cues=cues,
                newline=newline, bom=raw.startswith(b"\xef\xbb\xbf"))


def ensure_new(paths, source):
    targets = [Path(p).resolve() for p in paths]
    if len(set(targets)) != len(targets) or Path(source).resolve() in targets:
        raise ValueError("Output paths must differ from each other and from source")
    for path in targets:
        if path.exists():
            raise ValueError(f"Refusing to overwrite: {path}")


def write_new(path, text, encoding="utf-8"):
    with Path(path).open("x", encoding=encoding, newline="") as stream:
        stream.write(text)


def translation_text(value, pos):
    if not isinstance(value, str):
        raise ValueError(f"Translation must be a string at position {pos}")
    value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not value or any(not line.strip() for line in value.split("\n")):
        raise ValueError(f"Missing translation or blank line at position {pos}")
    return value


def extract(args):
    data = read_srt(args.source, args.encoding)
    ensure_new([args.output], args.source)
    for cue in data["cues"]:
        cue["translation"] = ""
    write_new(args.output, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return {"extracted": len(data["cues"]), "output": args.output}


def build(args):
    data = read_srt(args.source, args.encoding)
    draft = json.loads(Path(args.draft).read_text(encoding="utf-8-sig"))
    if not isinstance(draft, dict) or draft.get("source_sha256") != data["source_sha256"]:
        raise ValueError("Source changed or draft belongs to another file")
    rows = draft.get("cues")
    if not isinstance(rows, list) or len(rows) != len(data["cues"]):
        raise ValueError("Draft cue count differs from source")
    translations, unchanged = [], []
    for original, row in zip(data["cues"], rows):
        if not isinstance(row, dict) or any(row.get(k) != original[k] for k in original):
            raise ValueError(f"Draft alignment changed at position {original['position']}")
        value = translation_text(row.get("translation"), original["position"])
        translations.append(value)
        if value == original["source"]:
            unchanged.append(original["position"])
    ensure_new([args.zh, args.bilingual], args.source)
    zh, bilingual = [], []
    for cue, value in zip(data["cues"], translations):
        prefix = cue["index"] + "\n" + cue["timing"] + "\n"
        zh.append(prefix + value)
        bilingual.append(prefix + value + "\n" + cue["source"])
    encoding = "utf-8-sig" if data["bom"] else "utf-8"
    for path, blocks in [(args.zh, zh), (args.bilingual, bilingual)]:
        result = ("\n\n".join(blocks) + "\n\n").replace("\n", data["newline"])
        write_new(path, result, encoding)
    result = check(args)
    result["unchanged_translation_positions"] = unchanged
    return result


def check(args):
    source = read_srt(args.source, args.encoding)
    zh = read_srt(args.zh)
    bilingual = read_srt(args.bilingual)
    if not (len(source["cues"]) == len(zh["cues"]) == len(bilingual["cues"])):
        raise ValueError("Output cue count differs from source")
    for original, translated, dual in zip(source["cues"], zh["cues"], bilingual["cues"]):
        for item in [translated, dual]:
            if any(item[k] != original[k] for k in ["position", "index", "timing"]):
                raise ValueError(f"Output alignment changed at position {original['position']}")
        if dual["source"] != translated["source"] + "\n" + original["source"]:
            raise ValueError(f"Bilingual text mismatch at position {original['position']}")
    return {"checked_cues": len(source["cues"]), "structure": "passed",
            "semantic_review": "required", "zh": args.zh, "bilingual": args.bilingual}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ["extract", "build", "check"]:
        sub = commands.add_parser(name)
        sub.add_argument("source")
        sub.add_argument("--encoding", default="utf-8-sig", help="Source encoding only")
        if name == "extract":
            sub.add_argument("output")
        else:
            if name == "build":
                sub.add_argument("draft")
            sub.add_argument("--zh", required=True)
            sub.add_argument("--bilingual", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(globals()[args.command](args), ensure_ascii=False, indent=2))
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
