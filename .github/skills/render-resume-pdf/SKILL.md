---
name: render-resume-pdf
description: Convert or regenerate Markdown resumes as local PDFs using the uv-managed Python converter. Use for single-file or batch PDF creation, pagination review, adding themes with sample PDFs, or explicit replacement of an existing PDF.
---

# Render a resume PDF

1. Read root `AGENTS.md` and the intended Markdown input. Verify the resume begins with the name heading and the complete `email | phone | location | LinkedIn` contact line from `sources/experience.md`'s Contact section, without placeholders. The master contains the one-time LinkedIn integration; do not reopen source PDFs for this check or require the archives to exist. If the master is absent, ask for it. For tailoring, first use `tailor-resume`; do not render a JD or the comprehensive master as an application resume.

   For a tailoring request, require `PASS` from the independent Markdown-content review before producing the requested PDF, plus the author's private factual validation. Use the selected target folder and the same resolved date for `YYYYMMDD_resume.md` and `YYYYMMDD_resume.pdf`. The reviewer does not review PDF layout or pagination; the writer performs the rendering checks below. Standalone conversion or theme changes do not trigger the two-agent loop. If a rendering check necessitates a Markdown revision, return it to the blind reviewer within the same remaining review budget before calling the tailoring task done; if no pass remains, report the changed draft as incomplete. Do not claim a page count from Markdown alone.

2. Run `uv sync` if the environment is not ready. Use the project's locked dependencies; do not invoke the removed hard-coded generators.
3. For the target-folder workflow, convert only the approved dated Markdown in the requested theme. Substitute the current local date resolved by the author for `YYYYMMDD`:

   ```sh
   uv run python resume_pdf.py assets/example-role/YYYYMMDD_resume.md \
     --theme developer --output assets/example-role/YYYYMMDD_resume.pdf
   ```

   Use `--theme basic` when that is the requested style or no style was supplied. Always supply `--output` for tailored pairs, so exactly one PDF shares the Markdown basename, without a theme suffix. For same-day replacements, stage both files in ignored `previews/` and verify them before publishing either one; retain the old pair if approval or rendering fails. Do not leave preview files in the application folder. Do not use `--all` for a target-folder request.

   For standalone conversions, the existing style is named `basic` and remains the default. The `developer` theme uses monospace text, blue name/link accents, and teal section headings on white. The `discord` theme uses the same layout and colored items as basic, with Inter and blurple (`#5865F2`) accents on white. Inter is a licensed alternative, not the docs site's proprietary gg sans. Without `--output`, non-default conversion writes `<resume>.<theme>.pdf` instead of replacing `<resume>.pdf`. Both single-file and batch modes accept `--theme`. Never modify resume wording just to apply a theme. Use `--output path/to/preview.pdf` for a separate comparison without replacing an application PDF.

4. To convert all application resumes, use `uv run python resume_pdf.py --all`. Discovery is recursive under `assets/`, includes `resume.md` and `*_resume.md`, and excludes JDs and documentation. Batch preflight fails if an output already exists; it does not silently skip files.
5. Existing PDFs are protected. Add `--force` only when the user explicitly requests replacement. A same-day regenerate, update, or restyle request authorizes replacement of only that day's pair after staging and verification. A request to create a preview is not permission to replace a prior PDF. Preserve older outputs, the JD, and sibling folders.
6. Review text extraction for completeness and punctuation, verify the name and all four contact fields appear in order at the top of the first page, inspect page count and layout where rendering tools are available, and check that headings stay with following text. Font widths differ between themes, so recheck pagination after switching. Tailored resumes must be at most two pages unless the user explicitly changes the limit; verify the actual PDF. The converter itself does not truncate or shrink content, and standalone conversion does not enforce a page limit. Never claim visual review if only text extraction was possible.
7. Surface conversion errors. Fix the source syntax or unsupported characters rather than silently dropping content. The converter supports headings, paragraphs, bold/italic text, flat or nested unordered lists, and inline links. Unsupported blocks such as HTML, images, tables, code blocks, and blockquotes are rejected.
8. Leave input Markdown unchanged during rendering. For successful target-folder generation, return only the final Markdown and PDF paths. For standalone conversion, report the PDF path. Report genuine failures or layout limitations rather than claiming completion.

## Adding a theme: always make a sample

Whenever a new theme is added, create a sample PDF under the Git-ignored `samples/` folder before calling the theme complete. Use the existing resume selected for the request, without rewriting or copying its Markdown. If no source was selected, use synthetic resume content rather than arbitrarily selecting a private application. Synthetic samples use a complete fictional contact header and do not require access to the private master. Never render a JD or the evidence bank as a sample.

Use explicit output names `samples/<resume-stem>.<theme>.pdf`, including `.basic.pdf` for basic comparisons. Generate every requested comparison from the exact same source; at minimum render the newly added theme. For an all-theme comparison, render each registered theme once. Do not put samples in application folders, overwrite application PDFs, or replace existing samples without authorization.

Keep all samples private and ignored. Check selectable text, contact/header completeness, links, fonts, accent colors, pagination, and visual layout. A resume sample must respect the normal two-page limit without changing its wording for a styling-only request; report any overflow instead of silently shrinking or editing it. Applying styles to unchanged Markdown does not start a new hiring-screen loop.

Use only redistributable fonts, include their license and source/version in the repository, and do not fetch fonts during conversion. If a desired website font is proprietary or unavailable, disclose the limitation and the licensed alternative rather than silently substituting it.
