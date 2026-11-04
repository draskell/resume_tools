from pathlib import Path
import re
import subprocess
import sys

from pypdf import PdfReader
import pytest

import resume_pdf as converter


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = """# Example Person

person@example.com | Example City, ST

## Experience

### Example Employer

**Senior Data Engineer | 2021–Present**

- Built **Python** pipelines → analytics — improved *reliability*.
- Used R&D data with <5 errors and >99% uptime.
- [Portfolio](https://example.com/work?a=1&b=2)
"""


def pdf_text(path):
    return "\n".join(page.extract_text() for page in PdfReader(path).pages)


def write_source(path, text=SAMPLE):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize("theme", converter.THEMES)
def test_render_content_unicode_links_and_page_size(tmp_path, theme):
    source = write_source(tmp_path / "resume.md")
    output = tmp_path / "resume.pdf"
    converter.convert_files([(source, output)], theme=theme)
    reader = PdfReader(output)
    text = pdf_text(output)
    assert "\x7f" not in text
    for expected in (
        "Example Person", "person@example.com", "Example Employer",
        "Senior Data Engineer | 2021–Present",
        "Python", "→", "—", "reliability", "R&D", "<5", ">99%", "Portfolio",
    ):
        assert expected in text
    assert tuple(reader.pages[0].mediabox)[2:] == (612, 792)
    footer_positions = []

    def collect_footer(text, cm, tm, font, size):
        if text.strip() == "1":
            footer_positions.append(tm[5])

    reader.pages[0].extract_text(visitor_text=collect_footer)
    assert footer_positions and all(y < 30 for y in footer_positions)
    links = [
        annotation.get_object()["/A"]["/URI"]
        for annotation in reader.pages[0]["/Annots"]
    ]
    assert links == ["https://example.com/work?a=1&b=2"]
    assert source.read_text() == SAMPLE


def test_bold_italic_and_escaped_markup():
    story = converter.markdown_story(r"**Bold** *italic* ***both*** & \<literal>")
    assert "<b>Bold</b>" in story[0].text
    assert "<i>italic</i>" in story[0].text
    assert "&amp;" in story[0].text
    assert "&lt;literal&gt;" in story[0].text
    fonts = {fragment.fontName for fragment in story[0].frags}
    assert converter.FONT_NAME + "-Bold" in fonts
    assert converter.FONT_NAME + "-Italic" in fonts
    assert converter.FONT_NAME + "-BoldItalic" in fonts


@pytest.mark.parametrize("markdown", [
    "```python\nprint('hello')\n```",
    "    code block",
    "> quotation",
    "<div>HTML</div>",
    "hello <b>HTML</b>",
    "![photo](photo.png)",
    "1. numbered",
    "inline `code`",
    "---",
    "| a | b |\n| --- | --- |\n| x | y |",
    "[file](file:///tmp/private)",
    "[unsafe](javascript:alert)",
    "[relative](../document)",
])
def test_reject_unsupported_content(markdown):
    with pytest.raises(converter.ConversionError, match="Unsupported"):
        converter.markdown_story(markdown)


@pytest.mark.parametrize("markdown", ["", " \n\n", "[unused]: https://example.com"])
def test_reject_empty_document(markdown):
    with pytest.raises(converter.ConversionError, match="empty|no renderable"):
        converter.markdown_story(markdown)


def test_reject_uncovered_character():
    with pytest.raises(converter.ConversionError, match=r"U\+1F680"):
        converter.markdown_story("Rocket \U0001f680")


def test_nested_lists_and_breaks(tmp_path):
    output = tmp_path / "nested.pdf"
    converter.render_pdf(
        "# Name\n\nFirst  \nSecond\n\n- Parent\n  - Child\n\n  Continuation\n",
        output,
    )
    text = pdf_text(output)
    assert "First\nSecond" in text
    for expected in ("Parent", "Child", "Continuation"):
        assert expected in text


def test_pagination_keeps_employer_and_role_with_first_bullet(tmp_path):
    markdown = "# Person\n\n## Experience\n\n"
    for i in range(35):
        markdown += (
            f"### Employer{i}\n\n**Role{i} | 2020–2021**\n\n"
            f"- Achievement{i}: " + "Built reliable data systems. " * 10 + "\n\n"
        )
    output = tmp_path / "pages.pdf"
    converter.render_pdf(markdown, output)
    pages = [page.extract_text() for page in PdfReader(output).pages]
    assert len(pages) > 2
    for i in range(35):
        page = next(text for text in pages if f"Employer{i}\n" in text)
        assert f"Role{i} |" in page
        assert f"Achievement{i}:" in page


def test_discovery_recurses_and_excludes_non_resumes(tmp_path):
    expected = [
        write_source(tmp_path / "a-company" / "resume.md"),
        write_source(tmp_path / "b-company" / "role" / "resume.md"),
        write_source(tmp_path / "discord" / "20261103_discord_staff_data_engineer_resume.md"),
        write_source(tmp_path / "general" / "20261103_updated_resume.md"),
    ]
    for filename in (
        "experience.md", "README.md", "AGENTS.md", "a-company/job-description.md",
        "b-company/role/job-description.md", ".github/skills/tailor-resume/SKILL.md",
    ):
        write_source(tmp_path / filename)
    assert converter.discover_resumes(tmp_path) == expected


def test_main_single_file_and_explicit_output(tmp_path, capsys):
    source = write_source(tmp_path / "input.md")
    output = tmp_path / "previews" / "custom.pdf"
    assert converter.main([str(source), "--output", str(output)]) == 0
    assert output.is_file()
    assert not source.with_suffix(".pdf").exists()
    assert str(output) in capsys.readouterr().out


def test_main_batch(tmp_path, monkeypatch):
    assets = tmp_path / "assets"
    monkeypatch.setattr(converter, "ASSETS_DIR", assets)
    source = write_source(assets / "one" / "resume.md")
    second = write_source(assets / "two" / "role" / "resume.md")
    jd = write_source(assets / "one" / "job-description.md", "# JD\n\nRequirements")
    assert converter.main(["--all"]) == 0
    assert source.with_suffix(".pdf").exists()
    assert second.with_suffix(".pdf").exists()
    assert not jd.with_suffix(".pdf").exists()


def test_existing_pdf_requires_force(tmp_path, capsys):
    source = write_source(tmp_path / "resume.md")
    output = source.with_suffix(".pdf")
    output.write_bytes(b"original")
    assert converter.main([str(source)]) == 1
    assert "--force" in capsys.readouterr().err
    assert output.read_bytes() == b"original"
    assert converter.main([str(source), "--force"]) == 0
    assert output.read_bytes().startswith(b"%PDF")


def test_batch_conflict_preflight_preserves_all_files(tmp_path):
    one = write_source(tmp_path / "a.md")
    two = write_source(tmp_path / "b.md")
    output = two.with_suffix(".pdf")
    output.write_bytes(b"keep")
    with pytest.raises(converter.ConversionError, match="--force"):
        converter.convert_files([(one, one.with_suffix(".pdf")), (two, output)])
    assert not one.with_suffix(".pdf").exists()
    assert output.read_bytes() == b"keep"


def test_invalid_batch_input_preflight(tmp_path):
    one = write_source(tmp_path / "a.md")
    two = write_source(tmp_path / "b.md", "> unsupported")
    with pytest.raises(converter.ConversionError, match="Unsupported"):
        converter.convert_files(
            [(one, one.with_suffix(".pdf")), (two, two.with_suffix(".pdf"))]
        )
    assert not one.with_suffix(".pdf").exists()


def test_render_failure_preserves_outputs_and_cleans_temps(tmp_path, monkeypatch):
    one = write_source(tmp_path / "a.md")
    two = write_source(tmp_path / "b.md")
    existing = one.with_suffix(".pdf")
    existing.write_bytes(b"original")
    real_render = converter.render_pdf

    def failing_render(markdown, path, title, *, theme="basic"):
        if title == "b":
            path.write_bytes(b"partial render")
            raise OSError("disk failure")
        real_render(markdown, path, title, theme=theme)

    monkeypatch.setattr(converter, "render_pdf", failing_render)
    with pytest.raises(OSError, match="disk failure"):
        converter.convert_files(
            [(one, existing), (two, two.with_suffix(".pdf"))], force=True
        )
    assert existing.read_bytes() == b"original"
    assert not two.with_suffix(".pdf").exists()
    assert not list(tmp_path.glob(".*.pdf"))


def test_concurrent_writer_not_overwritten(tmp_path, monkeypatch):
    source = write_source(tmp_path / "resume.md")
    output = source.with_suffix(".pdf")
    real_render = converter.render_pdf

    def concurrent_render(markdown, path, title, *, theme="basic"):
        real_render(markdown, path, title, theme=theme)
        output.write_bytes(b"another writer")

    monkeypatch.setattr(converter, "render_pdf", concurrent_render)
    with pytest.raises(FileExistsError):
        converter.convert_files([(source, output)])
    assert output.read_bytes() == b"another writer"
    assert not list(tmp_path.glob(".*.pdf"))


@pytest.mark.parametrize("argv", [
    [], ["--all", "resume.md"], ["--all", "--output", "result.pdf"],
])
def test_argument_errors(argv):
    with pytest.raises(SystemExit) as error:
        converter.main(argv)
    assert error.value.code == 2


def test_missing_empty_batch_and_bad_paths(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(converter, "ASSETS_DIR", tmp_path)
    assert converter.main(["--all"]) == 1
    assert "No resumes" in capsys.readouterr().err
    assert converter.main([str(tmp_path / "missing.md")]) == 1
    assert "missing.md" in capsys.readouterr().err
    bad_extension = write_source(tmp_path / "resume.txt")
    assert converter.main([str(bad_extension)]) == 1
    assert "Markdown" in capsys.readouterr().err
    source = write_source(tmp_path / "resume.md")
    assert converter.main([str(source), "--output", str(source), "--force"]) == 1
    assert source.read_text() == SAMPLE
    assert "PDF" in capsys.readouterr().err


def test_duplicate_destination_rejected(tmp_path):
    one = write_source(tmp_path / "a.md")
    two = write_source(tmp_path / "b.md")
    with pytest.raises(converter.ConversionError, match="same output"):
        converter.convert_files([(one, tmp_path / "same.pdf"), (two, tmp_path / "same.pdf")])


def test_cli_subprocess(tmp_path):
    source = write_source(tmp_path / "resume.md")
    result = subprocess.run(
        [sys.executable, str(ROOT / "resume_pdf.py"), str(source)],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert source.with_suffix(".pdf").is_file()
    assert "Saved:" in result.stdout


@pytest.mark.parametrize("source", converter.discover_resumes(ROOT / "assets"))
def test_real_resumes_have_canonical_contact_headers(source):
    contact_section = (ROOT / "experience.md").read_text().split("## Contact\n\n", 1)[1]
    name, contact = contact_section.split("\n\n")[:2]
    assert source.read_text().startswith(f"# {name}\n\n{contact}\n\n")
    plain_contact = converter.markdown_story(contact)[0].getPlainText()
    reader = PdfReader(source.with_suffix(".pdf"))
    assert reader.pages[0].extract_text().splitlines()[:3] == ["1", name, plain_contact]


@pytest.mark.parametrize("theme", converter.THEMES)
@pytest.mark.parametrize("source", converter.discover_resumes(ROOT / "assets"))
def test_real_resumes_preserve_all_inline_text(source, tmp_path, theme):
    markdown = source.read_text()
    output = tmp_path / source.with_suffix(".pdf").name
    converter.render_pdf(markdown, output, theme=theme)
    assert len(PdfReader(output).pages) == 2
    text = " ".join(pdf_text(output).split())
    from markdown_it import MarkdownIt

    for token in MarkdownIt().parse(markdown):
        if token.type != "inline":
            continue
        plain = "".join(
            child.content if child.type in {"text", "code_inline"} else " "
            if child.type in {"softbreak", "hardbreak"} else ""
            for child in token.children or []
        )
        assert " ".join(plain.split()) in text


def test_skill_metadata_and_workflow_contract():
    for name in ("tailor-resume", "render-resume-pdf"):
        skill = (ROOT / ".github" / "skills" / name / "SKILL.md").read_text()
        assert skill.startswith(f"---\nname: {name}\ndescription:")
        assert "\n---\n" in skill
    tailor = (ROOT / ".github/skills/tailor-resume/SKILL.md").read_text()
    for required in ("experience.md", "job-description.md", "resume.md", "untrusted",
                     "metrics", "subfolder", "Do not modify"):
        assert required in tailor


def test_tailoring_workflow_fixture_preserves_master_and_jd(tmp_path, monkeypatch):
    master_path = write_source(
        tmp_path / "experience.md",
        "# Fixture Experience\n\n"
        "### Example Healthcare\n\n"
        "**Senior Data Engineer | 2020-2022**\n\n"
        "- Technical lead for a data platform supporting analytics; mentored engineers. [H1]\n"
        "- Led dbt adoption and data testing. [H1]\n"
        "- Designed and delivered a warehouse using S3, Airflow, and Snowflake. [H1]\n",
    )
    original_master = master_path.read_bytes()
    master = original_master.decode()
    assets = tmp_path / "assets"
    application = assets / "fixture-company"
    jd_text = (
        "# Fixture Company - Senior Data Engineer\n\n"
        "Build clinical trial data platforms using Python, SQL, dbt, Airflow, "
        "and Snowflake. Mentor engineers. GraphQL experience preferred.\n"
    )
    jd = write_source(application / "job-description.md", jd_text)
    prefixes = (
        "- Technical lead for a data platform",
        "- Led dbt adoption",
        "- Designed and delivered a warehouse",
    )
    selected = []
    for prefix in prefixes:
        line = next(line for line in master.splitlines() if line.startswith(prefix))
        selected.append(re.sub(r"\s+\[[^\]]+\]", "", line))
    tailored = (
        "# Fixture Person\n\n## Technical Skills\n\n"
        "Python | SQL | dbt | Airflow | Snowflake\n\n"
        "## Professional Experience\n\n### Example Healthcare\n\n"
        "**Senior Data Engineer | 2020-2022**\n\n"
        + "\n".join(selected) + "\n"
    )
    resume = write_source(application / "resume.md", tailored)
    monkeypatch.setattr(converter, "ASSETS_DIR", assets)
    assert converter.main(["--all"]) == 0
    text = " ".join(pdf_text(resume.with_suffix(".pdf")).split())
    for line in selected:
        assert line.removeprefix("- ") in text
    assert "GraphQL" not in text
    assert not re.search(r"\[H\d", tailored)
    assert not jd.with_suffix(".pdf").exists()
    assert jd.read_text() == jd_text
    assert master_path.read_bytes() == original_master


def test_basic_is_unchanged_default():
    default = converter.markdown_story(SAMPLE)
    explicit = converter.markdown_story(SAMPLE, "basic")
    for left, right in zip(default, explicit, strict=True):
        assert left.text == right.text
        for attr in (
            "fontName", "fontSize", "leading", "textColor", "spaceBefore",
            "spaceAfter", "keepWithNext", "leftIndent", "bulletFontName",
        ):
            assert getattr(left.style, attr, None) == getattr(right.style, attr, None)
    assert converter.make_styles()["body"].fontName == converter.FONT_NAME
    assert converter.make_styles()["body"].fontSize == 9.3
    assert converter.make_styles()["body"].leading == 11.8


def test_developer_uses_monospace_everywhere(tmp_path):
    source = SAMPLE.replace("*reliability*", "***reliability***")
    story = converter.markdown_story(source, "developer")
    assert all(paragraph.style.fontName.startswith("Courier") for paragraph in story)
    assert all(
        paragraph.style.bulletFontName == "Courier"
        for paragraph in story if paragraph.bulletText
    )
    assert all(
        paragraph.bulletText == "-" for paragraph in story if paragraph.bulletText
    )
    output = tmp_path / "developer.pdf"
    converter.render_pdf(source, output, theme="developer")
    reader = PdfReader(output)
    used_fonts = set()

    def collect_fonts(text, cm, tm, font, size):
        if text.strip() and font:
            used_fonts.add(str(font["/BaseFont"]))

    reader.pages[0].extract_text(visitor_text=collect_fonts)
    assert used_fonts <= {
        "/Courier", "/Courier-Bold", "/Courier-Oblique",
        "/Courier-BoldOblique", "/Symbol",
    }
    assert "/Courier-BoldOblique" in used_fonts
    assert "/Symbol" in used_fonts


def test_developer_outputs_are_separate_and_protected(tmp_path, capsys):
    source = write_source(tmp_path / "resume.md")
    basic = source.with_suffix(".pdf")
    basic.write_bytes(b"existing basic PDF")
    assert converter.main([str(source), "--theme", "developer"]) == 0
    output = source.with_suffix(".developer.pdf")
    assert output.is_file()
    assert basic.read_bytes() == b"existing basic PDF"
    saved = output.read_bytes()
    assert converter.main([str(source), "--theme", "developer"]) == 1
    assert "--force" in capsys.readouterr().err
    assert output.read_bytes() == saved
    assert converter.main([str(source), "--theme", "developer", "--force"]) == 0
    assert basic.read_bytes() == b"existing basic PDF"


def test_developer_batch_and_output_override(tmp_path, monkeypatch):
    assets = tmp_path / "assets"
    monkeypatch.setattr(converter, "ASSETS_DIR", assets)
    source = write_source(assets / "one" / "resume.md")
    second = write_source(assets / "two" / "role" / "resume.md")
    assert converter.main(["--all", "--theme", "developer"]) == 0
    for path in (source, second):
        assert path.with_suffix(".developer.pdf").is_file()
        assert not path.with_suffix(".pdf").exists()
    custom = tmp_path / "previews" / "custom.pdf"
    assert converter.main(
        [str(source), "--theme", "developer", "--output", str(custom)]
    ) == 0
    assert custom.is_file()


def test_theme_validation_rejects_unknown_name(tmp_path):
    source = write_source(tmp_path / "resume.md")
    with pytest.raises(SystemExit) as error:
        converter.main([str(source), "--theme", "unknown"])
    assert error.value.code == 2
    with pytest.raises(converter.ConversionError, match="Unknown theme"):
        converter.convert_files([(source, source.with_suffix(".pdf"))], theme="unknown")
    assert not source.with_suffix(".pdf").exists()


def test_developer_font_coverage_is_not_silently_substituted():
    with pytest.raises(converter.ConversionError, match="U\\+0141"):
        converter.markdown_story("Unsupported: \u0141", "developer")
    assert "\u2013" in converter.escaped_text("\u2013", "developer")
