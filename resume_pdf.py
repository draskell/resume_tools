"""Local, content-preserving Markdown resume rendering."""

import argparse
from dataclasses import dataclass
from functools import lru_cache, partial
from html import escape
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit

from markdown_it import MarkdownIt
from markdown_it.token import Token
import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont, TTFError
from reportlab.platypus import Paragraph, SimpleDocTemplate
from reportlab.platypus.doctemplate import LayoutError


ASSETS_DIR = Path(__file__).resolve().parent / "assets"
INTER_FONT_DIR = Path(__file__).resolve().parent / "fonts" / "inter"
FONT_NAME = "ResumeVera"


@dataclass(frozen=True)
class Theme:
    font_name: str
    accent: str
    text_color: str = "#000000"
    bullet: str = "\u2022"
    section_accent: str | None = None


THEMES = {
    "basic": Theme(FONT_NAME, "#18344A"),
    "developer": Theme(
        "Courier", "#1D4ED8", "#24292F", bullet="-", section_accent="#0F766E"
    ),
    "discord": Theme("ResumeInter", "#5865F2"),
}


class ConversionError(ValueError):
    """An input cannot be converted without losing content."""


def get_theme(name: str) -> Theme:
    if name not in THEMES:
        raise ConversionError(f"Unknown theme {name!r}; choose from {', '.join(THEMES)}.")
    return THEMES[name]


@lru_cache(maxsize=len(THEMES))
def register_fonts(theme: str = "basic") -> frozenset[int]:
    selected = get_theme(theme)
    if selected.font_name == "Courier":
        pdfmetrics.registerFontFamily(
            "Courier",
            normal="Courier",
            bold="Courier-Bold",
            italic="Courier-Oblique",
            boldItalic="Courier-BoldOblique",
        )
        font = pdfmetrics.getFont("Courier")
        courier_coverage = set()
        for code in range(32, 256):
            if font.encoding.vector[code] is None:
                continue
            try:
                char = bytes([code]).decode("cp1252")
            except UnicodeDecodeError:
                continue
            courier_coverage.add(ord(char))
        return frozenset(courier_coverage)
    if selected.font_name == "ResumeInter":
        directory = INTER_FONT_DIR
        faces = (
            ("", "Inter-Regular.ttf"),
            ("-Bold", "Inter-Bold.ttf"),
            ("-Italic", "Inter-Italic.ttf"),
            ("-BoldItalic", "Inter-BoldItalic.ttf"),
        )
    else:
        directory = Path(reportlab.__file__).parent / "fonts"
        faces = (
            ("", "Vera.ttf"),
            ("-Bold", "VeraBd.ttf"),
            ("-Italic", "VeraIt.ttf"),
            ("-BoldItalic", "VeraBI.ttf"),
        )
    coverage = []
    for suffix, filename in faces:
        path = directory / filename
        if not path.is_file():
            raise ConversionError(
                f"Missing theme font: {path}. Restore the project's bundled fonts "
                "or reinstall its locked dependencies."
            )
        try:
            font = TTFont(selected.font_name + suffix, str(path))
        except TTFError as error:
            raise ConversionError(f"Cannot load theme font {path}: {error}") from error
        pdfmetrics.registerFont(font)
        coverage.append(set(font.face.charToGlyph))
    pdfmetrics.registerFontFamily(
        selected.font_name,
        normal=selected.font_name,
        bold=selected.font_name + "-Bold",
        italic=selected.font_name + "-Italic",
        boldItalic=selected.font_name + "-BoldItalic",
    )
    return frozenset.intersection(*(frozenset(chars) for chars in coverage))


def escaped_text(text: str, theme: str = "basic") -> str:
    coverage = register_fonts(theme)
    result = []
    for char in text:
        if char == "\u2192":
            # Symbol covers the arrow absent from the main theme fonts.
            result.append('<font name="Symbol">\u2192</font>')
        elif ord(char) in coverage and (char.isprintable() or char in "\n\t"):
            result.append(escape(char))
        else:
            raise ConversionError(
                f"Unsupported character {char!r} (U+{ord(char):04X}); "
                "use a supported spelling or extend the font coverage."
            )
    return "".join(result)


def inline_markup(token: Token, theme: str = "basic") -> str:
    selected = get_theme(theme)
    result = []
    tags = {
        "strong_open": "<b>",
        "strong_close": "</b>",
        "em_open": "<i>",
        "em_close": "</i>",
        "link_close": "</link>",
        "softbreak": " ",
        "hardbreak": "<br/>",
    }
    for child in token.children or []:
        if child.type == "text":
            result.append(escaped_text(child.content, theme))
        elif child.type == "link_open":
            href = child.attrGet("href") or ""
            if urlsplit(href).scheme.lower() not in {"http", "https", "mailto"}:
                raise ConversionError(
                    f"Unsupported link destination {href!r}; use http, https, or mailto."
                )
            result.append(
                f'<link href="{escape(href, quote=True)}" color="{selected.accent}">'
            )
        elif child.type in tags:
            result.append(tags[child.type])
        else:
            raise ConversionError(f"Unsupported Markdown inline content: {child.type}.")
    return "".join(result)


def make_styles(theme: str = "basic") -> dict[str, ParagraphStyle]:
    selected = get_theme(theme)
    register_fonts(theme)
    body = ParagraphStyle(
        "Body",
        fontName=selected.font_name,
        textColor=colors.HexColor(selected.text_color),
        fontSize=9.3,
        leading=11.8,
        spaceAfter=4,
        allowWidows=0,
        allowOrphans=0,
    )
    styles = {"body": body}
    for level in range(1, 7):
        heading_color = selected.accent if level <= 2 else selected.text_color
        if level == 2 and selected.section_accent:
            heading_color = selected.section_accent
        styles[f"h{level}"] = ParagraphStyle(
            f"Heading{level}",
            parent=body,
            fontName=selected.font_name + "-Bold",
            fontSize=18 if level == 1 else 11 if level == 2 else 10,
            leading=22 if level == 1 else 14 if level == 2 else 12.5,
            textColor=colors.HexColor(heading_color),
            spaceBefore=0 if level == 1 else 8 if level == 2 else 4,
            spaceAfter=5 if level <= 2 else 2,
            keepWithNext=True,
        )
    return styles


def markdown_story(markdown: str, theme: str = "basic") -> list[Paragraph]:
    selected = get_theme(theme)
    if not markdown.strip():
        raise ConversionError("The Markdown document is empty.")
    # Enable table recognition so unsupported tables fail instead of becoming prose.
    parser = MarkdownIt("commonmark").enable("table")
    # Tokenize unsafe destinations too, so our scheme check rejects them explicitly.
    parser.validateLink = lambda _url: True
    tokens = parser.parse(markdown)
    styles = make_styles(theme)
    story = []
    list_items: list[bool] = []
    list_depth = 0
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.type == "bullet_list_open":
            list_depth += 1
        elif token.type == "bullet_list_close":
            list_depth -= 1
        elif token.type == "list_item_open":
            list_items.append(True)
        elif token.type == "list_item_close":
            list_items.pop()
        elif token.type in {"heading_open", "paragraph_open"}:
            inline = tokens[index + 1]
            if inline.type != "inline":
                raise ConversionError(f"Unsupported Markdown after {token.type}.")
            markup = inline_markup(inline, theme)
            if not markup.strip():
                index += 3
                continue
            style = styles[token.tag if token.type == "heading_open" else "body"]
            bullet = None
            if list_depth:
                first = list_items[-1]
                bullet = selected.bullet if first else None
                style = ParagraphStyle(
                    "ListParagraph",
                    parent=style,
                    leftIndent=list_depth * 12,
                    bulletIndent=list_depth * 12 - 10,
                    bulletFontName=selected.font_name,
                    bulletFontSize=9.3,
                    spaceAfter=3,
                )
                list_items[-1] = False
            elif (
                token.type == "paragraph_open"
                and len(story) > 0
                and story[-1].style.name == "Heading3"
            ):
                style = ParagraphStyle("Role", parent=style, keepWithNext=True)
            story.append(Paragraph(markup, style, bulletText=bullet))
            index += 3
            continue
        else:
            raise ConversionError(f"Unsupported Markdown block: {token.type}.")
        index += 1
    if not story:
        raise ConversionError("The Markdown document contains no renderable text.")
    return story


def footer(canvas, document, *, theme: str = "basic") -> None:
    canvas.saveState()
    canvas.setFont(get_theme(theme).font_name, 8)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawRightString(letter[0] - 0.5 * inch, 0.28 * inch, str(document.page))
    canvas.restoreState()


def render_pdf(
    markdown: str, destination: Path, title: str = "Resume", *, theme: str = "basic"
) -> None:
    story = markdown_story(markdown, theme)
    document = SimpleDocTemplate(
        str(destination),
        pagesize=letter,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.4 * inch,
        bottomMargin=0.45 * inch,
        title=title,
        author="",
    )
    themed_footer = partial(footer, theme=theme)
    document.build(story, onFirstPage=themed_footer, onLaterPages=themed_footer)


def discover_resumes(directory: Path) -> list[Path]:
    return sorted(
        path for path in directory.rglob("*.md")
        if path.is_file()
        and (path.name == "resume.md" or path.name.endswith("_resume.md"))
    )


def convert_files(
    jobs: list[tuple[Path, Path]], *, force: bool = False, theme: str = "basic"
) -> None:
    get_theme(theme)
    if not jobs:
        raise ConversionError("No resumes found under assets/.")
    prepared = []
    destinations: set[Path] = set()
    for source, destination in jobs:
        if source.suffix.lower() != ".md":
            raise ConversionError(f"Input must be a Markdown (.md) file: {source}")
        if destination.suffix.lower() != ".pdf":
            raise ConversionError(f"Output must be a PDF (.pdf) file: {destination}")
        if destination.resolve() in destinations:
            raise ConversionError(f"Multiple inputs target the same output: {destination}")
        destinations.add(destination.resolve())
        if os.path.lexists(destination) and not force:
            raise ConversionError(f"PDF already exists: {destination}. Use --force to replace it.")
        if destination.is_dir():
            raise ConversionError(f"Output is a directory: {destination}")
        markdown = source.read_text(encoding="utf-8")
        try:
            markdown_story(markdown, theme)
        except ConversionError as error:
            raise ConversionError(f"{source}: {error}") from error
        prepared.append((source, destination, markdown))

    staged: list[tuple[Path, Path]] = []
    try:
        # Stage every render before publishing any output, including in batch mode.
        for source, destination, markdown in prepared:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                prefix=f".{destination.stem}-",
                suffix=".pdf",
                dir=destination.parent,
                delete=False,
            ) as output:
                temporary = Path(output.name)
            staged.append((temporary, destination))
            render_pdf(markdown, temporary, title=source.stem, theme=theme)
        for temporary, destination in staged:
            if force:
                os.replace(temporary, destination)
            else:
                # Atomic no-clobber publication also protects against concurrent writers.
                os.link(temporary, destination)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, help="Markdown resume to convert")
    parser.add_argument("--all", action="store_true", help="Convert all resumes under assets/")
    parser.add_argument("--output", type=Path, help="Output PDF path (single-file mode only)")
    parser.add_argument("--force", action="store_true", help="Replace existing output PDFs")
    parser.add_argument(
        "--theme",
        choices=THEMES,
        default="basic",
        help="basic: compact sans-serif (default); developer: blue/teal monospace; "
        "discord: Inter with blurple accents",
    )
    args = parser.parse_args(argv)
    if (args.input is not None) == args.all:
        parser.error("Provide one Markdown input or --all, but not both.")
    if args.all and args.output:
        parser.error("--output is only available for single-file conversion.")
    try:
        suffix = ".pdf" if args.theme == "basic" else f".{args.theme}.pdf"
        if args.all:
            jobs = [(path, path.with_suffix(suffix)) for path in discover_resumes(ASSETS_DIR)]
        else:
            jobs = [(args.input, args.output or args.input.with_suffix(suffix))]
        convert_files(jobs, force=args.force, theme=args.theme)
    except (OSError, UnicodeError, ValueError, LayoutError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for _, destination in jobs:
        print(f"Saved: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
