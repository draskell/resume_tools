# Resume tools

A local workspace for maintaining an experience bank, tailoring resumes with an agent, and converting Markdown to PDFs. Python dependencies and the project-local `.venv/` are managed by [uv](https://docs.astral.sh/uv/).

## Setup

Requires Python 3.10+ and uv:

```sh
uv sync
```

`uv.lock` pins the dependencies. No browser, office suite, external rendering service, or model API key is needed. Resume extraction/rendering stays local.

Private documents are not distributed with the repository. Create a local `sources/experience.md` containing your name, contact details, skills, employment history, accomplishments, education, and source notes before asking an agent to tailor a resume.

## Source of truth and layout

`sources/experience.md` is the private, job-independent source for skills, employment, accomplishments, education, and training. Consolidate supported facts, evidence IDs, and conflict resolutions there. Keep target applications, JD requirements, output filenames, and screening feedback out of it. Original import filenames and application-folder context are preserved separately in the private `sources/provenance.md` ledger, which is not an input to routine tailoring.

```text
sources/
  experience.md                       # master evidence bank
  provenance.md                       # historical import ledger; maintenance only
  optional-source-archive.pdf          # already integrated; not needed for tailoring
AGENTS.md                             # agent workflow and factual rules
.github/skills/tailor-resume/SKILL.md
.github/skills/review-resume/SKILL.md
.github/skills/render-resume-pdf/SKILL.md
assets/
  example-role/
    job-description.md                # supplied JD
    YYYYMMDD_resume.md                # generated, using current local date
    YYYYMMDD_resume.pdf               # same basename, requested style only
    YYYYMMDD_resume_notes.md          # scored review of that exact resume
```

Any user-selected subfolder under `assets/` works, including nested role folders. No company-name convention, registry, or code edits are needed to add a new target. Paths and symlinks must stay within the project's `assets/` directory. Keep older outputs and sibling folders unchanged. External source archives need not be present once their supported evidence has been consolidated into the private master.

The LinkedIn export received a **one-time integration** into the master, with page references and user-approved conflict resolutions. Future JD matching uses only the integrated master and the JD; it does not reread or automatically discover source PDFs. Keep any archive under the ignored `sources/` folder and revisit it only on an explicit source-maintenance request. An export date alone does not resolve factual conflicts, and an omitted fact does not retract existing evidence.

## Tailor a resume with an agent

Put a JD in a target folder, then tell the agent the **folder and style**:

> Generate a resume in assets/example-role using developer.

That's the complete normal request. `basic` is used if you omit the style. The agent reads the folder's JD and private experience bank, writes a truthful tailored resume, runs the automatic blind screen, and produces exactly one pair: `YYYYMMDD_resume.md` and `YYYYMMDD_resume.pdf`, using the current local date resolved once at request start (`date +%Y%m%d`). The PDF uses only the requested style and must be at most two pages unless you explicitly change the limit. No separate PDF request or unrequested theme variants.

The JD can have any filename, including `job-description.md` or `*_jd.md`, and be Markdown, plain text, or a locally text-extractable PDF. The agent inspects immediate files only, not sibling or nested applications, and excludes existing resumes. It leaves the JD's name and contents unchanged. Missing or multiple plausible JDs require clarification, not a guessed selection or combined posting.

Existing same-day outputs are protected. A request to regenerate, update, or restyle authorizes replacement of only that day's pair and associated notes; otherwise the agent asks before overwriting. Replacements are staged in ignored `previews/` and verified before publication, preserving the old pair and notes on screening/rendering failure. Successful generation returns the three output paths; review details are saved in the companion notes. A material blocker is reported rather than disguised as success.

The author must not invent qualifications, infer employment from application folders, change dates/titles/metrics, or add JD requirements to the master. Update the bank only with new factual information supplied or approved by you. Repository-local skills and `AGENTS.md` define this agent workflow; Python renders the approved Markdown, not AI-generated content by itself.

Resume-facing entries use the master's approved title, normally the highest/latest title for an employer's overall tenure. Detailed promotions and alternate titles stay in the master for reference and detailed histories; they are not extra concurrent jobs or a claim that the highest title was held for the whole tenure.

Every resume starts with the name, followed by one contact line in the order **email | phone | location | LinkedIn**, copied from the master's Contact section. This header must appear above the title or summary in both Markdown and PDF, with no placeholders or missing fields.

Both formats are included in every target-folder generation request. Standalone conversion or restyling remains available without rerunning authoring or screening.

### Cloud-aware tailoring

When the JD identifies an AWS environment, the author emphasizes documented AWS experience and minimizes unrelated Azure branding, retaining relevant capabilities without a documented AWS equivalent. A cloud-neutral JD gets capability-led wording rather than assumptions about the company's platform. Prefer concise underlying tool names such as S3 and Airflow; use MWAA only when the JD requests it or hosting details matter.

Never relabel a historical project from one cloud to another. EMR and Synapse overlap for Spark/distributed processing, not every warehousing or orchestration feature. The author can select documented EMR work or describe a transferable capability without a brand, but cannot rewrite an Azure project as an AWS project. Newly supplied global skills do not establish use at a specific employer.

### Match score and companion notes

Each screen also returns an evidence-based **match score /100**: required-qualification alignment 40, relevant scope/ownership/leadership 25, concrete accomplishment/delivery evidence 20, clarity/chronology 10, and contactability/Markdown usability 5. The reviewer defines item weights from the JD on the first round and retains them across rounds. Evidence anchors award 0%, 25%, 50%, 75%, or 100% of each item's points; the report explains awards and reconciles subtotals. **PASS requires at least 85/100 and no material required-qualification gap or other blocking concern.** A high score cannot override a missing required qualification. Missing bonuses do not reduce the score or independently cause failure. This is a simulated match assessment, not an actual ATS score, probability, or market-calibrated prediction.

The reviewer stays blind and read-only. The author saves its Markdown report verbatim in `<resume-stem>_notes.md`, for example `YYYYMMDD_resume_notes.md`, with a metadata header identifying the resume basename and SHA-256 of its exact Markdown bytes. Notes contain the score breakdown, verdict, rationale, and current blocking/optional shortcomings. They are private and ignored, never used as a JD or rendered as a PDF; `*_resume_notes.md` is excluded from posting discovery.

After each re-screen, staged notes are replaced to describe the actual current reviewed draft. Publish matching notes with the verified Markdown/PDF pair; preserve the old pair and notes if a replacement fails. Same-day regeneration authorization includes refreshing associated notes. A failed draft and matching report remain in `previews/`, with paths and the blocker reported; unavailable screening receives no invented score or FAIL verdict.

Successful tailoring returns **three output paths**. Standalone conversion/restyling neither creates notes nor triggers another screen.

### Automatic rubber-duck review

Every tailored resume uses two roles: the author knows the private experience bank; one independent, read-only reviewer sees **only the JD and resume**. The reviewer receives a self-contained hiring-screen rubric, not this repository's authoring instructions, source filenames, private evidence, or author explanations. It simulates an automated resume screen at the hiring organization and returns **`PASS` or `FAIL` with rationale**, supported by JD requirements and visible resume evidence.

The reviewer assesses demonstrated skills, role scope/seniority, relevant accomplishments, clarity, and material qualification gaps. It distinguishes required qualifications from bonuses and credits equivalents when allowed by the JD. "Not shown in the resume" is not proof the candidate lacks an experience. This is a simulation, not the employer's actual ATS, a validated ATS score, or a prediction of the hiring decision.

On `FAIL`, the author privately searches the master for additional true details or clearer transferable experience addressing the concerns, revises the resume, and rechecks every factual claim. The reviewer sees only the JD and revised resume, never off-resume assurances or private citations. **Do not invent qualifications, strengthen metrics, or relabel adjacent work as direct domain experience to win a pass.** A real qualification gap can remain a legitimate failure.

The limit is **3 reviewer passes**, allowing up to **2 revision cycles**. Finish early when the current draft receives `PASS` and the author finds no substantive factual issues. Optional stylistic nits or preferred-qualification gaps may remain. If `FAIL` remains at the cap, or no useful supported revision is possible, preserve the honest draft and report the rationale as **incomplete**, not automatically approved. Unavailable/failed screening must be disclosed, not misrepresented as a candidate rejection. Reviewer comments are persisted in companion notes, outside resumes and tracked files; private author dispositions remain only in the session.

Start each request with a fresh reviewer context and reuse it only for that request's re-screens. Do not reuse the previous source-aware reviewer. If a host automatically exposes private author context that cannot be excluded, report that blind review is unavailable. The input separation is an instruction-level boundary, not a filesystem sandbox.

The author keeps the model selected for the current session. The reviewer uses the **configured subagent model** by default, which may be different. You can override only the reviewer for a request, for example: "Tailor this resume and use [model ID] as the reviewer." No reviewer model is pinned, and an unavailable requested model is reported rather than silently replaced. Without an explicit override, runtime model, reasoning, and context preferences apply.

Review adds sequential model work and therefore increases runtime and credit use; there is no fixed multiplier or enforced credit budget. This is an instruction-driven workflow requiring a host with independent subagent support, not a new Python command or external model service. Contract tests check the instructions, not whether every host or model will obey them.

Independent review covers **Markdown content only**, not PDF layout or pagination, and does not render PDFs. The writer then renders the chosen style and checks the actual PDF's two-page limit, complete text, header, and layout. A resulting Markdown change must be reviewed within the remaining budget; a page limit cannot be verified from Markdown alone. Standalone conversion or theme changes do not initiate the content-review loop.

## Convert Markdown to PDF

The target-folder workflow uses explicit output naming for the matching dated pair (substitute the actual date for `YYYYMMDD`):

```sh
uv run python resume_pdf.py assets/example-role/YYYYMMDD_resume.md \
  --theme developer --output assets/example-role/YYYYMMDD_resume.pdf
```

The commands below are standalone rendering utilities, not the agent's resume-generation workflow. Convert a single existing resume (paths are relative to your working directory):

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

Choose a theme at conversion time; the same Markdown works with any theme.

| Theme | Style | Default output |
| --- | --- | --- |
| `basic` (default) | Current compact sans-serif layout, restrained blue headings, white background | `resume.pdf` |
| `developer` | Monospace Courier, blue name/link accents, teal section headings, charcoal body, hyphen bullets, white background | `resume.developer.pdf` |
| `discord` | Basic layout with Inter text and blurple (`#5865F2`) name, section headings, and links; white background | `resume.discord.pdf` |

```sh
uv run python resume_pdf.py assets/example-company/resume.md --theme developer
uv run python resume_pdf.py --all --theme developer
uv run python resume_pdf.py assets/example-company/resume.md --theme basic
uv run python resume_pdf.py assets/example-company/resume.md --theme discord
```

For standalone comparisons, non-default themes get their own filename so they cannot accidentally replace the basic PDF. Target-folder generation always overrides that default with `--output .../YYYYMMDD_resume.pdf`, creating just the requested style. `--force` is still required to replace an existing converter destination after authorization and staging. Omit `--theme` to retain the original basic rendering.

The developer theme is a restrained monospace interpretation, not an exact reproduction of an xtools preview. All themes retain selectable text, clickable links, the complete contact header, and the same page dimensions and pagination rules. Font widths change wrapping, so review the page count when switching themes; a theme never removes content or automatically shrinks text to meet a page limit.

The discord theme is only a typography/color nod to the [developer docs](https://docs.discord.com/developers/quick-start/overview-of-apps), not a copy of the site or an official endorsement. Its primary accent is the docs' `#5865F2`. The site loads Inter as well as custom gg sans faces; [Discord's font FAQ](https://support.discord.com/hc/en-us/articles/9507780972951-gg-sans-Font-Update-FAQ) does not permit gg sans in other projects, so this theme explicitly uses open-source Inter instead.

Inter's unmodified Regular, Bold, Italic, and BoldItalic static TrueType faces are bundled in `fonts/inter/` from the official [Inter 4.1 release](https://github.com/rsms/inter/releases/tag/v4.1), under the included SIL Open Font License (`fonts/inter/LICENSE.txt`). The source `Inter-4.1.zip` SHA256 is `9883fdd4a49d4fb66bd8177ba6625ef9a64aa45899767dde3d36aa425756b11e`. No extra dependencies or runtime font downloads are needed.

### Theme samples

Every newly added theme must include a rendered sample in the Git-ignored `samples/` folder, as required by the rendering skill. Use the request's selected resume unchanged (or synthetic content when no source was selected), and use that same source for all comparisons:

```sh
uv run python resume_pdf.py assets/example-role/YYYYMMDD_resume.md \
  --theme discord --output samples/YYYYMMDD_resume.discord.pdf
```

Name samples `<resume-stem>.<theme>.pdf`, including `.basic.pdf` for a basic comparison. Check layout, page count, complete text, links, fonts, and colors. Do not alter resume wording, put comparisons in application folders, or replace application PDFs. Samples remain private; the licensed font assets are redistributable tooling, not private resume material.

### Sources for restrained Markdown theme ideas

- [GitHub Markdown CSS](https://github.com/sindresorhus/github-markdown-css): a good reference for a familiar, understated GitHub-like style; start with its light-only variant.
- [markdown-cv](https://github.com/elipapa/markdown-cv): resume-specific HTML/print styling, with `kjhealy` and `davewhipp` layouts.
- [Typora theme gallery](https://theme.typora.io/): a broader source of typography and spacing ideas. Favor light, single-column themes without sidebars, large banners, or heavy decoration.

These are design references, not installed or bundled themes. Their CSS cannot be applied directly to this ReportLab renderer; compatible typography, spacing, and color choices must be implemented as local PDF themes. No remote stylesheets, runtime font downloads, or personal-document uploads are used.

## Markdown and layout

Supported: headings (`#` through `######`), paragraphs, bold/italic text, unordered lists (including nesting), explicit line breaks, and inline links with `http`, `https`, or `mailto` destinations. Use `###` for employers followed by a paragraph for role/dates to keep those blocks with the following content.

Tables, images, raw HTML, blockquotes, ordered lists, inline code, fenced/indented code, and horizontal rules are explicitly rejected rather than silently omitted. Unrecognized plain Markdown text follows CommonMark rules. Font coverage is checked for the selected theme: bundled Bitstream Vera faces serve `basic`, standard PDF Courier faces serve `developer`, bundled Inter faces serve `discord`, and the PDF Symbol font supplies right arrows. Unsupported characters produce an actionable error instead of missing-glyph boxes; the font families have different character coverage.

Output uses US Letter, compact typography, theme-specific heading colors, page numbers, selectable text, and clickable links. Page counts are natural, not forcibly capped at two pages. Edit the resume for relevance/readability rather than shrinking text indefinitely.

## Development

```sh
uv run pytest
```

The repository contains tooling, agent instructions, licensed font assets, and synthetic tests. `.venv/`, caches, all of `sources/` (including the master and archived PDFs), all of `assets/`, `previews/`, and `samples/` are ignored by Git. The legacy root-master ignore rule is retained as a safeguard. Keep personal documents in those private locations; do not force-add them. Ignoring files does not back them up, so maintain a separate private backup.

The test suite runs without private documents. Additional checks against local resumes run when they are present. Hard-coded resume generators must not overwrite newer Markdown.
