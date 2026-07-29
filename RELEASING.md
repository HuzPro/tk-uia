# Releasing

A release is a tag push. `.github/workflows/publish.yml` builds the sdist and
wheel and uploads them to PyPI through
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/): PyPI trusts
the workflow's identity directly, so no API token exists anywhere, in this
repository or out of it.

## Before you tag

1. **The suite is green, including the gui lane.** `./.venv/Scripts/python.exe -m
   pytest -q`. The gui specs open real windows and take about eighty seconds.
   The unit lane alone is not enough for a release: `_accprop.py` is untested by
   design, and the gui specs are the only thing that reads an annotation back
   out of Windows.
2. **`ruff check src tests probes` and `ruff format --check src tests probes`.**
3. **`__version__` in `src/tk_uia/__init__.py` is the version you are shipping.**
   It is the single source: `[tool.hatch.version]` reads the package, the
   publish workflow refuses a tag that disagrees with it, and `describe()`
   prints it in its own headline.
4. **`CHANGELOG.md`'s top section is `## <version> - <date>`,** not
   `## Unreleased`, and the date is today's.
5. **`COVERAGE.md` is regenerated** if anything touched roles or annotation:
   `python probes/coverage_matrix.py`. It is measured, not written.
6. **The documented numbers still hold.** They live in `docs/GUIDE.md`, and the
   ones that go stale first are the `describe()` sample under *What your own
   application tells Windows* (re-run `probes/what_your_app_tells_windows.py`
   and paste), the gui spec count in *Measured*, and the coverage ratios. The
   `describe()` sample in `COOKBOOK.md` carries a version banner and goes stale
   the same way.

## Publish

Bump `__version__` and retitle the CHANGELOG's top section in the same commit,
then:

```powershell
git push origin main
git tag -a v0.6.3 -m "0.6.3"
git push origin v0.6.3
```

`gh run watch` or the Actions tab shows the rest. The workflow's first real step
compares the tag against `__version__` and refuses a mismatch, so a mistyped
tag publishes nothing. A version that reaches PyPI is permanent: uploads can be
yanked but never replaced, and re-uploading an existing version is refused.

## Checking the artifacts locally

Optional, and worth it before a first-of-anything. Build the same way the
workflow does:

```powershell
./.venv/Scripts/python.exe -m pip install build
./.venv/Scripts/python.exe -m build
```

> The repo's `.venv` is created by `uv`, which does not put `pip` in it. If
> `python -m pip` answers `No module named pip`, run
> `./.venv/Scripts/python.exe -m ensurepip --upgrade` first.

The wheel must contain the package and nothing else:

```powershell
./.venv/Scripts/python.exe -c "import zipfile; print('\n'.join(sorted(zipfile.ZipFile('dist/tk_uia-0.6.3-py3-none-any.whl').namelist())))"
```

- `tk_uia/py.typed` is present. Without it every type annotation in the package
  is invisible to a type checker in somebody else's project.
- No `tests/`, no `probes/`, no `.venv`. They belong in the sdist, not in what
  an application installs.
- `METADATA` says `Requires-Dist:` for the `dev` extra only. **Runtime
  dependencies are permanently zero** and that is the claim the whole package
  rests on: a stray runtime requirement is the one regression worth blocking a
  release for.

Then install the wheel the way a stranger will, in a virtual environment that
has never seen this repository:

```powershell
py -m venv $env:TEMP\tk-uia-smoke
$env:TEMP\tk-uia-smoke\Scripts\python.exe -m pip install dist\tk_uia-0.6.3-py3-none-any.whl
$env:TEMP\tk-uia-smoke\Scripts\python.exe -c "import tkinter as tk, tk_uia; r = tk.Tk(); r.withdraw(); s = tk_uia.enable(r); assert s is tk_uia.Strategy.PROVIDED, s; print(tk_uia.__version__, s)"
Remove-Item -Recurse -Force $env:TEMP\tk-uia-smoke
```

The assertion is the point: `enable()` reporting `NATIVE`, `UNSUPPORTED` or a
downgrade where `PROVIDED` was expected is exactly the silent no-op this
package exists to refuse, and an install that imports cleanly and writes
nothing would pass any weaker check.

## One-time setup, before the first tag ever pushed

On PyPI, under **Account settings > Publishing**, add a pending publisher:

| Field        | Value        |
| ------------ | ------------ |
| PyPI project | `tk-uia`     |
| Publisher    | GitHub       |
| Owner        | `HuzPro`     |
| Repository   | `tk-uia`     |
| Workflow     | `publish.yml`|
| Environment  | `pypi`       |

This needs the maintainer's PyPI account and nothing else; there is no token to
create, store, scope, or revoke. A pending publisher is not a reservation:
PyPI names are first-come, and **the first successful upload is what claims
`tk-uia`.** If the name has gone by then, the fallback is the maintainer's
decision and belongs in `pyproject.toml` under `[project] name`; the import
package stays `tk_uia` either way.

## After the first publish

1. **Flip the README's install instructions.** The *Install* section opens with
   "Not on PyPI yet" and gives a clone; once the upload has succeeded that
   sentence is false and the block becomes `pip install tk-uia`. Deliberately
   not done in advance: a README claiming an install command that does not work
   is worse than one that undersells.
2. **Strike the ROADMAP entry.** *Publishing to PyPI* moves from *Next* to
   shipped.
3. **Cut a GitHub release** against the tag, with the CHANGELOG section as its
   body.
4. **Verify from the outside.** In a fresh virtual environment,
   `pip install tk-uia` and run the same one-liner as above. An upload that
   succeeded and a package that installs are different claims, which is the
   distinction this whole project is about.

## Decisions that are the maintainer's, not the release process's

- **`Development Status :: 3 - Alpha`** in `pyproject.toml`. Accurate today:
  no screen reader has verified the tree, which is the top ROADMAP item. Moving
  to `4 - Beta` is a judgement about that, not about the code.
- **The Python classifiers stop at 3.13**, which is what has been tested. 3.14
  runs the same code and is not claimed, because a classifier is a claim.
- **The README is the PyPI long description**, and PyPI does not resolve
  relative links. Every link in `README.md` that points at a repo file is
  therefore an absolute `https://github.com/HuzPro/tk-uia/blob/main/...` URL,
  and `COOKBOOK.md` and `docs/GUIDE.md` follow the same rule so that a reader
  who arrives from PyPI does not fall off the second page. In-page `#anchor`
  links stay relative.
