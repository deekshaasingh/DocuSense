"""
Finding a real TrueType font, on any operating system.

PIL's `ImageFont.load_default()` is a tiny bitmap face that Tesseract can
barely read. Falling back to it silently is exactly how the evaluation set
was once rendered unreadable, taking `invoice_number` precision down to 1.3
percent (docs/failures.md section 3). That was fixed by naming a DejaVu
path, but the fix only covered Linux, so the same silent fallback came back
on Windows and macOS (section 11).

So this module looks in the standard font directories of all three systems,
and by default raises rather than quietly returning the bitmap font. A loud
failure costs a minute; a silently unreadable dataset costs an afternoon and
produces numbers that look real.
"""
from PIL import ImageFont

# Monospace first: fixed-width digits are less ambiguous to OCR. PIL also
# resolves a bare filename against the system font directories, which is why
# the plain names appear as well as the absolute paths.
CANDIDATES = (
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    # Windows
    "C:/Windows/Fonts/consola.ttf",
    "C:/Windows/Fonts/cour.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "consola.ttf",
    "cour.ttf",
    "arial.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Courier New.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    # resolved by name against whatever font path exists
    "DejaVuSansMono.ttf",
    "DejaVuSans.ttf",
)

_MESSAGE = (
    "No TrueType font could be found on this machine.\n"
    "Rendering with PIL's built-in bitmap font produces pages that Tesseract "
    "cannot read, which would make every measured number meaningless, so this "
    "stops rather than continuing quietly.\n"
    "Install a font and try again:\n"
    "  Debian or Ubuntu:  sudo apt install fonts-dejavu\n"
    "  macOS and Windows: the standard system fonts are normally present, so "
    "this usually means PIL cannot see the font directory."
)


def load_font(size: int, required: bool = True):
    """Return a readable TrueType font at `size`, or raise saying why not."""
    for name in CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    if required:
        raise RuntimeError(_MESSAGE)
    return ImageFont.load_default()


def font_in_use(size: int = 20) -> str:
    """Which font was picked. Useful when results differ between machines."""
    for name in CANDIDATES:
        try:
            ImageFont.truetype(name, size)
            return name
        except OSError:
            continue
    return "none (bitmap fallback)"
