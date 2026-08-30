#!/usr/bin/env python3
"""Generate a copyright-safe duplicate-detection demonstration set."""

import argparse
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance


def build_scene(size: tuple[int, int] = (1280, 840)) -> Image.Image:
    image = Image.new("RGB", size, "#d9e8ff")
    draw = ImageDraw.Draw(image)
    width, height = size
    draw.rectangle((0, height * 0.58, width, height), fill="#365341")
    draw.ellipse((width * 0.71, height * 0.08, width * 0.84, height * 0.28), fill="#ffd36a")
    draw.polygon(
        [(0, height * 0.62), (width * 0.28, height * 0.28), (width * 0.52, height * 0.62)],
        fill="#75879d",
    )
    draw.polygon(
        [(width * 0.28, height * 0.28), (width * 0.35, height * 0.43), (width * 0.24, height * 0.39)],
        fill="#f5f6f8",
    )
    draw.rounded_rectangle(
        (width * 0.57, height * 0.44, width * 0.82, height * 0.74),
        radius=24,
        fill="#f38c62",
    )
    draw.rectangle((width * 0.61, height * 0.51, width * 0.68, height * 0.61), fill="#a9c7e8")
    draw.rectangle((width * 0.72, height * 0.51, width * 0.79, height * 0.61), fill="#a9c7e8")
    draw.polygon(
        [(width * 0.54, height * 0.46), (width * 0.695, height * 0.31), (width * 0.85, height * 0.46)],
        fill="#553c42",
    )
    draw.line((width * 0.15, height * 0.7, width * 0.48, height * 0.48), fill="#e8d6a5", width=28)
    return image


def generate(output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    original = output / "01-mountain-house-original.jpg"
    build_scene().save(original, "JPEG", quality=96, subsampling=0)

    exact = output / "02-mountain-house-exact-copy.jpg"
    shutil.copyfile(original, exact)

    with Image.open(original) as image:
        resized = image.resize((720, 472), Image.Resampling.LANCZOS)
        resized.save(output / "03-mountain-house-resized.jpg", "JPEG", quality=92)
        image.save(output / "04-mountain-house-compressed.jpg", "JPEG", quality=55)
        altered = ImageEnhance.Color(image).enhance(0.82)
        draw = ImageDraw.Draw(altered)
        draw.rectangle((1060, 690, 1230, 790), fill="#263a30")
        altered.save(output / "05-mountain-house-edited.jpg", "JPEG", quality=88)

    unrelated = Image.new("RGB", (1000, 1000), "#171b48")
    draw = ImageDraw.Draw(unrelated)
    for index in range(12):
        radius = 34 + index * 30
        color = (80 + index * 10, 45 + index * 8, 180 - index * 7)
        draw.ellipse((500 - radius, 500 - radius, 500 + radius, 500 + radius), outline=color, width=18)
    unrelated.save(output / "06-unrelated-abstract.png", "PNG")
    return sorted(output.iterdir())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("demo-images"))
    args = parser.parse_args()
    paths = generate(args.output)
    print(f"Generated {len(paths)} demo images in {args.output.resolve()}")
    for path in paths:
        print(f"  {path.name}")


if __name__ == "__main__":
    main()
