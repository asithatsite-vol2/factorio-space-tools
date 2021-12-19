from typing import Callable
from colorhash import ColorHash
from colormath.color_objects import LabColor, sRGBColor
from colormath.color_conversions import convert_color
from colormath.color_diff import delta_e_cie1994 as delta_e


def colorhash_to_srgb(color: ColorHash) -> sRGBColor:
    r, g, b = color.rgb
    return sRGBColor(r, g, b, is_upscaled=True)


def colorhash_delta_e(color1: ColorHash, color2: ColorHash) -> float:
    color1 = convert_color(colorhash_to_srgb(color1), LabColor)
    color2 = convert_color(colorhash_to_srgb(color2), LabColor)
    return delta_e(color1, color2)


def find_confusion_matrix(colormap: dict[str, ColorHash], distance: Callable[[ColorHash, ColorHash], float] = colorhash_delta_e) -> list[tuple[str, str, float]]:
    """
    Generate the confusion pairs based on color distance

    Args:
        colormap (dict[str, ColorHash]): A dict of tagged colors
        distance (Callable[[ColorHash, ColorHash], float]): A distance metric between colors

    Returns:
        list[tuple[str, str, float]]: A list of tuples, with (tag1, tag2, min_dist) structure
    """
    confusion = []
    for tag1, color1 in colormap.items():
        min_dist = float('inf')
        min_tag = ''
        for tag2, color2 in colormap.items():
            if tag1 == tag2:
                continue
            dist = distance(color1, color2)
            if min_dist > dist:
                min_dist = dist
                min_tag = tag2

        confusion.append((tag1, min_tag, min_dist))
    return confusion
