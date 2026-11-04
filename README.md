# Resume tools

A local workspace for maintaining an experience bank, tailoring resumes with an agent, and converting Markdown to PDFs. Python dependencies and the project-local `.venv/` are managed by [uv](https://docs.astral.sh/uv/).

## Setup

Requires Python 3.10+ and uv:

```sh
uv sync
```

`uv.lock` pins the dependencies. No browser, office suite, external rendering service, or model API key is needed. Resume extraction/rendering stays local.

Private documents are not distributed with the repository. Create a local `experience.md` containing your name, contact details, skills, employment history, accomplishments, education, and source notes before asking an agent to tailor a resume.

## Source of truth and layout

`experience.md` is the private, comprehensive source for skills, employment, accomplishments, education, and training. Consolidate supported information from source documents and record provenance and conflict resolutions there. It is not a length-limited application resume.

```text
experience.md                         # master evidence bank
AGENTS.md                             # agent workflow and factual rules
.github/skills/tailor-resume/SKILL.md
.github/skills/render-resume-pdf/SKILL.md
assets/
  example-company/
    job-description.md                # supplied JD
    resume.md                         # tailored application resume
    resume.pdf                        # derived output, when requested
```

Use lowercase hyphenated company names. For multiple roles at a company, use role-specific subfolders rather than overwriting another application. Keep existing dated filenames when importing documents, and make subsequent edits in Markdown before regenerating PDFs. External source archives need not be present once their supported evidence has been consolidated into the private master.

## Tailor a resume with an agent

Repository-local skills and `AGENTS.md` explain the workflow to compatible agents. For example:

> Read experience.md and use the tailor-resume skill to create a resume for Example Company, Senior Data Engineer, using this JD: [paste the full posting].

The agent reads the master and JD together, preserves the posting as `assets/example-company/job-description.md`, and writes a supported, relevant `resume.md`. It must not invent qualifications, infer employment from application folders, change dates/titles/metrics, or add JD requirements to the master. Important evidence gaps belong in the agent's response, not the application resume. Update the master only with new factual information supplied or approved by you.

Every resume starts with the name, followed by one contact line in the order **email | phone | location | LinkedIn**, copied from the master's Contact section. This header must appear above the title or summary in both Markdown and PDF, with no placeholders or missing fields.

Tailoring produces Markdown first. Ask for PDF conversion separately or explicitly include it in the request. Skills are instructions for your agent, not a standalone automated writing service.

## Convert Markdown to PDF

Convert a single resume (paths are relative to your working directory):

```sh
uv run python resume_pdf.py assets/example-company/resume.md
```

The PDF defaults to the same folder and basename. Create a separate preview:

```sh
uv run python resume_pdf.py assets/example-company/resume.md --output previews/example.pdf
```

Convert all application resumes:

```sh
uv run python resume_pdf.py --all
```

Batch mode recursively searches this project's `assets/` for `resume.md` and `*_resume.md`, in sorted order. It does not convert `job-description.md`, the master, or project/skill documentation. Other filenames can be converted explicitly in single-file mode.

**Existing PDFs are protected.** Conversion reports a conflict when an output already exists. Regenerate only when intended:

```sh
uv run python resume_pdf.py assets/example-company/resume.md --force
uv run python resume_pdf.py --all --force
```

Inputs and conflicts are checked and every PDF is rendered to a temporary file before publishing. Failed validation/rendering leaves current PDFs intact. Publishing is atomic per file, not a filesystem-wide transaction: a later publish-time filesystem/concurrency error can leave earlier batch outputs published; it is reported as an error. Success messages are printed only when the complete request succeeds.

Original PDFs may lag behind edited Markdown. The converter never rewrites Markdown or synchronizes old PDF contents back into the master.

## Themes

Choose a theme at conversion time; the same Markdown works with either style.

| Theme | Style | Default output |
| --- | --- | --- |
| `basic` (default) | Current compact sans-serif layout, restrained blue headings, white background | `resume.pdf` |
| `developer` | Monospace Courier text and headings, hyphen bullets, charcoal accents, white background; an editor-inspired look without terminal decoration | `resume.developer.pdf` |

```sh
uv run python resume_pdf.py assets/example-company/resume.md --theme developer
uv run python resume_pdf.py --all --theme developer
uv run python resume_pdf.py assets/example-company/resume.md --theme basic
```

Non-default themes get their own filename so a comparison cannot accidentally replace the basic PDF. `--output` overrides that naming when needed, and `--force` is still required to replace any existing destination. Omit `--theme` to retain the original behavior.

The developer theme is a restrained monospace interpretation, not an exact reproduction of an xtools preview. Both themes retain selectable text, clickable links, the complete contact header, and the same page dimensions and pagination rules. Font widths change wrapping, so review the page count when switching themes; a theme never removes content or automatically shrinks text to meet a page limit.

### Sources for restrained Markdown theme ideas

- [GitHub Markdown CSS](https://github.com/sindresorhus/github-markdown-css): a good reference for a familiar, understated GitHub-like style; start with its light-only variant.
- [markdown-cv](https://github.com/elipapa/markdown-cv): resume-specific HTML/print styling, with `kjhealy` and `davewhipp` layouts.
- [Typora theme gallery](https://theme.typora.io/): a broader source of typography and spacing ideas. Favor light, single-column themes without sidebars, large banners, or heavy decoration.

These are design references, not installed or bundled themes. Their CSS cannot be applied directly to this ReportLab renderer; compatible typography, spacing, and color choices must be implemented as local PDF themes. No remote stylesheets, fonts, or personal-document uploads are used.

## Markdown and layout

Supported: headings (`#` through `######`), paragraphs, bold/italic text, unordered lists (including nesting), explicit line breaks, and inline links with `http`, `https`, or `mailto` destinations. Use `###` for employers followed by a paragraph for role/dates to keep those blocks with the following content.

Tables, images, raw HTML, blockquotes, ordered lists, inline code, fenced/indented code, and horizontal rules are explicitly rejected rather than silently omitted. Unrecognized plain Markdown text follows CommonMark rules. Font coverage is checked for the selected theme: bundled Bitstream Vera faces serve `basic`, standard PDF Courier faces serve `developer`, and the PDF Symbol font supplies right arrows. Unsupported characters produce an actionable error instead of missing-glyph boxes; the two font families have different character coverage.

Output uses US Letter, compact typography, theme-specific heading colors, page numbers, selectable text, and clickable links. Page counts are natural, not forcibly capped at two pages. Edit the resume for relevance/readability rather than shrinking text indefinitely.

## Development

```sh
uv run pytest
```

The repository contains tooling, agent instructions, and synthetic tests. `.venv/`, caches, all of `assets/`, the personal `experience.md` master, and `previews/` are ignored by Git. Keep personal documents in those private locations; do not force-add them. Ignoring files does not back them up, so maintain a separate private backup.

The test suite runs without private documents. Additional checks against local resumes run when they are present. Hard-coded resume generators must not overwrite newer Markdown.
