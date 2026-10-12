#!/usr/bin/env python3
"""Check design tokens without false passes.

Core types follow the DTCG 2025.10 format: color (sRGB/OKLCH), dimension,
duration, cubicBezier, number, fontFamily, fontWeight, inherited group types
and whole-token curly aliases.

Three skill-specific extension types are also accepted. They are NOT part of
DTCG and are validated by this script only: motion, surface-effect, font-size.

Unsupported constructs fail with an explicit diagnostic for manual review.
Exit code: 0 when every check passes, 1 otherwise.
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path


TYPES = {"color", "dimension", "duration", "cubicBezier", "number", "fontFamily", "fontWeight", "motion", "surface-effect", "font-size"}
GROUP_META = {"$type", "$description", "$extensions", "$deprecated"}
TOKEN_META = GROUP_META | {"$value"}
ALIAS = re.compile(r"^\{([^{}]+)\}$")
HEX = re.compile(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")
NUM = r"-?(?:\d+(?:\.\d+)?|\.\d+)"
TIME = re.compile(rf"^({NUM})(ms|s)$")
FONT_UNITS = ("px", "rem", "em", "vw", "vh", "vmin", "vmax", "pt")
LENGTH = re.compile(rf"^({NUM})({'|'.join(FONT_UNITS)})$")
CUBIC_BEZIER = re.compile(rf"^cubic-bezier\(\s*({NUM})\s*,\s*({NUM})\s*,\s*({NUM})\s*,\s*({NUM})\s*\)$")
EASING_KEYWORDS = {"linear", "ease", "ease-in", "ease-out", "ease-in-out", "step-start", "step-end"}
FONT_WEIGHTS = {"thin", "hairline", "extra-light", "ultra-light", "light", "normal", "regular", "medium", "semi-bold", "demi-bold", "bold", "extra-bold", "ultra-bold", "black", "heavy", "extra-black", "ultra-black"}
# CSS colors allowed as scrim strings. Colons and quotes are never valid here, which rules out URLs and script schemes.
CSS_COLOR = re.compile(
    r"^(#[0-9a-fA-F]{3,4}|#[0-9a-fA-F]{6}|#[0-9a-fA-F]{8}|transparent|currentcolor"
    r"|(rgb|rgba|hsl|hsla|oklch|oklab|lab|lch|color|linear-gradient|radial-gradient)\([0-9a-zA-Z\s.,%#()/+-]*\))$",
    re.IGNORECASE,
)
BACKDROP_FILTER = re.compile(r"^(\s*[a-z-]+\([0-9a-zA-Z\s.,%#/+-]*\)\s*)+$")
HEX_TOLERANCE = 1  # per 0-255 channel, to absorb rounding


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def duplicate_key(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


# ------------------------------------------------------------------------------
# Color math (sRGB is handled gamma-encoded, as browsers composite it)
# ------------------------------------------------------------------------------

def to_srgb(color):
    """Return gamma-encoded sRGB components (0..1) for a validated color value."""
    components = color["components"]
    if color["colorSpace"] == "srgb":
        return tuple(components)
    lightness, chroma, hue = components
    a = chroma * math.cos(math.radians(hue))
    b = chroma * math.sin(math.radians(hue))
    l_cone = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_cone = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_cone = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    linear = (
        4.0767416621 * l_cone - 3.3077115913 * m_cone + 0.2309699292 * s_cone,
        -1.2684380046 * l_cone + 2.6097574011 * m_cone - 0.3413193965 * s_cone,
        -0.0041960863 * l_cone - 0.7034186147 * m_cone + 1.707614701 * s_cone,
    )
    if any(v < -0.0001 or v > 1.0001 for v in linear):
        raise ValueError("OKLCH color is outside the sRGB gamut")
    linear = tuple(min(1.0, max(0.0, v)) for v in linear)
    return tuple(12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055 for v in linear)


def relative_luminance(rgb):
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def blend(top, alpha, bottom):
    return tuple(alpha * t + (1 - alpha) * b for t, b in zip(top, bottom))


def contrast_ratio(foreground_rgb, background_rgb):
    values = (relative_luminance(foreground_rgb), relative_luminance(background_rgb))
    return (max(values) + 0.05) / (min(values) + 0.05)


# ------------------------------------------------------------------------------
# Value validation
# ------------------------------------------------------------------------------

def check_alias(value, expected_type, lookup):
    """Validate an alias used inside a composite value. Returns an error string or None."""
    match = ALIAS.fullmatch(value)
    if not match:
        return None
    if lookup is None:
        return f"alias {value} cannot be resolved in this context"
    resolved = lookup(tuple(match.group(1).split(".")))
    if resolved is None:
        return f"alias {value} does not resolve to a token"
    if resolved[0] != expected_type:
        return f"alias {value} must reference a {expected_type} token, not {resolved[0]!r}"
    return None


def validate_color(value):
    if not isinstance(value, dict) or value.get("colorSpace") not in {"srgb", "oklch"}:
        return "expected a color object in supported space srgb or oklch"
    if set(value) - {"colorSpace", "components", "alpha", "hex"}:
        return "unsupported color property"
    components = value.get("components")
    if not isinstance(components, list) or len(components) != 3 or not all(number(v) for v in components):
        return "expected three numeric color components"
    if value["colorSpace"] == "srgb" and any(not 0 <= v <= 1 for v in components):
        return "sRGB components must be within 0..1"
    if value["colorSpace"] == "oklch" and not (0 <= components[0] <= 1 and components[1] >= 0):
        return "OKLCH lightness must be within 0..1 and chroma nonnegative"
    alpha = value.get("alpha", 1)
    if not number(alpha) or not 0 <= alpha <= 1:
        return "alpha must be within 0..1"
    if "hex" in value:
        if not isinstance(value["hex"], str) or not HEX.fullmatch(value["hex"]):
            return "hex must be a six- or eight-digit CSS hex color"
        try:
            rgb = to_srgb(value)
        except ValueError as exc:
            return f"hex cannot be checked: {exc}"
        digits = value["hex"][1:]
        expected = [round(v * 255) for v in rgb]
        actual = [int(digits[i:i + 2], 16) for i in (0, 2, 4)]
        if len(digits) == 8:
            expected.append(round(alpha * 255))
            actual.append(int(digits[6:8], 16))
        if any(abs(e - a) > HEX_TOLERANCE for e, a in zip(expected, actual)):
            computed = "#" + "".join(f"{v:02x}" for v in expected)
            return f"hex {value['hex']} does not match components (computed {computed})"
    return None


def parse_length(text):
    match = LENGTH.fullmatch(text.strip()) if isinstance(text, str) else None
    return (float(match.group(1)), match.group(2)) if match else None


def length_operand(item):
    """Accept '1rem' or {value, unit}; return (value, unit) or None."""
    if isinstance(item, dict):
        if set(item) == {"value", "unit"} and number(item["value"]) and item["unit"] in FONT_UNITS:
            return float(item["value"]), item["unit"]
        return None
    return parse_length(item)


def ideal_expression(item):
    """A clamp ideal is a length or `length (+|-) length`."""
    if isinstance(item, dict):
        return length_operand(item) is not None
    if not isinstance(item, str):
        return False
    parts = re.split(r"\s+[+-]\s+", item.strip())
    return 1 <= len(parts) <= 2 and all(parse_length(p) for p in parts)


def validate_clamp(minimum, ideal, maximum):
    low, high = length_operand(minimum), length_operand(maximum)
    if low is None or high is None or not ideal_expression(ideal):
        return "clamp() needs min and max lengths and an ideal length or `length + length` expression"
    if low[1] == high[1] and low[0] > high[0]:
        return f"clamp() min {minimum} is larger than max {maximum}"
    return None


def validate_font_size(value):
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("clamp("):
            if not text.endswith(")"):
                return f"invalid clamp() syntax in font-size: '{text}'"
            args = [a.strip() for a in text[len("clamp("):-1].split(",")]
            if len(args) != 3:
                return f"invalid clamp() syntax in font-size: '{text}'. Expected clamp(min, ideal, max)"
            return validate_clamp(*args)
        return None if parse_length(text) else f"invalid font-size string: '{text}'. Must be a length or clamp()"
    if isinstance(value, dict):
        if "clamp" in value:
            clamp = value["clamp"]
            if set(value) != {"clamp"} or not isinstance(clamp, dict) or set(clamp) != {"min", "ideal", "max"}:
                return "font-size clamp object must be {clamp: {min, ideal, max}}"
            return validate_clamp(clamp["min"], clamp["ideal"], clamp["max"])
        return None if length_operand(value) else "font-size object must be {value, unit} or {clamp: {min, ideal, max}}"
    return "expected font-size string or object"


def validate_motion(value, lookup):
    if not isinstance(value, dict):
        return "expected motion object with duration and easing"
    if "duration" not in value or ("easing" not in value and "curve" not in value):
        return "motion object must contain 'duration' and 'easing'"
    duration = value["duration"]
    easing = value["easing"] if "easing" in value else value["curve"]

    if isinstance(duration, str) and ALIAS.fullmatch(duration):
        issue = check_alias(duration, "duration", lookup)
        if issue:
            return issue
    elif isinstance(duration, str):
        match = TIME.fullmatch(duration.strip())
        if not match or float(match.group(1)) < 0:
            return f"invalid motion duration: '{duration}'. Use a non-negative CSS time such as '200ms' or '0.3s'"
    elif isinstance(duration, dict):
        if not (number(duration.get("value")) and duration["value"] >= 0 and duration.get("unit") in {"ms", "s"}):
            return "motion duration object must have a non-negative numeric 'value' and unit 'ms' or 's'"
    else:
        return f"invalid motion duration: '{duration}'. Use a CSS time string, {{value, unit}} or an alias"

    if isinstance(easing, str) and ALIAS.fullmatch(easing):
        return check_alias(easing, "cubicBezier", lookup)
    if isinstance(easing, str):
        if easing in EASING_KEYWORDS:
            return None
        match = CUBIC_BEZIER.fullmatch(easing.strip())
        if not match:
            return f"invalid easing: '{easing}'. Must be a CSS keyword or cubic-bezier(x1, y1, x2, y2)"
        nums = [float(x) for x in match.groups()]
        return None if 0 <= nums[0] <= 1 and 0 <= nums[2] <= 1 else "cubic-bezier x coordinates must be in range 0..1"
    if isinstance(easing, list):
        if len(easing) != 4 or not all(number(x) for x in easing):
            return "easing curve array must contain 4 numbers [x1, y1, x2, y2]"
        return None if 0 <= easing[0] <= 1 and 0 <= easing[2] <= 1 else "easing curve x coordinates must be within 0..1"
    return f"invalid easing: '{easing}'. Must be a keyword, cubic-bezier string, [x1, y1, x2, y2] list or alias"


def validate_surface_effect(value, lookup):
    known = {"blur", "saturation", "noise", "backdropFilter", "scrim"}
    if not isinstance(value, dict) or not any(k in value for k in known):
        return "expected surface-effect object with blur, saturation, noise, backdropFilter, or scrim"
    if set(value) - known:
        return f"unsupported surface-effect properties: {sorted(set(value) - known)}"
    if "blur" in value:
        blur = value["blur"]
        if isinstance(blur, str) and ALIAS.fullmatch(blur):
            issue = check_alias(blur, "dimension", lookup)
            if issue:
                return issue
        else:
            parsed = length_operand(blur)
            if parsed is None or parsed[1] not in {"px", "rem", "em"} or parsed[0] < 0:
                return f"invalid surface-effect blur: '{blur}'. Expected a non-negative px, rem or em length"
    if "saturation" in value:
        sat = value["saturation"]
        if isinstance(sat, str):
            if not re.fullmatch(r"\d+(\.\d+)?%?", sat.strip()):
                return f"invalid surface-effect saturation: '{sat}'"
        elif not (number(sat) and sat >= 0):
            return "surface-effect saturation must be a non-negative number or percentage"
    if "noise" in value:
        noise = value["noise"]
        valid = (number(noise) and 0 <= noise <= 1) or (isinstance(noise, str) and re.fullmatch(r"\d+(\.\d+)?%?", noise.strip()))
        if not valid:
            return f"invalid surface-effect noise opacity: '{noise}'. Must be numeric between 0 and 1 or percentage"
    if "backdropFilter" in value:
        bf = value["backdropFilter"]
        if not isinstance(bf, str) or not BACKDROP_FILTER.fullmatch(bf):
            return f"invalid surface-effect backdropFilter: '{bf}'. Expected CSS filter functions such as 'blur(12px) saturate(1.4)'"
    if "scrim" in value:
        scrim = value["scrim"]
        if isinstance(scrim, str) and ALIAS.fullmatch(scrim):
            return check_alias(scrim, "color", lookup)
        if isinstance(scrim, dict):
            issue = validate_color(scrim)
            return f"invalid surface-effect scrim: {issue}" if issue else None
        if not isinstance(scrim, str) or not CSS_COLOR.fullmatch(scrim.strip()):
            return f"invalid surface-effect scrim: '{scrim}'. Expected a color object, alias, or CSS color/gradient"
    return None


def validate_value(token_type, value, lookup=None):
    if token_type == "number":
        return None if number(value) else "expected a finite number"
    if token_type in {"dimension", "duration"}:
        units = {"px", "rem"} if token_type == "dimension" else {"ms", "s"}
        if not isinstance(value, dict) or set(value) != {"value", "unit"}:
            return "expected {value: number, unit: string}"
        if not number(value["value"]) or value["unit"] not in units:
            return f"expected a finite value and unit in {sorted(units)}"
        if token_type == "duration" and value["value"] < 0:
            return "duration must not be negative"
        return None
    if token_type == "cubicBezier":
        if not isinstance(value, list) or len(value) != 4 or not all(number(v) for v in value):
            return "expected four finite numeric control values"
        if not (0 <= value[0] <= 1 and 0 <= value[2] <= 1):
            return "the x coordinates must be within 0..1"
        return None
    if token_type == "fontFamily":
        valid = isinstance(value, str) and bool(value.strip())
        valid |= isinstance(value, list) and bool(value) and all(isinstance(v, str) and v.strip() for v in value)
        return None if valid else "expected a font name or a nonempty list of font names"
    if token_type == "fontWeight":
        valid = (number(value) and 1 <= value <= 1000) or (isinstance(value, str) and value in FONT_WEIGHTS)
        return None if valid else "expected a font weight keyword or number from 1 to 1000"
    if token_type == "motion":
        return validate_motion(value, lookup)
    if token_type == "surface-effect":
        return validate_surface_effect(value, lookup)
    if token_type == "font-size":
        return validate_font_size(value)
    if token_type == "color":
        return validate_color(value)
    return f"unsupported type: {token_type}"


# ------------------------------------------------------------------------------
# Audit
# ------------------------------------------------------------------------------

def audit_tokens(data, pairs=None):
    errors = []
    tokens = {}
    inherited_types = {}

    if not isinstance(data, dict):
        return ["root: expected an object"], 0

    def walk(group, path=(), inherited=None):
        for key, expected in (("$description", str), ("$extensions", dict)):
            if key in group and not isinstance(group[key], expected):
                errors.append(f"{'.'.join(path) or 'root'}: {key} has an invalid value")
        if "$deprecated" in group and not isinstance(group["$deprecated"], (bool, str)):
            errors.append(f"{'.'.join(path) or 'root'}: $deprecated has an invalid value")
        if "$value" in group:
            label = ".".join(path)
            if any(key not in TOKEN_META for key in group):
                errors.append(f"{label}: token contains a child or unsupported property")
            token_type = group.get("$type", inherited)
            is_alias = isinstance(group["$value"], str) and ALIAS.fullmatch(group["$value"])
            if (not isinstance(token_type, str) or token_type not in TYPES) and not (token_type is None and is_alias):
                errors.append(f"{label}: missing or unsupported $type: {token_type!r}")
            tokens[path] = group
            inherited_types[path] = token_type
            return

        if "$extends" in group:
            errors.append(f"{'.'.join(path) or 'root'}: group $extends requires an external DTCG resolver")
        if "$type" in group and (not isinstance(group["$type"], str) or group["$type"] not in TYPES):
            errors.append(f"{'.'.join(path) or 'root'}: unsupported group $type")
        current_type = group.get("$type", inherited)
        for key, item in group.items():
            if key in GROUP_META:
                continue
            label = ".".join((*path, key))
            if key.startswith("$") and key != "$root":
                errors.append(f"{label}: unsupported group property")
                continue
            if any(character in key for character in ".{}"):
                errors.append(f"{label}: invalid token/group name")
            if not isinstance(item, dict):
                errors.append(f"{label}: expected a token or group object")
                continue
            walk(item, (*path, key), current_type)

    walk(data)
    if not tokens:
        errors.append("root: no tokens found")

    def resolve(path, trail=()):
        if path in trail:
            errors.append(f"{'.'.join(path)}: circular alias")
            return None
        target = tokens.get(path)
        if target is None:
            errors.append(f"{'.'.join(path)}: alias target does not exist")
            return None
        value = target["$value"]
        if isinstance(value, str) and value.startswith("{"):
            match = ALIAS.fullmatch(value)
            if not match:
                errors.append(f"{'.'.join(path)}: unsupported or malformed alias")
                return None
            return resolve(tuple(match.group(1).split(".")), (*trail, path))
        return inherited_types[path], value

    def lookup(path):
        """Resolve an alias that appears inside a composite value, without duplicate error noise."""
        if path not in tokens:
            return None
        return resolve(path)

    for path in tokens:
        label = ".".join(path)
        try:
            result = resolve(path)
            if result is None:
                continue
            target_type, value = result
            own_type = inherited_types[path]
            if own_type is not None and own_type != target_type:
                errors.append(f"{label}: alias type {target_type!r} differs from {own_type!r}")
                continue
            effective_type = own_type or target_type
            if not isinstance(effective_type, str) or effective_type not in TYPES:
                continue
            issue = validate_value(effective_type, value, lookup)
            if issue:
                errors.append(f"{label}: {issue}")
        except Exception as exc:  # one malformed token must never hide the rest of the audit
            errors.append(f"{label}: validator error ({type(exc).__name__}: {exc})")

    if pairs is not None:
        errors.extend(audit_contrast_pairs(pairs, resolve))

    return list(dict.fromkeys(errors)), len(tokens)


def audit_contrast_pairs(pairs, resolve):
    errors = []
    if not isinstance(pairs, list):
        return ["contrast pairs: expected a list"]

    def color_of(label, field, ref):
        result = resolve(tuple(ref.strip("{}").split(".")))
        if result is None:
            return None
        if result[0] != "color" or validate_color(result[1]):
            errors.append(f"{label}: {field} must be a valid color token")
            return None
        return result[1]

    for index, pair in enumerate(pairs, 1):
        label = f"contrast pair {index}"
        refs_ok = isinstance(pair, dict) and all(isinstance(pair.get(key), str) and pair[key] for key in ("foreground", "background"))
        if not refs_ok or not number(pair.get("minRatio")) or pair["minRatio"] <= 1:
            errors.append(f"{label}: expected foreground, background, and minRatio > 1")
            continue
        if "over" in pair and not (isinstance(pair["over"], str) and pair["over"]):
            errors.append(f"{label}: 'over' must be a color token path")
            continue
        foreground = color_of(label, "foreground", pair["foreground"])
        background = color_of(label, "background", pair["background"])
        if foreground is None or background is None:
            continue
        try:
            bg_rgb = to_srgb(background)
            bg_alpha = background.get("alpha", 1)
            if bg_alpha < 1:
                if "over" not in pair:
                    errors.append(
                        f"{label}: background is translucent (alpha {bg_alpha}); "
                        "add \"over\": <opaque backdrop token> so it can be composited"
                    )
                    continue
                backdrop = color_of(label, "over", pair["over"])
                if backdrop is None:
                    continue
                if backdrop.get("alpha", 1) < 1:
                    errors.append(f"{label}: 'over' backdrop must be opaque")
                    continue
                bg_rgb = blend(bg_rgb, bg_alpha, to_srgb(backdrop))
            fg_rgb = blend(to_srgb(foreground), foreground.get("alpha", 1), bg_rgb)
            ratio = contrast_ratio(fg_rgb, bg_rgb)
        except ValueError as exc:
            errors.append(f"{label}: {exc}")
            continue
        if ratio + 0.0001 < pair["minRatio"]:
            errors.append(f"{label}: {ratio:.2f}:1 is below {pair['minRatio']}:1")
    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate design tokens (DTCG 2025.10 core types plus skill extensions)")
    parser.add_argument("--tokens", type=Path, default=Path("tokens.json"), help="Path to token JSON file (default: tokens.json)")
    parser.add_argument("--contrast-pairs", type=Path, default=None, help="JSON list of {foreground, background, minRatio, over?} token paths")
    parser.add_argument("--json", action="store_true", help="Print machine-readable result")
    args = parser.parse_args()

    if args.contrast_pairs is None and Path("contrast-pairs.json").exists():
        args.contrast_pairs = Path("contrast-pairs.json")

    if not args.tokens.exists():
        error_msg = f"Token file not found: {args.tokens}. Generate tokens.json or pass --tokens <path>."
        report = {"status": "fail", "checked": "None", "token_count": 0, "errors": [error_msg]}
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"FAIL: 0 tokens checked\n  - {error_msg}")
        return 1

    try:
        data = json.loads(args.tokens.read_text(encoding="utf-8"), object_pairs_hook=duplicate_key)
        pairs = json.loads(args.contrast_pairs.read_text(encoding="utf-8"), object_pairs_hook=duplicate_key) if args.contrast_pairs else None
        errors, count = audit_tokens(data, pairs)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors, count = [str(exc)], 0
    checked = "DTCG 2025.10 core types and skill extension types"
    if args.contrast_pairs:
        checked += " and specified color contrast pairs"
    report = {"status": "pass" if not errors else "fail", "checked": checked, "token_count": count, "errors": errors}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{report['status'].upper()}: {count} tokens checked")
        for error in errors:
            print(f"  - {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
