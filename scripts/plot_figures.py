#!/usr/bin/env python3
"""Draw the two-panel frontier/profile illustration with optional Matplotlib.

Run: python scripts/plot_figures.py [--font-file path/to/LinLibertine_R.otf]
Linux Libertine O matches acmart. Installed-font and kpsewhich lookup are used
when --font-file is absent. CFF fonts are converted to TrueType outlines in
temporary files for correct Type-42 embedding; no font is redistributed.
This script runs no scientific workflow. The five frontier points are exact
four-layer chain outcomes; the four crosses are illustrative, not outcomes.
Native output: figures/frontier-duality.pdf, 350 x 106 PDF points. A sibling
paper/figures receives identical bytes when present.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import shutil
import subprocess
import tempfile

import matplotlib as mpl
mpl.use("Agg")
from matplotlib import font_manager as fm
from matplotlib import pyplot as plt
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
FONT_CACHE = tempfile.TemporaryDirectory(prefix="figure-fonts-", ignore_cleanup_errors=True)


def register_font(path: Path) -> Path:
    """Give the PDF Type-42 backend TrueType outlines, retaining the same face.

    TeX's Libertine OTF has CFF outlines. Convert those outlines to quadratic
    curves within one font unit in a temporary file, not a shipped font asset.
    Direct CFF embedding as CIDFontType2 can leave invisible PDF text.
    """
    font = TTFont(path)
    if "CFF " in font:
        glyph_set = font.getGlyphSet()
        glyphs = {}
        for name in font.getGlyphOrder():
            pen = TTGlyphPen(None)
            glyph_set[name].draw(Cu2QuPen(pen, max_err=1.0, reverse_direction=True))
            glyphs[name] = pen.glyph()
        del font["CFF "]
        font.sfntVersion = "\x00\x01\x00\x00"
        builder = FontBuilder(font=font, isTTF=True)
        builder.isTTF = True
        builder.setupGlyf(glyphs)
        builder.setupMaxp()
        converted = Path(FONT_CACHE.name) / (path.stem + ".ttf")
        font.save(converted)
        path = converted
    fm.fontManager.addfont(str(path))
    return path


def configure_font(path: Path | None) -> str:
    if path is None:
        try:
            path = Path(fm.findfont("Linux Libertine O", fallback_to_default=False))
        except ValueError:
            lookup = shutil.which("kpsewhich")
            found = subprocess.check_output([lookup, "LinLibertine_R.otf"], text=True).strip() if lookup else ""
            if not found:
                raise SystemExit("Install Linux Libertine O or supply --font-file LinLibertine_R.otf")
            path = Path(found)
    if not path.is_file():
        raise FileNotFoundError(path)
    regular = register_font(path)
    for name in ("LinLibertine_RI.otf", "LinLibertine_RB.otf"):
        companion = path.with_name(name)
        if companion.is_file():
            register_font(companion)
    family = fm.FontProperties(fname=str(regular)).get_name()
    mpl.rcParams.update({
        "font.family": family, "font.size": 8, "mathtext.fontset": "custom",
        "mathtext.rm": family, "mathtext.it": f"{family}:italic",
        "mathtext.bf": f"{family}:bold", "mathtext.fallback": "cm",
        "pdf.fonttype": 42, "pdf.use14corefonts": False, "text.usetex": False,
        "axes.unicode_minus": False, "axes.linewidth": .5,
        "path.simplify": False,
    })
    return family


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-file", type=Path)
    args = parser.parse_args()
    family = configure_font(args.font_file)
    mpl.rcParams["font.size"] = 9
    gas = [0, 1, 2, 3, 4]
    cost = [4, 3, 2, 1, 0]
    dominated_gas = [1, 2, 3, 4]
    dominated_cost = [4, 4, 3, 2]
    fig = plt.figure(figsize=(350 / 72, 106 / 72))
    axes = [fig.add_axes([left / 350, 25 / 106, 140 / 350, 77 / 106])
            for left in (26, 206)]
    for ax in axes:
        ax.set(xlim=(-.3, 4.3), ylim=(-.3, 4.8))
        ax.set_xticks(gas)
        ax.set_yticks(gas)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(length=2, width=.5, pad=2)
    axes[0].set(xlabel=r"gas used $r$", ylabel=r"cost $c$")
    axes[0].plot(gas, cost, "o", color="black", ms=3.6)
    axes[0].plot(dominated_gas, dominated_cost, "x", color=".55", ms=5, mew=.7)
    axes[0].annotate("", xy=(1, 3), xytext=(1, 4),
                     arrowprops={"arrowstyle": "-|>", "lw": .6, "color": "black",
                                 "shrinkA": 0, "shrinkB": 0, "mutation_scale": 6})
    axes[1].set(xlabel=r"available gas $g$", ylabel=r"$V(g)$")
    # Same const-plot/post convention as the source: no extrapolation past g=4.
    axes[1].step(gas, cost, where="post", color="black", lw=.6)
    axes[1].plot(gas, cost, "o", color="black", ms=3)
    output = ROOT / "figures/frontier-duality.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, metadata={"Creator": None, "Producer": None, "CreationDate": None, "ModDate": None})
    plt.close(fig)
    paper = ROOT.parent / "paper/figures"
    if paper.is_dir():
        shutil.copyfile(output, paper / output.name)
    print(f"frontier-duality: 2 panels, 5 outcomes, 4 illustrative crosses, post steps; embedded {family}")


if __name__ == "__main__":
    main()
