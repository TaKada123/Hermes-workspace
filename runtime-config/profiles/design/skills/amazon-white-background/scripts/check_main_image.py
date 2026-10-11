#!/usr/bin/env python3
"""Check (and optionally fix) an Amazon-style white-background main image.

  python check_main_image.py image.png [--min-coverage 0.85] [--min-size 1000] [--tolerance 3] [--fix fixed.png] [--json]

Checks
  white_background : share of a border band (outer 2%) whose pixels are within `tolerance` of #FFFFFF  (PASS ≥ 0.98)
  exact_ffffff     : share of detected background pixels that are exactly 255,255,255 (informational, aim ≥ 0.95)
  coverage         : longest side of the product bounding box ÷ matching image side             (PASS ≥ min-coverage)
  size             : longest image side in px                                                   (PASS ≥ min-size; 1600+ recommended)

--fix snaps near-white background pixels to pure #FFFFFF and re-crops/pads so the product covers ~87%, square canvas.
Pillow is supplied by the Hermes-managed runtime.
"""
import argparse, json, sys

try:
    from PIL import Image
except ImportError:
    sys.exit(
        "Pillow is supplied by the Hermes-managed runtime. If unavailable, stop and run "
        "`hermes pm doctor` followed by `hermes pm repair`."
    )


def analyse(img, tolerance=3, product_threshold=12):
    rgb = img.convert("RGB")
    w, h = rgb.size
    pixels = rgb.load()
    band = max(2, int(round(min(h, w) * 0.02)))
    border_count = 0
    white_border_count = 0
    product_points = []
    for y in range(h):
        for x in range(w):
            distance = 255 - min(pixels[x, y])  # 0 = pure white
            if x < band or x >= w - band or y < band or y >= h - band:
                border_count += 1
                white_border_count += int(distance <= tolerance)
            if distance > product_threshold:    # anything clearly not white
                product_points.append((x, y))
    white_bg = white_border_count / border_count

    if not product_points:
        return dict(width=w, height=h, white_background=white_bg, exact_ffffff=1.0, coverage=0.0, bbox=None)
    xs, ys = zip(*product_points)
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    coverage = max(bw / w, bh / h)
    background_count = 0
    exact_count = 0
    for y in range(h):
        for x in range(w):
            if x0 <= x <= x1 and y0 <= y <= y1:
                continue
            background_count += 1
            exact_count += int(pixels[x, y] == (255, 255, 255))
    exact = exact_count / background_count if background_count else 0.0
    return dict(width=w, height=h, white_background=white_bg, exact_ffffff=exact,
                coverage=float(coverage), bbox=[x0, y0, x1, y1])


def fix(img, bbox, out, tolerance=8, target=0.87):
    im = img.convert("RGB")
    im.putdata([
        (255, 255, 255) if 255 - min(pixel) <= tolerance else pixel
        for pixel in im.getdata()
    ])
    if bbox:
        x0, y0, x1, y1 = bbox
        im = im.crop((x0, y0, x1 + 1, y1 + 1))
    side = int(round(max(im.size) / target))
    side = max(side, 1000)
    scale = side * target / max(im.size)
    if scale > 1:  # upscale small images so the canvas reaches 1000+ px
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        side = int(round(max(im.size) / target))
    canvas = Image.new("RGB", (side, side), (255, 255, 255))
    canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    canvas.save(out, quality=95)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--min-coverage", type=float, default=0.85)
    ap.add_argument("--min-size", type=int, default=1000)
    ap.add_argument("--tolerance", type=int, default=3, help="max distance from 255 counted as white (0 = exact)")
    ap.add_argument("--fix", metavar="OUT")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    img = Image.open(a.image)
    r = analyse(img, a.tolerance)
    longest = max(r["width"], r["height"])
    checks = {
        "white_background": (r["white_background"] >= 0.98, f"{r['white_background']:.1%} of border pixels are white (≤{a.tolerance} from #FFFFFF)"),
        "exact_ffffff": (r["exact_ffffff"] >= 0.95, f"{r['exact_ffffff']:.1%} of background is exactly #FFFFFF"),
        "coverage": (r["coverage"] >= a.min_coverage, f"product covers {r['coverage']:.1%} of the frame (need ≥{a.min_coverage:.0%})"),
        "size": (longest >= a.min_size, f"longest side {longest}px (need ≥{a.min_size}; 1600+ recommended for zoom)"),
    }
    ok = all(v[0] for k, v in checks.items() if k != "exact_ffffff")
    if a.json:
        print(json.dumps({"pass": ok, **{k: {"pass": v[0], "detail": v[1]} for k, v in checks.items()}, "bbox": r["bbox"]}, ensure_ascii=False, indent=2))
    else:
        for k, (p, d) in checks.items():
            tag = "PASS" if p else ("WARN" if k == "exact_ffffff" else "FAIL")
            print(f"[{tag}] {k:17s} {d}")
        print("RESULT:", "PASS" if ok else "FAIL")
    if a.fix:
        print("fixed ->", fix(img, r["bbox"], a.fix))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
