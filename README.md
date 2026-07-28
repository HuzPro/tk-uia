# tk-uia

[![tests](https://github.com/HuzPro/tk-uia/actions/workflows/tests.yml/badge.svg)](https://github.com/HuzPro/tk-uia/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/HuzPro/tk-uia/blob/main/LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Make Tkinter applications fully accessible to Windows screen readers and UI
Automation: named, correctly typed, and activatable.

Tk 8.6 exposes widgets to Windows accessibility with no names and mostly wrong
control types: buttons are unnamed, labels read as images, and every themed
`ttk` widget is an anonymous pane. `tk_uia.enable(root)` fixes both halves.
Each widget is annotated through MSAA for legacy clients, and answers UI
Automation for itself: `Invoke` genuinely presses, `Value` genuinely types,
`Toggle`, `SelectionItem` and `RangeValue` genuinely act, and names and states
are read live from the widget at the moment a client asks. Screen readers such
as NVDA, and UIA tools such as Inspect.exe or
[pytest-uia](https://github.com/HuzPro/pytest-uia), see controls they can both
read and operate. No runtime dependencies, no C extension, no visible change
to the window.

## Install

```bash
pip install tk-uia
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

`enable()` comes first: every other call (`set_acc_name`, `label_for`, the
`bind_*` family) refuses until it has run.

| Widget | Bare Tk | After `enable()` |
|---|---|---|
| `tk.Button(text="New Task")` | `ButtonControl`, no name, Invoke does nothing | `ButtonControl`, `Name='New Task'`, Invoke presses it |
| `tk.Label(text="Task list")` | `ImageControl`, no name | `TextControl`, name read live |
| `tk.Checkbutton(text="Done")` | `ButtonControl`, no name | `CheckBoxControl`, Toggle works, live `ToggleState` |
| `tk.Entry(textvariable=var)` | `PaneControl`, no ValuePattern | `EditControl`, SetValue types into it |
| `ttk.Button(text="Save")` | anonymous `PaneControl` | `ButtonControl`, named, Invoke presses it |
| `tk.Scale(from_=0, to=10)` | `PaneControl` | `SliderControl`, RangeValue moves it |

Measured from a separate process. [COVERAGE.md](https://github.com/HuzPro/tk-uia/blob/main/COVERAGE.md)
has the table for every widget class in both toolkits.
[COOKBOOK.md](https://github.com/HuzPro/tk-uia/blob/main/COOKBOOK.md) builds a
real form end to end.

## Features

- One call covers the whole application, including windows opened later.
- Working patterns per class: `Invoke` for buttons, `Toggle` for checkbuttons,
  `SelectionItem` for radiobuttons and notebook tabs, `Value` for entries,
  spinboxes, comboboxes and `Text`, `RangeValue` for scales and progressbars.
- Names, values, enabled state, help and description are pulled live at the
  moment a client asks; name and value changes are raised as UIA
  property-changed events.
- Names inferred from `-text`, correct control types for classic `tk` and `ttk`.
- A declared `textvariable` is followed automatically: the name or value stays
  current with no further code.
- `label_for(label, entry)` records which caption names which field.
  `infer_names_from_layout(root)` retrofits an existing dialog in one call and
  reports every name it chose.
- `describe(root)` returns an audit you can `print()`: what a client gets and
  what is missing, with a reason and a fix per widget. Usable as data for CI
  gating.
- Notebook tabs become real tab controls a client can switch without a click.
- `annotate_only(root)` keeps the previous annotation-only behaviour, and
  `leave_to_the_proxy(widget)` opts a single widget out.
- Detects Tk 9.1's native accessibility (TIP 733) and stands down.

## Limitations

- In-process only. You can make your own application accessible, not someone
  else's.
- Listbox rows and Treeview items are not exposed. Notebook tabs are.
- A combobox has no ExpandCollapse yet, so a client cannot open its dropdown;
  choosing goes through `ValuePattern.SetValue`, which on a readonly combobox
  takes exactly the values a user could pick and fires the same
  `<<ComboboxSelected>>` a dropdown choice would.
- `infer_names_from_layout` is a guess by convention: rows are frames, or grid
  rows within a frame, read across their columns. It returns every name it
  chose; read the guess before shipping it.
- A widget left to the MSAA proxy advertises an `InvokePattern` that does
  nothing; that is the proxy's own behaviour, and `describe()` says which
  widgets it applies to.
- Verified against the UI Automation tree, which is what screen readers
  consume. Not yet verified against NVDA speech output; that is what 1.0
  means on the [roadmap](https://github.com/HuzPro/tk-uia/blob/main/ROADMAP.md).

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
