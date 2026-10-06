"""Generate six original, non-personal images for a classroom demonstration."""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


def generate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    scene = Image.new('RGB', (512, 384), '#92b6d5')
    draw = ImageDraw.Draw(scene)
    draw.polygon([(0, 300), (150, 80), (300, 300)], fill='#324f42')
    draw.rectangle((230, 130, 460, 330), fill='#bc7751')
    for x in range(245, 455, 35):
        for y in range(150, 315, 35):
            draw.rectangle((x, y, x + 18, y + 23), fill='#233142')
    draw.ellipse((350, 30, 420, 100), fill='#f5dd95')
    scene.save(output / '01-original.png')
    (output / '02-exact-copy.png').write_bytes((output / '01-original.png').read_bytes())
    scene.resize((256, 192), Image.Resampling.LANCZOS).save(output / '03-resized.png')
    scene.save(output / '04-compressed.jpg', quality=65)
    ImageOps.mirror(scene).save(output / '05-mirrored-review.png')
    document = Image.new('RGB', (512, 384), 'white')
    text = ImageDraw.Draw(document)
    text.text((45, 40), 'CLASS PROJECT\n\nImageVault AI\nPrivate photo storage\n\nThis is a different image.', fill='black', spacing=18)
    document.save(output / '06-unrelated-document.png')
    (output / 'manifest.json').write_text(json.dumps({
        'purpose': 'Synthetic demonstration, not a real-world accuracy benchmark',
        'exact': [['01-original.png', '02-exact-copy.png']],
        'near_duplicate': [['01-original.png', '03-resized.png'], ['01-original.png', '04-compressed.jpg']],
        'manual_review': ['05-mirrored-review.png'],
        'unrelated': ['06-unrelated-document.png'],
    }, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('demo-images'))
    generate(parser.parse_args().output)
