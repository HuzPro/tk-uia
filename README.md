# tk-uia

[![tests](https://github.com/HuzPro/tk-uia/actions/workflows/tests.yml/badge.svg)](https://github.com/HuzPro/tk-uia/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/HuzPro/tk-uia/blob/main/LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Make Tkinter applications readable by Windows screen readers and UI Automation.

Tk 8.6 exposes widgets to Windows accessibility with no names and mostly wrong
control types: buttons are unnamed, labels read as images, and every themed
`ttk` widget is an anonymous pane. `tk_uia.enable(root)` annotates each widget
through MSAA, so screen readers such as NVDA, and UIA tools such as Inspect.exe
or [pytest-uia](https://github.com/HuzPro/pytest-uia), see named, correctly
typed controls instead. No runtime dependencies, no C extension, no visible
change to the window.

## Install

Not on PyPI yet ([RELEASING.md](https://github.com/HuzPro/tk-uia/blob/main/RELEASING.md)
has the plan). Install from a clone:

```bash
git clone https://github.com/HuzPro/tk-uia
cd tk-uia
pip install -e .
```

Windows only. On other platforms `enable()` returns `UNSUPPORTED` and does
nothing, so cross-platform code can call it unconditionally.

## Usage

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

| Widget | Bare Tk | After `enable()` |
|---|---|---|
| `tk.Button(text="New Task")` | `ButtonControl`, no name | `ButtonControl`, `Name='New Task'` |
| `tk.Label(text="Task list")` | `ImageControl`, no name | `TextControl`, `Name='Task list'` |
| `tk.Checkbutton(text="Done")` | `ButtonControl`, no name | `CheckBoxControl`, live `ToggleState` |
| `tk.Entry(textvariable=var)` | `PaneControl`, no ValuePattern | `EditControl`, value follows the variable |

Measured from a separate process. [COVERAGE.md](https://github.com/HuzPro/tk-uia/blob/main/COVERAGE.md)
has the table for every widget class in both toolkits.
[COOKBOOK.md](https://github.com/HuzPro/tk-uia/blob/main/COOKBOOK.md) builds a
real form end to end.

## Features

- One call covers the whole application, including windows opened later.
- Names inferred from `-text`, correct control types for classic `tk` and `ttk`.
- A declared `textvariable` is followed automatically: the name or value stays
  current with no further code.
- `label_for(label, entry)` records which caption names which field.
  `infer_names_from_layout(root)` retrofits an existing dialog in one call and
  reports every name it chose.
- `describe(root)` prints an audit of what a client gets and what is missing,
  with a reason and a fix per widget. Usable as data for CI gating.
- Notebook tabs become real, clickable tab controls.
- Detects Tk 9.1's native accessibility (TIP 733) and stands down.

## Limitations

- In-process only. You can annotate your own application, not someone else's.
- `InvokePattern` on a Tk button does nothing; assistive technology and test
  tools must click. See the
  [guide](https://github.com/HuzPro/tk-uia/blob/main/docs/GUIDE.md#the-limitation-findable-and-readable-is-not-activatable).
- Listbox rows and Treeview items are not exposed. Notebook tabs are.
- Verified against the UI Automation tree, which is what screen readers
  consume. Not yet verified against NVDA speech output; that is the top
  [roadmap](https://github.com/HuzPro/tk-uia/blob/main/ROADMAP.md) item.

## Documentation

| | |
|---|---|
| [COOKBOOK.md](https://github.com/HuzPro/tk-uia/blob/main/COOKBOOK.md) | Your first accessible form, in ten minutes. |
| [docs/GUIDE.md](https://github.com/HuzPro/tk-uia/blob/main/docs/GUIDE.md) | Full API, how it works, every caveat and measurement. |
| [COVERAGE.md](https://github.com/HuzPro/tk-uia/blob/main/COVERAGE.md) | Every widget class, measured bare and after `enable()`. |
| [ROADMAP.md](https://github.com/HuzPro/tk-uia/blob/main/ROADMAP.md) | What is next and what is out of scope. |
| [CHANGELOG.md](https://github.com/HuzPro/tk-uia/blob/main/CHANGELOG.md) | Release history. |

## License

[MIT](https://github.com/HuzPro/tk-uia/blob/main/LICENSE)
