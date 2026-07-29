"""Theme tokens and the contrast rules the desktop must satisfy.

Every colour the shell paints comes from a palette in this module. Nothing
hardcodes a hex value elsewhere, so switching to the dark palette cannot leave
an unreadable corner behind, and the contrast gate can check the whole surface
by checking these tables.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum

# WCAG 2.2 success criteria the product commits to.
AA_NORMAL_TEXT_RATIO = 4.5
AA_LARGE_TEXT_RATIO = 3.0
AA_NON_TEXT_RATIO = 3.0
LARGE_TEXT_POINTS = 18


class ThemeMode(StrEnum):
    """What the user asked for, which is not always what gets painted."""

    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True, slots=True)
class Palette:
    """One complete set of colour roles."""

    canvas: str
    surface: str
    surface_subtle: str
    text: str
    muted: str
    primary: str
    primary_hover: str
    on_primary: str
    border: str
    focus: str
    success: str
    warning: str
    danger: str
    navigation: str
    navigation_text: str
    navigation_hover: str

    def role_names(self) -> tuple[str, ...]:
        return tuple(field.name for field in fields(self))


LIGHT = Palette(
    canvas="#F5F7FA",
    surface="#FFFFFF",
    surface_subtle="#EEF2F7",
    text="#172033",
    muted="#5A6376",
    primary="#2F51C8",
    primary_hover="#2342AB",
    on_primary="#FFFFFF",
    border="#808C9E",
    focus="#1B3FA8",
    success="#0F6B4B",
    warning="#8A5200",
    danger="#B02E40",
    navigation="#17233D",
    navigation_text="#DCE5F5",
    navigation_hover="#2C3E62",
)

DARK = Palette(
    canvas="#12161F",
    surface="#1A2029",
    surface_subtle="#232A35",
    text="#E9EEF6",
    muted="#A7B2C4",
    primary="#7FA5F5",
    primary_hover="#9DBBFA",
    on_primary="#0B111C",
    border="#677384",
    focus="#9DBBFA",
    success="#5FCFA1",
    warning="#E8B45C",
    danger="#F2848F",
    navigation="#0E131B",
    navigation_text="#D5DEEC",
    navigation_hover="#242D3B",
)

SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 20, "xl": 28}
RADIUS = {"sm": 6, "md": 10, "lg": 16}
TYPE = {"body": 13, "label": 12, "title": 24, "hero": 30}

# Pairs the shell actually renders. The contrast gate walks this table, so a
# new pairing must be declared here before it can be painted.
TEXT_PAIRS: tuple[tuple[str, str, bool], ...] = (
    ("text", "canvas", False),
    ("text", "surface", False),
    ("text", "surface_subtle", False),
    ("muted", "canvas", False),
    ("muted", "surface", False),
    ("muted", "surface_subtle", False),
    ("on_primary", "primary", False),
    ("on_primary", "primary_hover", False),
    ("success", "surface", False),
    ("warning", "surface", False),
    ("danger", "surface", False),
    ("navigation_text", "navigation", False),
    ("navigation_text", "navigation_hover", False),
    ("primary", "surface", True),
)

NON_TEXT_PAIRS: tuple[tuple[str, str], ...] = (
    ("border", "surface"),
    ("border", "canvas"),
    ("focus", "surface"),
    ("focus", "canvas"),
    ("primary", "surface"),
)


def resolve(mode: ThemeMode, *, system_prefers_dark: bool) -> Palette:
    """Return the palette to paint for a requested mode."""

    if mode is ThemeMode.DARK:
        return DARK
    if mode is ThemeMode.LIGHT:
        return LIGHT
    return DARK if system_prefers_dark else LIGHT


def relative_luminance(color: str) -> float:
    """Return the WCAG relative luminance of an ``#RRGGBB`` colour."""

    red, green, blue = (_channel(value) for value in _rgb(color))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: str, background: str) -> float:
    """Return the WCAG contrast ratio between two colours."""

    first = relative_luminance(foreground)
    second = relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def contrast_failures(palette: Palette) -> tuple[str, ...]:
    """Return a readable description of every pair below its threshold."""

    failures: list[str] = []
    for foreground, background, is_large in TEXT_PAIRS:
        required = AA_LARGE_TEXT_RATIO if is_large else AA_NORMAL_TEXT_RATIO
        ratio = contrast_ratio(getattr(palette, foreground), getattr(palette, background))
        if ratio < required:
            failures.append(f"{foreground} on {background}: {ratio:.2f} < {required}")
    for foreground, background in NON_TEXT_PAIRS:
        ratio = contrast_ratio(getattr(palette, foreground), getattr(palette, background))
        if ratio < AA_NON_TEXT_RATIO:
            failures.append(f"{foreground} on {background}: {ratio:.2f} < {AA_NON_TEXT_RATIO}")
    return tuple(failures)


def stylesheet(palette: Palette) -> str:
    """Render the application stylesheet from one palette."""

    return f"""
    QWidget {{
        color: {palette.text};
        font-family: "Segoe UI";
        font-size: {TYPE["body"]}px;
    }}
    QMainWindow, QWidget#AppCanvas {{
        background: {palette.canvas};
    }}
    QFrame#Navigation {{
        background: {palette.navigation};
        border: none;
    }}
    QPushButton#NavButton {{
        color: {palette.navigation_text};
        background: transparent;
        border: none;
        border-radius: {RADIUS["md"]}px;
        padding: 11px 14px;
        text-align: left;
        font-weight: 600;
    }}
    QPushButton#NavButton:hover {{
        background: {palette.navigation_hover};
    }}
    QPushButton#NavButton:checked {{
        color: {palette.on_primary};
        background: {palette.primary};
    }}
    QFrame#Card {{
        background: {palette.surface};
        border: 1px solid {palette.border};
        border-radius: {RADIUS["lg"]}px;
    }}
    QLabel#WorkspaceTitle {{
        font-size: {TYPE["title"]}px;
        font-weight: 700;
    }}
    QLabel#HeroTitle {{
        font-size: {TYPE["hero"]}px;
        font-weight: 750;
    }}
    QLabel#Muted {{
        color: {palette.muted};
    }}
    QLabel#Success {{ color: {palette.success}; }}
    QLabel#Warning {{ color: {palette.warning}; }}
    QLabel#Danger {{ color: {palette.danger}; }}
    QPushButton {{
        background: {palette.surface};
        border: 1px solid {palette.border};
        border-radius: {RADIUS["sm"]}px;
        min-height: 34px;
        padding: 0 14px;
    }}
    QPushButton:hover {{
        border-color: {palette.primary};
    }}
    QPushButton:focus, QLineEdit:focus, QComboBox:focus,
    QPlainTextEdit:focus, QTextEdit:focus {{
        border: 2px solid {palette.focus};
        outline: none;
    }}
    QPushButton#Primary {{
        color: {palette.on_primary};
        background: {palette.primary};
        border-color: {palette.primary};
        font-weight: 650;
    }}
    QPushButton#Primary:hover {{
        background: {palette.primary_hover};
    }}
    QLineEdit, QComboBox, QPlainTextEdit, QTextEdit, QTableWidget, QTableView, QListView {{
        background: {palette.surface};
        color: {palette.text};
        border: 1px solid {palette.border};
        border-radius: {RADIUS["sm"]}px;
        padding: 7px;
        selection-background-color: {palette.primary};
        selection-color: {palette.on_primary};
    }}
    QTabWidget::pane {{
        border: 1px solid {palette.border};
        border-radius: {RADIUS["md"]}px;
        background: {palette.surface};
    }}
    QTabBar::tab {{
        padding: 9px 16px;
        color: {palette.muted};
    }}
    QTabBar::tab:selected {{
        color: {palette.primary};
        font-weight: 650;
    }}
    """


def _rgb(color: str) -> tuple[int, int, int]:
    value = color.strip()
    if not value.startswith("#") or len(value) != 7:
        raise ValueError(f"Theme colours must be #RRGGBB, got {color!r}.")
    try:
        return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))
    except ValueError as error:
        raise ValueError(f"Theme colours must be #RRGGBB, got {color!r}.") from error


def _channel(value: int) -> float:
    scaled = value / 255
    return scaled / 12.92 if scaled <= 0.04045 else ((scaled + 0.055) / 1.055) ** 2.4


__all__ = [
    "AA_LARGE_TEXT_RATIO",
    "AA_NON_TEXT_RATIO",
    "AA_NORMAL_TEXT_RATIO",
    "DARK",
    "LIGHT",
    "NON_TEXT_PAIRS",
    "RADIUS",
    "SPACING",
    "TEXT_PAIRS",
    "TYPE",
    "Palette",
    "ThemeMode",
    "contrast_failures",
    "contrast_ratio",
    "relative_luminance",
    "resolve",
    "stylesheet",
]
