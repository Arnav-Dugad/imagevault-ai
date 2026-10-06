"""Small reproducible pixel corpus; not a benchmark of model accuracy."""
from random import Random

import pytest
from PIL import Image, ImageDraw, ImageEnhance

from tests.test_reliability import encoded, evidence
from io import BytesIO


def generated_scene(seed):
    rng = Random(seed)
    image = Image.new('RGB', (512, 384), '#e4ddd1')
    draw = ImageDraw.Draw(image)
    for _ in range(18):
        x, y = rng.randrange(440), rng.randrange(310)
        w, h = rng.randrange(20, 70), rng.randrange(20, 70)
        color = tuple(rng.randrange(30, 230) for _ in range(3))
        draw.rectangle((x, y, x+w, y+h), fill=color)
    draw.text((20, 340), f'Classroom scene {seed}', fill='black')
    return image


@pytest.mark.parametrize('seed', range(10))
@pytest.mark.parametrize('transformation', ['resize', 'jpeg', 'brightness'])
def test_confirmed_copy_corpus(seed, transformation):
    first = generated_scene(seed)
    second = (first.resize((256, 192), Image.Resampling.LANCZOS) if transformation == 'resize'
              else Image.open(BytesIO(encoded(first, 'JPEG', quality=70))).convert('RGB')
              if transformation == 'jpeg' else ImageEnhance.Brightness(first).enhance(1.05))
    match = evidence(first, second)
    assert match is not None and match.match_type == 'PERCEPTUAL'


@pytest.mark.parametrize('seed', range(10))
def test_unrelated_scene_is_never_confirmed_even_with_high_semantic_score(seed):
    match = evidence(generated_scene(seed), generated_scene(seed + 100), clip=0.99)
    assert match is None or match.match_type == 'VISUAL'
