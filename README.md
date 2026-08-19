# Bar_Code 🧾
![CI](https://github.com/realMNohgee/Bar_Code/actions/workflows/ci.yml/badge.svg) ![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg) ![License](https://img.shields.io/badge/license-MIT-blue.svg)

**Validate and render 1D barcodes — EAN-13, UPC-A, and EAN-8 — from the command line.** Zero dependencies, pure Python 3 standard library.

Bar_Code detects the barcode format from the digit length, checks the EAN/UPC check digit, and renders the full binary module encoding as ASCII art or a correct-bar-width SVG. It's a self-contained `Bar_Code.py` file you can drop anywhere and run with `python3`.

> Part of the **Trust & Reliability Layer for Agentic AI** — deterministic, inspectable utilities that give agents and pipelines verifiable ground truth (here: is this GTIN structurally valid, and exactly what does its barcode look like).

## Why it exists

Barcodes are everywhere — product GTINs, warehouse SKUs, shipping labels, library codes — but most people (and agents) treat them as opaque strings. A GTIN with a bad check digit will silently fail to scan, and hand-rolling the EAN L/G/R encoding is error-prone. Bar_Code gives you one deterministic tool to (1) *validate* a code's check digit and (2) *materialize* its exact barcode pattern, with `--format json` so an agent can call it as a subprocess and parse the result.

## One tool, many domains

| Domain | What Bar_Code does |
|---|---|
| 🛒 **Retail / E-commerce** | Validate product GTINs (EAN-13/UPC-A) before printing labels or listing products. |
| 📦 **Logistics / Warehousing** | Verify shipping-label barcodes and regenerate scannable SVG art for pick/pack. |
| 📚 **Library / Inventory** | Check EAN-8 codes on small items (books, media) and render shelf tags. |
| 🤖 **Agentic AI pipelines** | A deterministic subprocess a barcode-adjacent agent can shell out to for `--format json` ground truth. |
| 🧪 **QA / Test automation** | Assert check-digit integrity and exact module counts in test suites and CI gates. |

## Install

```bash
git clone git@github.com:realMNohgee/Bar_Code.git
cd Bar_Code
python3 Bar_Code.py --help
```

No `pip install`, no venv, no dependencies — just Python 3.

## Quick start

```bash
# Validate a barcode (exit 0 = valid, nonzero = invalid/bad input)
python3 Bar_Code.py check 4006381333931

# Validate a UPC-A and an EAN-8
python3 Bar_Code.py check 036000291452
python3 Bar_Code.py check 96385074

# Render an EAN-13 as ASCII art
python3 Bar_Code.py generate 4006381333931 --ascii

# Render to an SVG file with correct bar widths
python3 Bar_Code.py generate 4006381333931 --svg barcode.svg

# Auto-compute the check digit from data-only input (7 => EAN-8, 11 => UPC-A)
python3 Bar_Code.py generate 9638507 --ascii

# List the L/G/R encodings for digits 0-9
python3 Bar_Code.py list

# Machine-readable output (works before or after the subcommand)
python3 Bar_Code.py --format json check 4006381333931
python3 Bar_Code.py list --format json
```

### Example output

`check 4006381333931` →

```
Format:       EAN-13
Code:         4006381333931
Valid:        yes
Check digit:  1
```

`check 4006381333932` (wrong check digit) → exits `1`:

```
Format:       EAN-13
Code:         4006381333932
Valid:        no
Check digit:  got 2, expected 1
```

## Subcommands

| Command | What it does |
|---|---|
| `check CODE` | Detect format by length (8 → EAN-8, 12 → UPC-A, 13 → EAN-13), validate the check digit, report `valid/invalid` and the correct check digit. |
| `generate CODE [--ascii] [--svg FILE]` | Compute the full binary encoding and render it. ASCII art is the default; `--svg FILE` writes an SVG with correct bar widths. Accepts a full code (8/12/13 digits) or data without a check digit (7 → EAN-8, 11 → UPC-A). |
| `list` | List the L/G/R 7-bit encodings for digits 0-9. |

Every subcommand accepts `--format text|json` (before *or* after the subcommand).

## How it works

- **Check digit** — the GS1 algorithm: alternate weights `3, 1, 3, 1, …` counted from the right (the data digit immediately left of the check digit always has weight 3). This one rule is standard for EAN-8, UPC-A, and EAN-13.
- **Encoding** — EAN-13 uses the L-code and G-code tables on the left (L/G parity chosen by the first digit) and R-code on the right, wrapped in `101` start/end guards and a `01010` center guard (95 modules). UPC-A is 6×L + 6×R (95 modules); EAN-8 is 4×L + 4×R (67 modules).

## License

MIT — see [LICENSE](LICENSE).

---

🧰 **[Tool on Hermtica Marketplace](https://hermtica.com/marketplace)**
