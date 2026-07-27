# tk-uia

[![tests](https://github.com/HuzPro/tk-uia/actions/workflows/tests.yml/badge.svg)](https://github.com/HuzPro/tk-uia/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/HuzPro/tk-uia/blob/main/LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**Your Tkinter application is unreadable to a screen reader. One call makes it
findable and readable.**

A blind user running NVDA over a Tk 8.6 window hears almost nothing useful.
Buttons are unnamed, labels are announced as pictures, and every themed `ttk`
widget is an anonymous pane. The words are on the screen and none of them are in
the accessibility tree. `tk_uia.enable(root)` puts them there, with zero runtime
dependencies, no C extension, no `ttk` rewrite, and nothing visible on screen.

The same call makes the window drivable by UI Automation tooling: pytest-uia,
pywinauto, Inspect.exe, Accessibility Insights. Real accessibility is a better
test hook than a test hook.

## Install

tk-uia is not on PyPI yet. The wheel builds, installs and annotates; the upload
is the step that has not happened, and
[RELEASING.md](https://github.com/HuzPro/tk-uia/blob/main/RELEASING.md) has the
plan. Install from a clone:

```bash
git clone https://github.com/HuzPro/tk-uia
cd tk-uia
pip install -e .
```

Windows only. Off Windows `enable()` returns `UNSUPPORTED` and does nothing, so
cross-platform code can call it unconditionally.

## Quickstart

One call, once, after building your window.

```python
import tkinter as tk
import tk_uia

root = tk.Tk()
root.title("Tasks")
tk.Label(root, text="Task list").pack()
tk.Button(root, text="New Task", command=create).pack()

tk_uia.enable(root)
root.mainloop()
```

What a UI Automation client reads, measured from a separate process against Tk
8.6.15 on Windows 11:

| Widget | Bare Tk | After `enable()` |
|---|---|---|
| `tk.Button(text="New Task")` | `ButtonControl`, `Name=''` | `ButtonControl`, `Name='New Task'` |
| `tk.Label(text="Task list")` | `ImageControl`, `Name=''` | `TextControl`, `Name='Task list'` |
| `tk.Checkbutton(text="Done")` | `ButtonControl`, `Name=''` | `CheckBoxControl`, `Name='Done'`, `ToggleState` correct and live |
| `tk.Entry(textvariable=var)` | `PaneControl`, `Name=''`, no ValuePattern | `EditControl`, ValuePattern reads the variable and follows it |

Next: [COOKBOOK.md](https://github.com/HuzPro/tk-uia/blob/main/COOKBOOK.md)
builds one real form end to end, in ten minutes.

## What it does

- `enable(root)` annotates every widget in the application and returns which of
  `ANNOTATED` / `NATIVE` / `UNSUPPORTED` happened, so a gate that mis-fires is
  not silent. One call covers every window the application opens.
- Widgets carrying a `-text` are named from it. Every widget gets the right
  control type, across both classic `tk` and `ttk`.
- A widget that declared a `textvariable` is followed automatically. Its name or
  its value stays in step with the variable, with no further call and no way to
  go stale.
- `label_for(caption, entry)` says which label speaks for which entry. Tk records
  that nowhere, so it is the one thing no library can read back on its own.
- `infer_names_from_layout(root)` is the retrofit for a dialog that already has
  fifty rows. It applies your form's own row-and-caption convention and returns
  every name it chose. On a six-tab settings dialog it took 83 of 110 controls
  addressable to 110 of 110.
- `describe(root)` reports what your application has told Windows, and names
  every widget it did not, with a reason for each. It touches no COM and no UI
  Automation, so you can leave the call in a production build.
- Names are inferred, never invented. A widget with no words gets a role and no
  name, because a listbox announced as `.!listbox` looks like it worked.

The full API, the measurements behind each line, and the design reasoning are in
[docs/GUIDE.md](https://github.com/HuzPro/tk-uia/blob/main/docs/GUIDE.md).

## Three things to know before adopting it

- **Annotation is in-process only.** You can annotate your own application and
  nothing else. Reaching for another process's window does not raise, it does
  nothing, and it can corrupt an annotation that process made for itself.
  [Details](https://github.com/HuzPro/tk-uia/blob/main/docs/GUIDE.md#in-process-only).
- **`Invoke` lies.** An annotated Tk button advertises an `InvokePattern` and a
  `DefaultAction` of "Press", and both return cleanly without running the Tk
  command. Assistive technology and test tools have to click.
  [The measurement](https://github.com/HuzPro/tk-uia/blob/main/docs/GUIDE.md#the-limitation-findable-and-readable-is-not-activatable).
- **List and tree items are not in the tree.** A `Listbox` is a findable
  `ListControl` whose rows are absent, and the same goes for `Treeview` items. A
  `ttk.Notebook`'s tabs are the exception and are reachable.
  [Details](https://github.com/HuzPro/tk-uia/blob/main/docs/GUIDE.md#notebook-tabs-are-reachable-other-compound-widget-items-are-not).

One more, stated plainly: nothing here has been heard out loud. Everything is
read back through UI Automation, which is the API a screen reader consumes.
"NVDA can read this tree" is evidenced. "NVDA says the right thing at the right
moment" is not, and closing that gap is the top roadmap item.

## Documentation

| | |
|---|---|
| [COOKBOOK.md](https://github.com/HuzPro/tk-uia/blob/main/COOKBOOK.md) | Your first accessible form, in ten minutes. Start here. |
| [docs/GUIDE.md](https://github.com/HuzPro/tk-uia/blob/main/docs/GUIDE.md) | The reference. Full API, how it works, every caveat, every measurement. |
| [COVERAGE.md](https://github.com/HuzPro/tk-uia/blob/main/COVERAGE.md) | Every widget class in both toolkits, measured bare and after `enable()`. Regenerated by a probe, not written. |
| [ROADMAP.md](https://github.com/HuzPro/tk-uia/blob/main/ROADMAP.md) | What is next, and what is a deliberate non-goal. |
| [CHANGELOG.md](https://github.com/HuzPro/tk-uia/blob/main/CHANGELOG.md) | What changed in each version. |
| [RELEASING.md](https://github.com/HuzPro/tk-uia/blob/main/RELEASING.md) | How a version gets from this working copy onto PyPI. |

## This library stands down at Tk 9.1

TIP 733 puts MSAA in Tk itself, with the same role mapping this package uses.
`enable()` detects it, binds nothing and reports `NATIVE`. Tk 9.1 is expected
stable around September 2026 and CPython is unlikely to bundle it before 3.16,
which is the gap this fills.
[The forward path](https://github.com/HuzPro/tk-uia/blob/main/docs/GUIDE.md#the-forward-path-this-library-is-deliberately-temporary).

## License

[MIT](https://github.com/HuzPro/tk-uia/blob/main/LICENSE)
