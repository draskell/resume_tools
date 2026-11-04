from datetime import date
from pathlib import Path
import re
import shutil
import subprocess
import sys

from pypdf import PdfReader
from pypdf.generic import ContentStream
import pytest
from reportlab.lib.colors import HexColor

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
        write_source(tmp_path / "c-company" / "20260102_platform_engineer_resume.md"),
        write_source(tmp_path / "d-company" / "20260102_resume.md"),
    ]
    for filename in (
        "sources/experience.md", "README.md", "AGENTS.md", "a-company/job-description.md",
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


@pytest.mark.parametrize("theme", converter.THEMES)
def test_cli_subprocess(tmp_path, theme):
    source = write_source(tmp_path / "resume.md")
    result = subprocess.run(
        [sys.executable, str(ROOT / "resume_pdf.py"), str(source), "--theme", theme],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    suffix = ".pdf" if theme == "basic" else f".{theme}.pdf"
    assert source.with_suffix(suffix).is_file()
    assert "Saved:" in result.stdout


@pytest.mark.parametrize("source", converter.discover_resumes(ROOT / "assets"))
def test_real_resumes_have_canonical_contact_headers(source):
    master_path = ROOT / "sources" / "experience.md"
    contact_section = master_path.read_text().split("## Contact\n\n", 1)[1]
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
    for name in ("tailor-resume", "review-resume", "render-resume-pdf"):
        skill = (ROOT / ".github" / "skills" / name / "SKILL.md").read_text()
        assert skill.startswith(f"---\nname: {name}\ndescription:")
        assert "\n---\n" in skill
    tailor = (ROOT / ".github/skills/tailor-resume/SKILL.md").read_text()
    for required in ("sources/experience.md", "one-time", "highest/latest",
                     "job-description.md", "resume.md", "untrusted",
                     "metrics", "subfolder", "Do not modify"):
        assert required in tailor


@pytest.mark.parametrize("filename", [
    "AGENTS.md", "README.md", ".github/skills/tailor-resume/SKILL.md",
    ".github/skills/render-resume-pdf/SKILL.md",
])
def test_target_folder_generation_contract(filename):
    text = (ROOT / filename).read_text()
    for required in (
        "target folder", "YYYYMMDD_resume.md", "YYYYMMDD_resume.pdf",
        "--output", "two pages", "same-day", "previews/", "sibling",
    ):
        assert required in text
    assert "only" in text


@pytest.mark.parametrize("filename", [
    "AGENTS.md", "README.md", ".github/skills/tailor-resume/SKILL.md",
])
def test_job_independent_sources_and_folder_discovery_contract(filename):
    text = (ROOT / filename).read_text()
    for required in (
        "job-independent", "sources/provenance.md", "not an input to routine tailoring",
        "date +%Y%m%d", "immediate files", "*_jd.md", "multiple plausible JDs",
        "symlinks", "code edits",
    ):
        assert required in text
    assert "Render a PDF only when requested" not in text
    assert "Ask for PDF conversion separately" not in text
    assert "writes a supported, relevant `resume.md`" not in text


@pytest.mark.skipif(
    not (ROOT / "sources/experience.md").exists(),
    reason="Private source bank is not distributed",
)
def test_private_evidence_bank_has_no_application_paths_or_tailoring_policy():
    master = (ROOT / "sources/experience.md").read_text()
    assert "assets/" not in master
    assert "_jd.md" not in master
    assert "**Cloud-aware tailoring:**" not in master
    assert "**Tool naming:**" not in master
    assert "sources/provenance.md" in master
    ledger = (ROOT / "sources/provenance.md").read_text()
    for source_id in ("L1", "L2", "L3", "U1", *(f"H{i}" for i in range(1, 13))):
        assert f"**{source_id}:**" in ledger


@pytest.mark.parametrize("filename", [
    "AGENTS.md", "README.md",
    ".github/skills/tailor-resume/SKILL.md",
    ".github/skills/render-resume-pdf/SKILL.md",
])
def test_author_documentation_uses_integrated_master(filename):
    text = (ROOT / filename).read_text()
    assert "sources/experience.md" in text
    assert "one-time" in text
    assert "`experience.md`" not in text
    assert "resume_sources.py" not in text


def test_agent_instruction_skill_references_exist():
    instructions = (ROOT / "AGENTS.md").read_text()
    references = re.findall(r"`(\.github/skills/[^`]+/SKILL\.md)`", instructions)
    assert set(references) == {
        f".github/skills/{name}/SKILL.md"
        for name in ("tailor-resume", "review-resume", "render-resume-pdf")
    }
    assert all((ROOT / path).is_file() for path in references)


@pytest.mark.parametrize("filename", [
    "AGENTS.md", "README.md", ".github/skills/tailor-resume/SKILL.md",
])
def test_automatic_review_bounds_and_stopping_contract(filename):
    text = (ROOT / filename).read_text()
    for required in (
        "read-only", "3 reviewer passes", "2 revision cycles", "PASS", "FAIL",
        "substantive", "incomplete",
    ):
        assert required in text
    assert "automatic" in text.casefold()
    assert "stylistic" in text
    assert "current draft" in text


@pytest.mark.parametrize("filename", [
    "AGENTS.md", "README.md", ".github/skills/tailor-resume/SKILL.md",
])
def test_reviewer_model_selection_contract(filename):
    text = (ROOT / filename).read_text()
    for required in (
        "current session", "configured subagent model", "override",
        "reviewer model", "unavailable",
    ):
        assert required in text
    assert re.search(r"(?:Do not pin|No reviewer model is pinned)", text)
    assert re.search(r"silently (?:substitut|replac)", text)


@pytest.mark.parametrize("filename", [
    "AGENTS.md", "README.md", ".github/skills/tailor-resume/SKILL.md",
])
def test_cloud_aware_tailoring_preserves_historical_platforms(filename):
    text = (ROOT / filename).read_text()
    for required in (
        "Cloud-aware tailoring", "JD", "documented AWS", "AWS equivalent",
        "S3", "Airflow", "MWAA", "EMR", "Synapse", "Spark/distributed processing",
        "Never relabel a historical project from one cloud to another",
    ):
        assert required in text
    assert "when the JD is silent" in text or "not assumptions" in text or "rather than assumptions" in text


def test_reviewer_is_blind_read_only_and_returns_screening_rationale():
    review = (ROOT / ".github/skills/review-resume/SKILL.md").read_text()
    for required in (
        "independent, read-only hiring screener",
        "only candidate evidence is the complete supplied JD and current resume text",
        "Do not inspect other files", "Do not edit", "Do not delegate",
        "untrusted", "Verdict: PASS | FAIL", "Draft:", "Review round:",
        "Rationale:", "Requirements:", "Assessment: MET | PARTIAL | NOT_SHOWN",
        "Concerns:", "ID:", "Priority: BLOCKING | OPTIONAL", "Location:",
        "JD evidence:", "Resume evidence:", "Screening concern:",
        "Suggested improvement:", "Resolved:",
        "at least one blocking concern", "not the organization's actual ATS",
        "not demonstrated in this resume", "bonus-only gap",
        "Never change `FAIL` to `PASS`",
    ):
        assert required in review
    for forbidden in (
        "experience.md", "master", "source bank", "AGENTS.md", "tailor-resume",
        "ACCEPT", "REQUEST_CHANGES",
    ):
        assert forbidden not in review


def test_writer_loop_requires_blind_pass_and_private_factual_validation():
    tailor = (ROOT / ".github/skills/tailor-resume/SKILL.md").read_text()
    for required in (
        ".github/skills/review-resume/SKILL.md", "separate context",
        "Keep the saved draft stable", "Await the result before editing",
        "Reuse the same reviewer context/model", "Do not reset the budget",
        "ADDRESSED", "NOT_SUPPORTED", "actual revised draft",
        "author's factual checks find no substantive issues", "Stop immediately",
        "incomplete, not done", "unreviewed revision",
        "Missing evidence", "unavailable delegation",
        "only the complete JD and current resume text",
        "Do not send `AGENTS.md`", "its name/path", "no filesystem reads needed",
        "Never reuse a reviewer context that has seen those sources",
        "Do not send private evidence, source citations, or author comment dispositions",
        "Do not fabricate achievements", "Never modify the master to obtain a pass",
        "not a candidate `FAIL` verdict",
    ):
        assert required in tailor
    assert "`ACCEPT`" not in tailor
    assert "`REQUEST_CHANGES`" not in tailor


@pytest.mark.parametrize("filename", [
    "AGENTS.md", "README.md", ".github/skills/tailor-resume/SKILL.md",
])
def test_blind_screening_context_limitations_are_disclosed(filename):
    text = (ROOT / filename).read_text()
    assert "fresh" in text
    assert "blind review" in text
    assert "unavailable" in text
    assert "cannot be excluded" in text
    assert "source" in text


def test_markdown_review_preserves_pdf_conversion_boundaries():
    review = (ROOT / ".github/skills/review-resume/SKILL.md").read_text()
    assert "Review Markdown only" in review
    assert "do not review PDF layout or pagination" in review
    render = (ROOT / ".github/skills/render-resume-pdf/SKILL.md").read_text()
    for required in (
        "Markdown-content review before producing the requested PDF",
        "reviewer does not review PDF layout or pagination",
        "Standalone conversion or theme changes do not trigger",
        "same remaining review budget", "incomplete",
        "Do not claim a page count from Markdown alone",
    ):
        assert required in render


@pytest.mark.skipif(shutil.which("git") is None, reason="Git is needed to check ignore rules")
def test_private_source_and_application_paths_are_ignored(tmp_path):
    subprocess.run(
        ["git", "init", "--quiet", str(tmp_path)], check=True, capture_output=True,
    )
    (tmp_path / ".gitignore").write_bytes((ROOT / ".gitignore").read_bytes())
    paths = [
        "sources/experience.md", "sources/archive.pdf", "sources/nested/notes.md",
        "assets/example-company/resume.md", "assets/example-company/resume.pdf",
        "previews/sample.pdf", "samples/example.basic.pdf",
        "samples/nested/example.discord.pdf", "experience.md",
    ]
    result = subprocess.run(
        ["git", "check-ignore", "--stdin"], cwd=tmp_path,
        input="\n".join(paths + [
            "README.md", "resume_pdf.py", "fonts/inter/Inter-Regular.ttf",
            "fonts/inter/LICENSE.txt",
        ]) + "\n",
        capture_output=True, text=True, check=True,
    )
    assert result.stdout.splitlines() == paths


@pytest.mark.parametrize("filename", [
    "AGENTS.md", "README.md", ".github/skills/render-resume-pdf/SKILL.md",
])
def test_new_themes_require_private_samples_and_licensed_fonts(filename):
    text = (ROOT / filename).read_text().casefold()
    assert re.search(r"\bnew(?:ly added)? theme\b", text)
    for required in ("sample", "samples/", "license"):
        assert required in text
    render = (ROOT / ".github/skills/render-resume-pdf/SKILL.md").read_text()
    for required in (
        "Whenever a new theme is added", "same source", "without rewriting",
        "<resume-stem>.<theme>.pdf", ".basic.pdf", "synthetic",
        "do not fetch fonts during conversion",
    ):
        assert required in render


def test_all_theme_samples_preserve_application_files(tmp_path):
    source = write_source(tmp_path / "assets/example-role/20260102_resume.md")
    application_pdf = source.with_suffix(".pdf")
    application_pdf.write_bytes(b"existing application PDF")
    samples = tmp_path / "samples"
    for theme in converter.THEMES:
        output = samples / f"{source.stem}.{theme}.pdf"
        assert converter.main([
            str(source), "--theme", theme, "--output", str(output),
        ]) == 0
        assert len(PdfReader(output).pages) <= 2
        for expected in ("Example Person", "Python", "reliability", "Portfolio"):
            assert expected in pdf_text(output)
    assert {path.name for path in samples.iterdir()} == {
        f"{source.stem}.{theme}.pdf" for theme in converter.THEMES
    }
    assert source.read_text() == SAMPLE
    assert application_pdf.read_bytes() == b"existing application PDF"


@pytest.mark.parametrize("theme", converter.THEMES)
def test_target_folder_pair_fixture_preserves_sources_and_siblings(tmp_path, theme):
    master_path = write_source(
        tmp_path / "sources" / "experience.md",
        "# Fixture Experience\n\n"
        "## Contact\n\n"
        "Fixture Person\n\n"
        "person@example.com | 555-0100 | Example City, ST | "
        "[linkedin.com/in/example](https://linkedin.com/in/example)\n\n"
        "## Skills\n\nPython | SQL | dbt | Airflow | Snowflake\n\n"
        "## Experience\n\n"
        "### Example Healthcare\n\n"
        "**Senior Data Engineer | 2020-2022**\n\n"
        "- Technical lead for a data platform supporting analytics; mentored engineers. [H1]\n"
        "- Led dbt adoption and data testing. [H1]\n"
        "- Designed and delivered a warehouse using S3, Airflow, and Snowflake. [H1]\n",
    )
    original_master = master_path.read_bytes()
    master = original_master.decode()
    assert not list(master_path.parent.glob("*.pdf"))
    contact_section = master.split("## Contact\n\n", 1)[1]
    name, contact = contact_section.split("\n\n")[:2]
    assets = tmp_path / "assets"
    application = assets / "arbitrary-folder" / "nested-role"
    jd_text = (
        "# Fixture Company - Senior Data Engineer\n\n"
        "Build clinical trial data platforms using Python, SQL, dbt, Airflow, "
        "and Snowflake. Mentor engineers. GraphQL experience preferred.\n"
    )
    jd = write_source(application / "platform_engineer_jd.md", jd_text)
    sibling = write_source(assets / "another-role" / "job-description.md", "# Other JD\n")
    old_resume = write_source(application / "20250101_resume.md")
    old_pdf = old_resume.with_suffix(".pdf")
    old_pdf.write_bytes(b"older PDF")
    prior_files = {
        path: path.read_bytes() for path in (master_path, jd, sibling, old_resume, old_pdf)
    }
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
        f"# {name}\n\n{contact}\n\n## Technical Skills\n\n"
        "Python | SQL | dbt | Airflow | Snowflake\n\n"
        "## Professional Experience\n\n### Example Healthcare\n\n"
        "**Senior Data Engineer | 2020-2022**\n\n"
        + "\n".join(selected) + "\n"
    )
    prefix = date(2026, 1, 2).strftime("%Y%m%d")
    resume = write_source(application / f"{prefix}_resume.md", tailored)
    output = resume.with_suffix(".pdf")
    assert converter.main(
        [str(resume), "--theme", theme, "--output", str(output)]
    ) == 0
    assert len(PdfReader(output).pages) <= 2
    text = " ".join(pdf_text(output).split())
    for line in selected:
        assert line.removeprefix("- ") in text
    assert "person@example.com | 555-0100 | Example City, ST | linkedin.com/in/example" in text
    assert "GraphQL" not in text
    assert not re.search(r"\[H\d", tailored)
    assert not jd.with_suffix(".pdf").exists()
    assert resume.read_text() == tailored
    assert {path: path.read_bytes() for path in prior_files} == prior_files
    assert set(assets.rglob("*.*")) == {
        jd, sibling, old_resume, old_pdf, resume, output,
    }
    assert resume.name == "20260102_resume.md"
    assert output.name == "20260102_resume.pdf"


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
    styles = converter.make_styles("basic")
    assert styles["body"].textColor == HexColor("#000000")
    assert styles["h1"].textColor == HexColor("#18344A")
    assert styles["h2"].textColor == HexColor("#18344A")
    assert styles["h3"].textColor == HexColor("#000000")


def test_developer_accents_are_readable_and_present_in_rendered_pdf(tmp_path):
    styles = converter.make_styles("developer")
    blue = HexColor("#1D4ED8")
    teal = HexColor("#0F766E")
    assert styles["h1"].textColor == blue
    assert styles["h2"].textColor == teal
    assert styles["body"].textColor == HexColor("#24292F")
    for color in (blue, teal, styles["body"].textColor):
        linear = [
            channel / 12.92 if channel <= 0.04045
            else ((channel + 0.055) / 1.055) ** 2.4
            for channel in (color.red, color.green, color.blue)
        ]
        luminance = sum(weight * channel for weight, channel in zip(
            (0.2126, 0.7152, 0.0722), linear, strict=True,
        ))
        assert 1.05 / (luminance + 0.05) >= 4.5
    link = next(p for p in converter.markdown_story(SAMPLE, "developer") if "Portfolio" in p.text)
    assert 'color="#1D4ED8"' in link.text
    output = tmp_path / "developer.pdf"
    converter.render_pdf(SAMPLE, output, theme="developer")
    reader = PdfReader(output)
    stream = ContentStream(reader.pages[0].get_contents(), reader)
    fill_colors = [
        tuple(float(value) for value in operands)
        for operands, operator in stream.operations if operator == b"rg"
    ]
    for color in (blue, teal):
        assert any(
            actual == pytest.approx((color.red, color.green, color.blue), abs=1e-6)
            for actual in fill_colors
        )


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


@pytest.mark.parametrize("theme", [name for name in converter.THEMES if name != "basic"])
def test_non_default_outputs_are_separate_and_protected(tmp_path, capsys, theme):
    source = write_source(tmp_path / "resume.md")
    basic = source.with_suffix(".pdf")
    basic.write_bytes(b"existing basic PDF")
    assert converter.main([str(source), "--theme", theme]) == 0
    output = source.with_suffix(f".{theme}.pdf")
    assert output.is_file()
    assert basic.read_bytes() == b"existing basic PDF"
    saved = output.read_bytes()
    assert converter.main([str(source), "--theme", theme]) == 1
    assert "--force" in capsys.readouterr().err
    assert output.read_bytes() == saved
    assert converter.main([str(source), "--theme", theme, "--force"]) == 0
    assert basic.read_bytes() == b"existing basic PDF"


@pytest.mark.parametrize("theme", [name for name in converter.THEMES if name != "basic"])
def test_non_default_batch_and_output_override(tmp_path, monkeypatch, theme):
    assets = tmp_path / "assets"
    monkeypatch.setattr(converter, "ASSETS_DIR", assets)
    source = write_source(assets / "one" / "resume.md")
    second = write_source(assets / "two" / "role" / "resume.md")
    assert converter.main(["--all", "--theme", theme]) == 0
    for path in (source, second):
        assert path.with_suffix(f".{theme}.pdf").is_file()
        assert not path.with_suffix(".pdf").exists()
    custom = tmp_path / "previews" / "custom.pdf"
    assert converter.main(
        [str(source), "--theme", theme, "--output", str(custom)]
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


def test_discord_preserves_basic_layout_and_accent_locations():
    basic = converter.make_styles("basic")
    themed = converter.make_styles("discord")
    accent = HexColor("#5865F2")
    for name in basic:
        for attribute in (
            "fontSize", "leading", "spaceBefore", "spaceAfter", "keepWithNext",
            "leftIndent", "rightIndent", "allowWidows", "allowOrphans",
        ):
            assert getattr(themed[name], attribute, None) == getattr(basic[name], attribute, None)
        assert themed[name].fontName.startswith("ResumeInter")
        if name in {"h1", "h2"}:
            assert themed[name].textColor == accent
        else:
            assert themed[name].textColor == basic[name].textColor
    assert converter.get_theme("discord").bullet == converter.get_theme("basic").bullet
    link = next(p for p in converter.markdown_story(SAMPLE, "discord") if "Portfolio" in p.text)
    assert 'color="#5865F2"' in link.text


def test_discord_embeds_real_inter_faces_and_blurple(tmp_path):
    source = SAMPLE + "\n\nA ***bold italic*** detail.\n"
    story = converter.markdown_story(source, "discord")
    font_names = {fragment.fontName for p in story for fragment in p.frags}
    assert {
        "ResumeInter", "ResumeInter-Bold", "ResumeInter-Italic", "ResumeInter-BoldItalic",
    } <= font_names
    output = tmp_path / "discord.pdf"
    converter.render_pdf(source, output, theme="discord")
    reader = PdfReader(output)
    used_fonts = set()

    def collect_fonts(text, cm, tm, font, size):
        if text.strip() and font:
            used_fonts.add(str(font["/BaseFont"]).split("+")[-1])

    reader.pages[0].extract_text(visitor_text=collect_fonts)
    assert used_fonts == {
        "Inter-Regular", "Inter-Bold", "Inter-Italic", "Inter-BoldItalic", "/Symbol",
    }
    embedded_fonts = [
        font.get_object() for font in reader.pages[0]["/Resources"]["/Font"].values()
        if "Inter" in str(font.get_object()["/BaseFont"])
    ]
    assert len(embedded_fonts) == 4
    assert all("/FontFile2" in font["/FontDescriptor"] for font in embedded_fonts)
    stream = ContentStream(reader.pages[0].get_contents(), reader)
    accent = HexColor("#5865F2")
    assert any(
        tuple(float(value) for value in operands)
        == pytest.approx((accent.red, accent.green, accent.blue), abs=1e-6)
        for operands, operator in stream.operations if operator == b"rg"
    )
    license_text = (ROOT / "fonts/inter/LICENSE.txt").read_text()
    assert "Copyright (c) 2016 The Inter Project Authors" in license_text
    assert "SIL OPEN FONT LICENSE Version 1.1" in license_text


@pytest.mark.parametrize("failure", ["missing", "corrupt"])
def test_discord_font_errors_do_not_substitute_fonts(tmp_path, monkeypatch, capsys, failure):
    source = write_source(tmp_path / "resume.md")
    directory = tmp_path / "fonts"
    if failure == "corrupt":
        directory.mkdir()
        (directory / "Inter-Regular.ttf").write_bytes(b"not-a-valid-font")
    monkeypatch.setattr(converter, "INTER_FONT_DIR", directory)
    converter.register_fonts.cache_clear()
    try:
        assert converter.main([str(source), "--theme", "discord"]) == 1
        error = capsys.readouterr().err
        expected = "Missing theme font" if failure == "missing" else "Cannot load theme font"
        assert expected in error
        assert "Inter-Regular.ttf" in error
        assert not source.with_suffix(".discord.pdf").exists()
    finally:
        converter.register_fonts.cache_clear()
