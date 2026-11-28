"""Trusted built-in assets, scene definitions and source metadata."""

from copy import deepcopy

# Geometry is normalized; surface and device cannot be deleted or moved by decor.
ASSETS = {
    "table_round": {"kind": "surface", "variant": "wood"},
    "table_square": {"kind": "surface", "variant": "wood"},
    "table_felt": {"kind": "surface", "variant": "felt"},
    "mat_blue": {"kind": "surface", "variant": "textile"},
    "mat_striped": {"kind": "surface", "variant": "textile"},
    "boat_deck": {"kind": "surface", "variant": "metal"},
    "boat_bench": {"kind": "surface", "variant": "metal"},
    "chair_wood": {"kind": "decor", "variant": "wood"},
    "chair_metal": {"kind": "decor", "variant": "metal"},
    "lamp": {"kind": "decor", "variant": "warm"},
    "plant": {"kind": "decor", "variant": "green"},
    "bag": {"kind": "decor", "variant": "canvas"},
    "speaker_s50": {"kind": "decor", "variant": "wood"},
    "cushion": {"kind": "decor", "variant": "textile"},
}
SKINS = ("vesna_212s4", "vega_122s_two_tier", "mayak_233")
BACKGROUNDS = ("apartment", "garage", "beach", "kindergarten_boat", "card_club")
LIGHTS = ("day", "evening", "dim")
SURFACES = {
    "apartment": ("table_round", "table_square", "table_felt"),
    "garage": ("table_round", "table_square"),
    "beach": ("mat_blue", "mat_striped"),
    "kindergarten_boat": ("boat_deck", "boat_bench"),
    "card_club": ("table_felt", "table_round", "table_square"),
}


def obj(identifier, asset, x, y):
    return {
        "id": identifier,
        "asset_id": asset,
        "x": x,
        "y": y,
        "scale": 100,
        "rotation": 0,
        "z": 0,
    }


def preset(background):
    if background not in BACKGROUNDS:
        raise ValueError("Unknown scene")
    objects = {
        "apartment": [
            obj("lamp1", "lamp", 12, 23),
            obj("plant1", "plant", 87, 30),
            obj("chair1", "chair_wood", 80, 76),
            obj("speaker1", "speaker_s50", 30, 17),
            obj("speaker2", "speaker_s50", 70, 17),
        ],
        "garage": [
            obj("chair1", "chair_metal", 17, 67),
            obj("chair2", "chair_wood", 85, 67),
            obj("bag1", "bag", 15, 87),
        ],
        "beach": [obj("bag1", "bag", 16, 76), obj("cushion1", "cushion", 83, 69)],
        "kindergarten_boat": [obj("plant1", "plant", 14, 25), obj("cushion1", "cushion", 82, 75)],
        "card_club": [
            obj("lamp1", "lamp", 15, 26),
            obj("chair1", "chair_wood", 85, 75),
            obj("speaker1", "speaker_s50", 29, 17),
            obj("speaker2", "speaker_s50", 71, 17),
        ],
    }[background]
    return {
        "schema_version": 1,
        "background": background,
        "lighting": "day" if background in {"beach", "kindergarten_boat"} else "evening",
        "surface": SURFACES[background][0],
        "skin": "vesna_212s4"
        if background in {"beach", "garage", "kindergarten_boat"}
        else "vega_122s_two_tier",
        "objects": deepcopy(objects),
    }


def catalogue():
    return {
        "schema_version": 1,
        "assets": {
            key: {
                **value,
                "revision": 1,
                "format": "procedural_svg",
                "origin": "sameplace_original",
                "label_key": "decor." + key,
            }
            for key, value in ASSETS.items()
        },
        "skins": list(SKINS),
        "surfaces": SURFACES,
        "scenes": [{"id": key, "revision": 1, "scene": preset(key)} for key in BACKGROUNDS],
        "lights": list(LIGHTS),
    }
