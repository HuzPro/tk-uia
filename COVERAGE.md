# What a Windows accessibility client sees in Tkinter

Measured, not asserted: every row below is one widget in a real window,
read back through UI Automation from another process. Regenerate with
`python probes/coverage_matrix.py`.

The two views are joined by rectangle rather than by name, because a
widget whose class has no role is never annotated and so has no name to
join on — and those are the rows worth having.

## classic tk

| widget | `winfo_class` | bare Tk | after `enable()` | + what the app says | patterns | `describe()` says | a test writes |
|---|---|---|---|---|---|---|---|
| `tk.Label` | `Label` | `ImageControl` — | `TextControl` 'a Label' | `TextControl` 'a Label' |  | — | `app.text("a Label")` |
| `tk.Button` | `Button` | `ButtonControl` — | `ButtonControl` 'a Button' | `ButtonControl` 'a Button' | Invoke | CANNOT_BE_PRESSED | `app.button("a Button")` |
| `tk.Entry` | `Entry` | `PaneControl` — | `EditControl` — | `EditControl` 'Task title' | Value | — | `app.textbox("Task title")` |
| `tk.Text` | `Text` | `PaneControl` — | `EditControl` — | `EditControl` 'Notes' | Value | NO_VALUE | `app.textbox("Notes")` |
| `tk.Checkbutton` | `Checkbutton` | `ButtonControl` — | `CheckBoxControl` 'a Checkbutton' | `CheckBoxControl` 'a Checkbutton' | Toggle, Invoke | — | `app.checkbox("a Checkbutton")` |
| `tk.Radiobutton` | `Radiobutton` | `ButtonControl` — | `RadioButtonControl` 'a Radiobutton' | `RadioButtonControl` 'a Radiobutton' | SelectionItem, Invoke | — | `app.radio("a Radiobutton")` |
| `tk.Scale` | `Scale` | `PaneControl` — | `SliderControl` — | `SliderControl` 'Volume' |  | — | `app.slider("Volume")` |
| `tk.Scrollbar` | `Scrollbar` | `ScrollBarControl` — | `ScrollBarControl` — | `ScrollBarControl` 'Scroll the results' | RangeValue | — | `app.scrollbar("Scroll the results")` |
| `tk.Spinbox` | `Spinbox` | `PaneControl` — | `SpinnerControl` — | `SpinnerControl` 'Quantity' | Value | — | `app.spinbox("Quantity")` |
| `tk.Message` | `Message` | `PaneControl` — | `TextControl` 'a Message' | `TextControl` 'a Message' |  | — | `app.text("a Message")` |
| `tk.Listbox` | `Listbox` | `PaneControl` — | `ListControl` — | `ListControl` 'Search results' | Selection | ITEMS_NOT_IN_THE_TREE | `app.listbox("Search results")` |
| `tk.Canvas` | `Canvas` | `PaneControl` — | `ImageControl` — | `ImageControl` 'Activity sparkline' |  | — | `app.image("Activity sparkline")` |
| `tk.Frame` | `Frame` | `PaneControl` — | `GroupControl` — | `GroupControl` 'Details' |  | — | `app.group("Details")` |
| `tk.LabelFrame` | `Labelframe` | `PaneControl` — | `GroupControl` 'a LabelFrame' | `GroupControl` 'a LabelFrame' |  | — | `app.group("a LabelFrame")` |
| `tk.PanedWindow` | `Panedwindow` | `PaneControl` — | `GroupControl` — | `GroupControl` 'Split view' |  | — | `app.group("Split view")` |
| `tk.Menu (on a Menubutton)` | `Menu` | *not on screen* | *not on screen* | *not on screen* | — | NEVER_MAPPED | — |
| `tk.Menubutton` | `Menubutton` | `PaneControl` — | `SplitButtonControl` 'a Menubutton' | `SplitButtonControl` 'a Menubutton' | Invoke | — | `app.split_button("a Menubutton")` |
| `tk.OptionMenu` | `Menubutton` | `PaneControl` — | `SplitButtonControl` 'one' | `SplitButtonControl` 'one' | Invoke | — | `app.split_button("one")` |
| `tk.Menu (menubar)` | `Menu` | *not on screen* | *not on screen* | *not on screen* | — | NEVER_MAPPED | — |
| `tk.Toplevel` | `Toplevel` | `PaneControl` — | `PaneControl` — | `PaneControl` — |  | NAMED_BY_ITS_TITLE | **no query** |

**20 widget classes surveyed, 2 never on screen.**

| of 18 on screen | typed | named | queryable |
|---|---|---|---|
| bare Tk | 5 | 0 | — |
| after `enable()` | 17 | 8 | — |
| **+ what the app says** | **17** | **17** | **17** |

*24 queries offered for this window.*

## ttk

| widget | `winfo_class` | bare Tk | after `enable()` | + what the app says | patterns | `describe()` says | a test writes |
|---|---|---|---|---|---|---|---|
| `ttk.Label` | `TLabel` | `PaneControl` — | `TextControl` 'a Label' | `TextControl` 'a Label' |  | — | `app.text("a Label")` |
| `ttk.Button` | `TButton` | `PaneControl` — | `ButtonControl` 'a Button' | `ButtonControl` 'a Button' | Invoke | CANNOT_BE_PRESSED | `app.button("a Button")` |
| `ttk.Entry` | `TEntry` | `PaneControl` — | `EditControl` — | `EditControl` 'Task title' | Value | — | `app.textbox("Task title")` |
| `ttk.Checkbutton` | `TCheckbutton` | `PaneControl` — | `CheckBoxControl` 'a Checkbutton' | `CheckBoxControl` 'a Checkbutton' | Toggle | — | `app.checkbox("a Checkbutton")` |
| `ttk.Radiobutton` | `TRadiobutton` | `PaneControl` — | `RadioButtonControl` 'a Radiobutton' | `RadioButtonControl` 'a Radiobutton' | SelectionItem | — | `app.radio("a Radiobutton")` |
| `ttk.Combobox` | `TCombobox` | `PaneControl` — | `ComboBoxControl` — | `ComboBoxControl` 'Priority' | Value | — | `app.combobox("Priority")` |
| `ttk.Spinbox` | `TSpinbox` | `PaneControl` — | `SpinnerControl` — | `SpinnerControl` 'Quantity' | Value | — | `app.spinbox("Quantity")` |
| `ttk.Scale` | `TScale` | `PaneControl` — | `SliderControl` — | `SliderControl` 'Volume' |  | — | `app.slider("Volume")` |
| `ttk.Scrollbar` | `TScrollbar` | `PaneControl` — | `ScrollBarControl` — | `ScrollBarControl` 'Scroll the results' |  | — | `app.scrollbar("Scroll the results")` |
| `ttk.Progressbar` | `TProgressbar` | `PaneControl` — | `ProgressBarControl` — | `ProgressBarControl` 'Upload progress' | Value | NO_VALUE | `app.progressbar("Upload progress")` |
| `ttk.Separator` | `TSeparator` | `PaneControl` — | `SeparatorControl` — | `SeparatorControl` 'Divider' |  | — | `app.separator("Divider")` |
| `ttk.Sizegrip` | `TSizegrip` | `PaneControl` — | `ThumbControl` — | `ThumbControl` 'Resize this window' |  | — | `app.thumb("Resize this window")` |
| `ttk.Frame` | `TFrame` | `PaneControl` — | `GroupControl` — | `GroupControl` 'Details' |  | — | `app.group("Details")` |
| `ttk.Labelframe` | `TLabelframe` | `PaneControl` — | `GroupControl` 'a Labelframe' | `GroupControl` 'a Labelframe' |  | — | `app.group("a Labelframe")` |
| `ttk.Panedwindow` | `TPanedwindow` | `PaneControl` — | `GroupControl` — | `GroupControl` 'Split view' |  | — | `app.group("Split view")` |
| `ttk.Notebook` | `TNotebook` | `PaneControl` — | `TabControl` — | `TabControl` 'Settings' | Selection | — | `app.tab_strip("Settings")` |
| `ttk.Treeview` | `Treeview` | `PaneControl` — | `TreeControl` — | `TreeControl` 'Task list' | Selection | ITEMS_NOT_IN_THE_TREE | `app.tree("Task list")` |
| `ttk.LabeledScale` | `TFrame` | `PaneControl` — | `GroupControl` — | `GroupControl` 'Brightness' |  | — | `app.group("Brightness")` |
| `ttk.Menu (on a Menubutton)` | `Menu` | *not on screen* | *not on screen* | *not on screen* | — | NEVER_MAPPED | — |
| `ttk.Menubutton` | `TMenubutton` | `PaneControl` — | `SplitButtonControl` 'a Menubutton' | `SplitButtonControl` 'a Menubutton' | Invoke | — | `app.split_button("a Menubutton")` |
| `ttk.OptionMenu` | `TMenubutton` | `PaneControl` — | `SplitButtonControl` 'one' | `SplitButtonControl` 'one' | Invoke | — | `app.split_button("one")` |

**21 widget classes surveyed, 1 never on screen.**

| of 20 on screen | typed | named | queryable |
|---|---|---|---|
| bare Tk | 0 | 0 | — |
| after `enable()` | 20 | 7 | — |
| **+ what the app says** | **20** | **20** | **20** |

*28 queries offered for this window.*

