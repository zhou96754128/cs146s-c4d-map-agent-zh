#!/usr/bin/env python3
"""打包 .skill（ZIP，结构与 C4 系一致：SKILL.md + scripts/ + references/ + vendor/）
并同步官方命名产物：Zhouruoying_C4D_map.html。只用标准库。"""
import hashlib
import pathlib
import shutil
import zipfile

ROOT = pathlib.Path("/Users/xiaowo/.cogseed-dev/userWorkSpace/检查挑战清单完成情况/C4D/Zhouruoying_C4D_map-agent")
SKILLDIR = ROOT / "Zhouruoying_C4D_agent-skill"
OUT = ROOT / "Zhouruoying_C4D_Agent技能.skill"

INCLUDE_DIRS = ["scripts", "references", "vendor"]
INCLUDE_FILES = ["SKILL.md"]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    members = []
    members.append(SKILLDIR / "SKILL.md")
    for d in INCLUDE_DIRS:
        base = SKILLDIR / d
        if base.is_dir():
            members += sorted([p for p in base.rglob("*") if p.is_file()])
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for p in members:
            z.write(p, p.relative_to(SKILLDIR).as_posix())
    # verify
    with zipfile.ZipFile(OUT) as z:
        names = z.namelist()
        bad = z.testzip()
    print("SKILL_PKG =", OUT.name, OUT.stat().st_size, "bytes")
    print("  members =", len(names), "testzip =", bad)
    for n in names:
        print("   -", n)
    print("  sha256 =", sha(OUT)[:32])

    # official-named map copy
    src = ROOT / "Zhouruoying_C4D_郑州足迹地图.html"
    dst = ROOT / "Zhouruoying_C4D_map.html"
    shutil.copyfile(src, dst)
    print("MAP =", dst.name, dst.stat().st_size, "bytes", "identical =", sha(src) == sha(dst))
    print("  sha256 =", sha(dst)[:32])


if __name__ == "__main__":
    main()
