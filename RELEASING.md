# Releasing

How a version of tk-uia gets from this working copy onto PyPI. Written down
because a release is a thing done rarely and badly remembered, and because two
of the steps below can only be done by the maintainer holding the account.

Nothing here has been run against the real index yet: **0.6.0 is built,
installed from its own wheel and smoke-tested, and has not been uploaded.**
Everything up to *Publish* is proven; everything from *Publish* down is the plan.

## Before you build

1. **The suite is green, including the gui lane.** `./.venv/Scripts/python.exe -m
   pytest -q` — the gui specs open real windows and take about eighty seconds.
   The unit lane alone is not enough for a release: `_accprop.py` is untested by
   design, and the gui specs are the only thing that reads an annotation back
   out of Windows.
2. **`ruff check src tests probes` and `ruff format --check src tests probes`.**
3. **`__version__` in `src/tk_uia/__init__.py` is the version you are shipping.**
   It is the single source: `[tool.hatch.version]` reads the package, and
   `describe()` prints it in its own headline, so a stale one lands in every
   report an application prints.
4. **`CHANGELOG.md`'s top section is `## <version> — <date>`,** not
   `## Unreleased`, and the date is today's.
5. **`COVERAGE.md` is regenerated** if anything touched roles or annotation:
   `python probes/coverage_matrix.py`. It is measured, not written.
6. **The documented numbers still hold.** They live in `docs/GUIDE.md`, and the
   ones that go stale first are the `describe()` sample under *What your own
   application tells Windows* (re-run `probes/what_your_app_tells_windows.py`
   and paste), the gui spec count in *Measured*, and the coverage ratios. The
   `describe()` sample in `COOKBOOK.md` carries a version banner and goes stale
   the same way.

## Build

```powershell
./.venv/Scripts/python.exe -m pip install build
./.venv/Scripts/python.exe -m build
```

This produces `dist/tk_uia-<version>-py3-none-any.whl` and
`dist/tk_uia-<version>.tar.gz`. `dist/` is git-ignored.

> The repo's `.venv` is created by `uv`, which does not put `pip` in it. If
> `python -m pip` answers `No module named pip`, run
> `./.venv/Scripts/python.exe -m ensurepip --upgrade` first. `build` itself
> needs it: it creates an isolated environment per artifact and installs
> hatchling into it with pip.

Delete any older artifacts from `dist/` before uploading — `twine upload dist/*`
uploads whatever it finds, and re-uploading an existing version is refused by
PyPI rather than ignored.

## Check the artifacts

The wheel must contain the package and nothing else. `packages =
["src/tk_uia"]` in `pyproject.toml` is what ensures that; verify rather than
assume, because a wheel carrying `tests/` is only noticed by whoever installs
it.

```powershell
./.venv/Scripts/python.exe -c "import zipfile; print('\n'.join(sorted(zipfile.ZipFile('dist/tk_uia-0.6.0-py3-none-any.whl').namelist())))"
```

What to look for:

- `tk_uia/py.typed` is present — without it every type annotation in the package
  is invisible to a type checker in somebody else's project.
- No `tests/`, no `probes/`, no `.venv`. They belong in the sdist, which is a
  source distribution and should be able to run the suite; they do not belong in
  what an application installs.
- `tk_uia-<version>.dist-info/METADATA` says `Requires-Dist:` for the `dev`
  extra only. **Runtime dependencies are permanently zero** and that is the
  claim the whole package rests on — a stray runtime requirement is the one
  regression worth blocking a release for.

Then install the wheel the way a stranger will, in a virtual environment that
has never seen this repository:

```powershell
py -m venv $env:TEMP\tk-uia-smoke
$env:TEMP\tk-uia-smoke\Scripts\python.exe -m pip install dist\tk_uia-0.6.0-py3-none-any.whl
$env:TEMP\tk-uia-smoke\Scripts\python.exe -c "import tkinter as tk, tk_uia; r = tk.Tk(); r.withdraw(); s = tk_uia.enable(r); assert s is tk_uia.Strategy.ANNOTATED, s; print(tk_uia.__version__, s)"
Remove-Item -Recurse -Force $env:TEMP\tk-uia-smoke
```

`pip list` in that environment must show `tk-uia` and `pip` and nothing else.
The assertion is the point: `enable()` returning `NATIVE` or `UNSUPPORTED` where
`ANNOTATED` was expected is exactly the silent no-op this package exists to
refuse, and an install that imports cleanly and annotates nothing would pass any
weaker check.

## Publish

**This step needs the maintainer's PyPI account, and cannot be done by anyone
else or by any automation that does not hold the token.**

1. Sign in to PyPI and create an **API token** — Account settings → API tokens.
   Scope it to the `tk-uia` project once the project exists; the *first* upload
   has no project to scope to, so it needs an account-wide token, which should
   be revoked and replaced with a scoped one immediately afterwards.
2. Put it where the tool will find it. `twine` reads `TWINE_USERNAME=__token__`
   and `TWINE_PASSWORD=pypi-…` from the environment, or `~/.pypirc`. **The token
   is a credential and belongs in neither this repository nor any note in it.**
3. Upload:

   ```powershell
   ./.venv/Scripts/python.exe -m pip install twine
   ./.venv/Scripts/python.exe -m twine check dist/*
   ./.venv/Scripts/python.exe -m twine upload dist/*
   ```

   `hatch publish` is the equivalent if hatch is already installed; it reads the
   same token and uploads the same two files. There is no reason to prefer one.

   Rehearsing against **TestPyPI** first (`twine upload --repository testpypi
   dist/*`) costs one extra token and is worth it for a first upload, since the
   name claim below is not reversible.

### About the name

`tk-uia` was **verified free on PyPI when this project started**, and it is
still not claimed by anything of ours. That is not a reservation: PyPI names are
first-come, nothing prevents somebody else registering `tk-uia` in the meantime,
and **the first successful upload is what claims it.** If the name has gone by
the time this is run, the decision — a different distribution name with the same
import name, or a different name entirely — is the maintainer's and belongs in
`pyproject.toml` under `[project] name`, nowhere else. The import package stays
`tk_uia` either way.

## After publishing

1. **Tag the commit and push the tag.**

   ```powershell
   git tag -a v0.6.0 -m "0.6.0"
   git push origin v0.6.0
   ```

2. **Cut a GitHub release** against that tag, with the CHANGELOG section for the
   version as its body.
3. **Flip the README's install instructions.** The *Install* section currently
   opens with "tk-uia is not on PyPI yet" and gives a `git clone` +
   `pip install -e .`. Once the upload has succeeded that sentence is false, and
   the block becomes:

   ```bash
   pip install tk-uia
   ```

   **This has deliberately not been done yet.** A README claiming an install
   command that does not work is worse than one that undersells, and until the
   upload succeeds the git-clone route is the true one.
4. **Strike the ROADMAP entry.** *Publishing to PyPI* moves from *Next* to
   shipped, and the "The name is free" line stops being true in the way it was
   written.
5. **Verify from the outside.** In a fresh virtual environment,
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
  therefore an absolute `https://github.com/HuzPro/tk-uia/blob/main/…` URL, and
  `COOKBOOK.md` and `docs/GUIDE.md` follow the same rule so that a reader who
  arrives from PyPI does not fall off the second page. In-page `#anchor` links
  stay relative. Anything added to those three files has to keep the
  convention; nothing enforces it.
