---
name: render-resume-pdf
description: Convert or regenerate Markdown resumes as local PDFs using the uv-managed Python converter. Use for single-file or batch resume PDF creation, pagination review, or explicit replacement of an existing PDF.
---

# Render a resume PDF

1. Read root `AGENTS.md` and the intended Markdown input. Verify the resume begins with the name heading and the complete `email | phone | location | LinkedIn` contact line from `sources/experience.md`'s Contact section, without placeholders. For tailoring, first use `tailor-resume`; do not render a JD or the comprehensive master as an application resume.
2. Run `uv sync` if the environment is not ready. Use the project's locked dependencies; do not invoke the removed hard-coded generators.
3. Convert one file:

   ```sh
   uv run python resume_pdf.py assets/example-company/resume.md
   ```

   Use `--output path/to/preview.pdf` for a separate preview without replacing the current application PDF.

   The existing style is named `basic` and remains the default. Add `--theme developer` for light monospace text and headings; it writes `<resume>.developer.pdf` instead of replacing `<resume>.pdf`. `--theme basic` explicitly selects the original style. Both single-file and batch modes accept `--theme`. Never modify resume wording just to apply a theme.

4. To convert all application resumes, use `uv run python resume_pdf.py --all`. Discovery is recursive under `assets/`, includes `resume.md` and `*_resume.md`, and excludes JDs and documentation. Batch preflight fails if an output already exists; it does not silently skip files.
5. Existing PDFs are protected. Add `--force` only when the user explicitly requests replacement. A request to create a preview is not permission to replace a prior PDF.
6. Review text extraction for completeness and punctuation, verify the name and all four contact fields appear in order at the top of the first page, inspect page count and layout where rendering tools are available, and check that headings stay with following text. Font widths differ between themes, so recheck pagination after switching. Prefer readable natural pagination to forcing a fixed count, unless the user specifies a page limit. Never claim visual review if only text extraction was possible.
7. Surface conversion errors. Fix the source syntax or unsupported characters rather than silently dropping content. The converter supports headings, paragraphs, bold/italic text, flat or nested unordered lists, and inline links. Unsupported blocks such as HTML, images, tables, code blocks, and blockquotes are rejected.
8. Leave input Markdown unchanged. Report the output path and any genuine layout limitations.
