#!/usr/bin/env python3
"""Daily orchestrator: build long-form + Short + thumbnail, then upload both."""
import sys, os, pathlib, traceback
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import OUT, get_day_entry

def main(day=None, do_upload=True):
    plan, entry, day = get_day_entry(day)
    print(f"=== The Bible Outdoor — Day {day}: {entry['theme']} ===")

    import build_longform, build_short, build_thumbnail
    lf_path, lf_meta = build_longform.build(day)
    sh_path, sh_meta = build_short.build(day)
    thumb = build_thumbnail.build(day)

    if not do_upload:
        print("Build-only mode; skipping upload.")
        return

    import upload
    final_dir = OUT / f"day{day:02d}"
    ok = True
    for meta_file, t in [(final_dir / "longform_meta.json", thumb),
                         (final_dir / "short_meta.json", None)]:
        try:
            upload.upload(meta_file, t)
        except Exception:
            ok = False
            traceback.print_exc()
    if not ok:
        sys.exit(1)

if __name__ == "__main__":
    day = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != "-" else None
    do_upload = "--no-upload" not in sys.argv
    main(day, do_upload)
