"""One-off helper: download real Pexels photos for a longform script's
`background_images`, reusing the same visuals.fetch_visual() lookup the
Shorts pipeline already uses for per-scene photos. Requires a real
PEXELS_API_KEY in .env -- there's no placeholder fallback here, since a
gradient placeholder written into an assets/ folder meant for real
artwork would look like a real download that just happens to be ugly,
not an obvious "this didn't work" signal.

    python -m pipeline.fetch_backgrounds content/scripts/stories/assets \
        dyatlov-mountain "snowy mountain slope dusk winter" \
        dyatlov-forest "dark pine forest snow night"

Writes dyatlov-mountain.jpg and dyatlov-forest.jpg into the given
directory. Update the script's "background_images" list to point at
whatever filenames you chose.
"""
import argparse
import sys
from pathlib import Path

from pipeline import visuals
from pipeline.config import Config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out_dir", type=Path, help="directory to save images into, e.g. content/scripts/stories/assets")
    parser.add_argument("pairs", nargs="+", help="alternating NAME QUERY NAME QUERY ... (NAME becomes NAME.jpg)")
    args = parser.parse_args()

    if len(args.pairs) % 2 != 0:
        sys.exit("Arguments must be NAME QUERY pairs -- got an odd count")

    cfg = Config.load()
    if not cfg.pexels_api_key:
        sys.exit("PEXELS_API_KEY is not set in .env -- this tool only fetches real Pexels photos, no placeholder fallback")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(args.pairs), 2):
        name, query = args.pairs[i], args.pairs[i + 1]
        out_path = args.out_dir / f"{name}.jpg"
        result = visuals.fetch_visual(query, out_path, cfg.pexels_api_key, cfg.size)
        if result != "pexels":
            print(f"! {query!r} -> fell back to a placeholder, not a real photo -- try a different query")
        else:
            print(f"OK: {query!r} -> {out_path}")


if __name__ == "__main__":
    main()
