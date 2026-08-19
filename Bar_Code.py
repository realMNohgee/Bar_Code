from __future__ import annotations

import argparse
import json
import os
import sys

# ---------------------------------------------------------------------------
# Bar_Code — validate and render 1D barcodes (EAN-13, UPC-A, EAN-8).
#
# Zero dependencies: pure Python 3 standard library only. It detects the
# barcode format from the digit length, validates the EAN/UPC check digit,
# and renders the binary module encoding as ASCII art and/or an SVG file
# using the standard EAN L/G/R code tables.
# ---------------------------------------------------------------------------

_DESCRIPTION = (
    "Bar_Code — validate and render 1D barcodes (EAN-13, UPC-A, EAN-8).\n"
    "Zero dependencies, pure Python 3 standard library.\n\n"
    "Subcommands:\n"
    "  check CODE     detect format by length and validate the check digit\n"
    "  generate CODE  render a barcode as ASCII art and/or an SVG file\n"
    "  list           list the L/G/R 7-bit encodings for digits 0-9"
)

# --- EAN/UPC encoding tables ------------------------------------------------

# L-codes: the 7-module bit patterns for digits 0-9 in left-odd parity.
# '1' = bar (black module), '0' = space (white module).
L_CODES = [
    "0001101",  # 0
    "0011001",  # 1
    "0010011",  # 2
    "0111101",  # 3
    "0100011",  # 4
    "0110001",  # 5
    "0101111",  # 6
    "0111011",  # 7
    "0110111",  # 8
    "0001011",  # 9
]

# Guard patterns (module sequences that delimit the symbol).
GUARD_START = "101"     # start guard, also reused as the end guard
GUARD_CENTER = "01010"  # center guard separating the two halves

# EAN-13 first-digit parity table: which code (L or G) each of the 6 left
# digits uses. The first digit of an EAN-13 is encoded *implicitly* by this
# L/G pattern — it is never written as its own 7-bit group.
#   'L' = L-code (odd parity),  'G' = G-code (even parity)
FIRST_DIGIT_PARITY = [
    "LLLLLL",  # 0
    "LLGLGG",  # 1
    "LLGGLG",  # 2
    "LLGGGL",  # 3
    "LGLLGG",  # 4
    "LGGLLG",  # 5
    "LGGGLL",  # 6
    "LGLGLG",  # 7
    "LGLGGL",  # 8
    "LGGLGL",  # 9
]

# Format name keyed by the FULL code length (including the check digit).
FORMATS = {8: "EAN-8", 12: "UPC-A", 13: "EAN-13"}

# Data-only lengths accepted by `generate` (check digit is computed/added).
# (12 is deliberately absent: a 12-digit string is unambiguous UPC-A data
#  AND unambiguous EAN-13 data-without-check, so EAN-13 must be given in
#  full, 13-digit form.)
DATA_ONLY_FORMATS = {7: "EAN-8", 11: "UPC-A"}


# --- Encoding helpers -------------------------------------------------------

def _complement(bits: str) -> str:
    """Bitwise NOT of a 0/1 string (1 -> 0, 0 -> 1)."""
    return "".join("1" if b == "0" else "0" for b in bits)


def _r_code(digit: int) -> str:
    """R-code (right side, even parity) = bitwise complement of the L-code."""
    return _complement(L_CODES[digit])


def _g_code(digit: int) -> str:
    """G-code (left side, even parity) = reverse of the R-code."""
    return _r_code(digit)[::-1]


# --- Check-digit math -------------------------------------------------------

def _check_digit(data: str) -> int:
    """Compute the GS1 check digit for a data string (check digit excluded).

    The weights alternate 3, 1, 3, 1, ... counted from the RIGHT: the data
    digit immediately left of the check digit always has weight 3. This one
    universal rule yields the standard result for every format:
      * EAN-13 (12 data digits): 1,3,1,3,... left-to-right
      * EAN-8  ( 7 data digits): 3,1,3,1,3,1,3 left-to-right
      * UPC-A  (11 data digits): 3,1,3,1,...   left-to-right
    """
    total = 0
    n = len(data)
    for i, ch in enumerate(data):
        pos_from_right = n - 1 - i          # 0 for the rightmost digit
        weight = 3 if pos_from_right % 2 == 0 else 1
        total += int(ch) * weight
    return (10 - (total % 10)) % 10


def _validate(code: str) -> dict:
    """Detect format, compute the expected check digit, and compare.

    Returns a dict with the format, the data portion, the correct check
    digit, the digit present in the code, and the validity flag.
    """
    fmt = FORMATS[len(code)]
    data = code[:-1]                 # all digits except the check digit
    given = int(code[-1])            # the check digit written in the code
    expected = _check_digit(data)    # the mathematically correct check digit
    return {
        "format": fmt,
        "code": code,
        "data": data,
        "valid": given == expected,
        "check_digit": expected,
        "given_check_digit": given,
    }


# --- Binary encoding --------------------------------------------------------

def _encode_binary(code: str, fmt: str) -> str:
    """Build the full binary module string for a barcode.

    Layout for all three formats is: start guard, left digit groups, center
    guard, right digit groups, end guard. EAN-13 differs only in that its six
    left digits use the L/G parity pattern selected by the first digit.
    """
    if fmt == "EAN-13":
        first = int(code[0])                     # implicit digit -> L/G pattern
        parity = FIRST_DIGIT_PARITY[first]       # 6-char L/G sequence
        left = code[1:7]                         # 6 left data digits
        right = code[7:13]                       # 6 right data digits
        left_bits = "".join(
            L_CODES[int(d)] if p == "L" else _g_code(int(d))
            for d, p in zip(left, parity)
        )
        right_bits = "".join(_r_code(int(d)) for d in right)
    elif fmt == "UPC-A":
        left = code[0:6]                         # 6 left digits, all L-code
        right = code[6:12]                       # 6 right digits, all R-code
        left_bits = "".join(L_CODES[int(d)] for d in left)
        right_bits = "".join(_r_code(int(d)) for d in right)
    else:  # EAN-8
        left = code[0:4]                         # 4 left digits, L-code
        right = code[4:8]                        # 4 right digits, R-code
        left_bits = "".join(L_CODES[int(d)] for d in left)
        right_bits = "".join(_r_code(int(d)) for d in right)
    return GUARD_START + left_bits + GUARD_CENTER + right_bits + GUARD_START


# --- Rendering --------------------------------------------------------------

def _render_ascii(bits: str, height: int = 3) -> str:
    """Render the binary module string as ASCII art using '#' and space."""
    quiet = "  "  # two-space quiet zone on each side
    row = quiet + "".join("#" if b == "1" else " " for b in bits) + quiet
    return "\n".join([row] * height)  # repeat vertically for visibility


def _render_svg(bits: str, digits: str) -> str:
    """Render the binary module string as an SVG with correct bar widths.

    Consecutive '1' modules are merged into single black rectangles so each
    bar's width equals its run length in modules. A quiet zone is added on
    each side and the human-readable digits are printed beneath the bars.
    """
    module = 2             # pixels per module
    bar_height = 100       # pixels tall for the bars
    text_height = 24       # pixels reserved for the digits caption
    quiet = 9              # quiet-zone modules on each side
    total_modules = len(bits) + 2 * quiet
    width = total_modules * module
    height = bar_height + text_height

    # Merge consecutive '1' modules into single bars: list of (x, width).
    bars = []
    x = quiet * module
    i = 0
    while i < len(bits):
        if bits[i] == "1":
            j = i + 1
            while j < len(bits) and bits[j] == "1":
                j += 1
            bars.append((x, (j - i) * module))
            x += (j - i) * module
            i = j
        else:
            x += module
            i += 1

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d">' % (width, height, width, height),
        '<rect width="%d" height="%d" fill="#ffffff"/>' % (width, height),
    ]
    for bx, bw in bars:
        parts.append(
            '<rect x="%d" y="0" width="%d" height="%d" fill="#000000"/>'
            % (bx, bw, bar_height)
        )
    # Human-readable digits centered under the bars.
    parts.append(
        '<text x="%d" y="%d" font-family="monospace" font-size="%d" '
        'text-anchor="middle" fill="#000000">%s</text>'
        % (width // 2, bar_height + text_height - 6, 16, digits)
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _write_svg(path: str, content: str) -> str:
    """Write SVG content to `path`, creating parent directories if needed."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w") as fh:
        fh.write(content)
    return os.path.abspath(path)


# --- Output helpers ---------------------------------------------------------

def _emit_error(fmt: str, message: str) -> None:
    """Write an error message to stderr (as JSON when fmt == 'json')."""
    if fmt == "json":
        print(json.dumps({"error": message}), file=sys.stderr)
    else:
        print(message, file=sys.stderr)


# --- Subcommand handlers ----------------------------------------------------

def _cmd_check(args: argparse.Namespace) -> int:
    """`check CODE` — detect format by length and validate the check digit."""
    code = args.code.strip()

    # Reject non-numeric input.
    if not code:
        _emit_error(args.format, "Error: barcode is empty")
        return 1
    if not code.isdigit():
        _emit_error(
            args.format,
            "Error: barcode must be numeric, got %r" % args.code,
        )
        return 1
    # Reject unsupported lengths.
    if len(code) not in FORMATS:
        _emit_error(
            args.format,
            "Error: barcode length %d not supported "
            "(expected 8, 12, or 13 digits)" % len(code),
        )
        return 1

    info = _validate(code)

    # Emit the report in the requested format.
    if args.format == "json":
        print(json.dumps(info, indent=2))
    else:
        print("Format:       %s" % info["format"])
        print("Code:         %s" % info["code"])
        print("Valid:        %s" % ("yes" if info["valid"] else "no"))
        if info["valid"]:
            print("Check digit:  %d" % info["check_digit"])
        else:
            print("Check digit:  got %d, expected %d"
                  % (info["given_check_digit"], info["check_digit"]))

    # A failed check digit is an error: clear stderr message + nonzero exit.
    if not info["valid"]:
        _emit_error(
            args.format,
            "Error: %s check digit mismatch — got %d, expected %d"
            % (info["format"], info["given_check_digit"], info["check_digit"]),
        )
        return 1
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    """`generate CODE` — render a barcode as ASCII art and/or an SVG file."""
    code = args.code.strip()

    # Reject non-numeric input.
    if not code:
        _emit_error(args.format, "Error: barcode is empty")
        return 1
    if not code.isdigit():
        _emit_error(
            args.format,
            "Error: barcode must be numeric, got %r" % args.code,
        )
        return 1

    # Work out the format and whether a check digit must be computed.
    computed = False
    n = len(code)
    if n in FORMATS:
        # Full code: validate the existing check digit.
        fmt = FORMATS[n]
        info = _validate(code)
        if not info["valid"]:
            _emit_error(
                args.format,
                "Error: %s check digit mismatch — got %d, expected %d"
                % (fmt, info["given_check_digit"], info["check_digit"]),
            )
            return 1
        full = code
    elif n in DATA_ONLY_FORMATS:
        # Data only: append the correct check digit.
        fmt = DATA_ONLY_FORMATS[n]
        check = _check_digit(code)
        full = code + str(check)
        computed = True
    else:
        _emit_error(
            args.format,
            "Error: barcode length %d not supported "
            "(expected 7, 8, 11, 12, or 13 digits)" % len(code),
        )
        return 1

    # Build the binary encoding and the requested renderings.
    bits = _encode_binary(full, fmt)
    show_ascii = args.ascii or (args.svg is None)  # ASCII is the default
    ascii_art = _render_ascii(bits) if show_ascii else None
    svg_path = None
    if args.svg:
        svg_path = _write_svg(args.svg, _render_svg(bits, full))

    # Emit the report in the requested format.
    if args.format == "json":
        out = {
            "format": fmt,
            "code": full,
            "check_digit": int(full[-1]),
            "check_digit_computed": computed,
            "binary": bits,
            "modules": len(bits),
        }
        if ascii_art is not None:
            out["ascii"] = ascii_art
        if svg_path is not None:
            out["svg"] = svg_path
        print(json.dumps(out, indent=2))
    else:
        print("Format:       %s" % fmt)
        print("Code:         %s" % full)
        print("Check digit:  %d%s" % (int(full[-1]), " (computed)" if computed else ""))
        print("Modules:      %d" % len(bits))
        print("Binary:       %s" % bits)
        if ascii_art is not None:
            print("ASCII:")
            print(ascii_art)
        if svg_path is not None:
            print("SVG:          %s" % svg_path)

    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    """`list` — print the L/G/R 7-bit encodings for digits 0-9."""
    rows = [
        {"digit": d, "L": L_CODES[d], "G": _g_code(d), "R": _r_code(d)}
        for d in range(10)
    ]
    if args.format == "json":
        print(json.dumps(rows, indent=2))
    else:
        print("Digit  L-code     G-code     R-code")
        print("-----  -------    -------    -------")
        for r in rows:
            print("  %d    %s   %s   %s" % (r["digit"], r["L"], r["G"], r["R"]))
    return 0


# --- CLI plumbing -----------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser with a shared --format parent parser.

    `--format` uses default=argparse.SUPPRESS and is attached to BOTH the
    top-level parser and every subparser, so it works before AND after the
    subcommand. The real "text" fallback is resolved in main().
    """
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--format",
        choices=["text", "json"],
        default=argparse.SUPPRESS,
        help="Output format: text or json (default: text)",
    )

    p = argparse.ArgumentParser(
        prog="Bar_Code",
        description=_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
    )
    sub = p.add_subparsers(dest="command", required=True)

    # check CODE
    sp_check = sub.add_parser(
        "check", parents=[common],
        help="Validate a barcode's check digit (8=EAN-8, 12=UPC-A, 13=EAN-13)",
    )
    sp_check.add_argument("code", help="Numeric barcode digits")
    sp_check.set_defaults(func=_cmd_check)

    # generate CODE [--ascii] [--svg FILE]
    sp_gen = sub.add_parser(
        "generate", parents=[common],
        help="Render a barcode as ASCII art and/or an SVG file",
    )
    sp_gen.add_argument(
        "code",
        help="Numeric digits (full code, or data without check digit: "
             "7=>EAN-8, 11=>UPC-A)",
    )
    sp_gen.add_argument(
        "--ascii", action="store_true",
        help="Print ASCII art to stdout (also the default when no --svg)",
    )
    sp_gen.add_argument(
        "--svg", metavar="FILE",
        help="Write the barcode to FILE as SVG",
    )
    sp_gen.set_defaults(func=_cmd_generate)

    # list
    sp_list = sub.add_parser(
        "list", parents=[common],
        help="List the L/G/R 7-bit encodings for digits 0-9",
    )
    sp_list.set_defaults(func=_cmd_list)

    return p


def main(argv=None) -> int:
    """Parse arguments once, resolve the --format fallback, dispatch."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    args.format = getattr(args, "format", None) or "text"  # SUPPRESS fallback
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
