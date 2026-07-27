# tk-uia

[![tests](https://github.com/HuzPro/tk-uia/actions/workflows/tests.yml/badge.svg)](https://github.com/HuzPro/tk-uia/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**Your Tkinter application is unreadable to a screen reader. One call makes it
findable and readable.**

A blind user running NVDA over a Tk 8.6 window hears almost nothing useful. The
button is announced as an unnamed button. The label beside it is announced as a
*picture*. The text box, the listbox and every themed `ttk` widget in the window
are announced as anonymous panes. The words are on the screen; none of them are
in the accessibility tree.

```python
import tkinter as tk
import tk_uia

root = tk.Tk()
tk.Button(root, text="New Task").pack()
tk_uia.enable(root)          # ← the whole of it
```

After that call the same window offers a `ButtonControl` named "New Task", a
`TextControl` that reads its own words, and an `EditControl` where Tk offered an
anonymous pane. Zero runtime dependencies, no C extension, no `ttk` rewrite,
nothing visible on screen.

**One call is where it starts, not where it ends.** `enable()` names every
widget that carries its own words and gives every widget the right control type.
What it cannot do on its own is read a value out of a widget that does not hold
one: an entry showing `buy milk` arrives as an `EditControl` whose ValuePattern
is `''` — measured, and a confidently wrong answer where bare Tk gave no answer
at all. One more line (`bind_value_variable`) fixes that, and the table below
marks exactly which cells each call is responsible for. This README's job is to
tell you which is which before you ship it to somebody who depends on it.

Because the mechanism is real accessibility rather than a test hook, the same
call also makes the window drivable by UI Automation tooling — pytest-uia,
pywinauto, Inspect.exe, Accessibility Insights. That is the second audience, and
it is a consequence rather than the point.

### The claim, stated precisely

It is often said that "Tk exposes no accessibility tree". That is **not true**,
and the sloppy version of the claim is worth correcting because someone will
check. Probed against Tk 8.6.15 on Windows 11, across 30 widget types:

- The toplevel **is** in the tree, as a `WindowControl` with the right title.
- Every widget **is** in the tree — Tk creates one real HWND per widget — and
  every `BoundingRectangle` is correct.
- `Name` and `AutomationId` are **empty for all 30**.
- `tk.Button` / `Checkbutton` / `Radiobutton` are `ButtonControl`.
  `tk.Label` is an **`ImageControl`**. `tk.Entry`, `Text`, `Canvas`, `Listbox`
  and **all 15 `ttk` widget types** are anonymous `PaneControl`.

So the accurate statement is: **Tk exposes unnamed, mis-roled controls.** There
is structure; there is nothing to announce and nothing to match on. No amount of
cleverness in the client fixes that, because there is no name to search for. The
application has to say who its widgets are — which is exactly what `enable()`
does on its behalf.

### Is this for you?

| Your situation | What to reach for |
|---|---|
| Tkinter app **you own**, and you want screen-reader users to be able to use it | **tk-uia.** This is the whole reason it exists. |
| Tkinter app you own, and you want GUI acceptance tests that query by name and role rather than by pixel | **tk-uia**, then any UIA-based tool. Making it testable and making it accessible are the same act. |
| Tk **9.1 or later** | **Nothing — use Tk's own.** TIP 733 puts MSAA in Tk itself, with the same role mapping. `tk_uia.enable()` detects it, stands down and reports `NATIVE`. |
| A Tk app you **cannot modify** | **Not this.** Annotation is in-process only. There is a narrow cross-process rescue — see [below](#the-app-you-cannot-modify) — but it sets names only, and misusing it corrupts apps that annotate themselves properly. |
| macOS or Linux | **Not this.** MSAA is a Windows API; `enable()` returns `UNSUPPORTED` and does nothing, so cross-platform code can call it unconditionally. Tk's Linux accessibility is an ATK problem and a different project. |
| You need the assistive technology or test tool to *press* the button | **Read [the limitation](#the-limitation-findable-and-readable-is-not-activatable) first.** Annotation makes widgets findable and readable. It does not make `InvokePattern` work, and `InvokePattern` on a Tk button lies. |
| PyQt, wxPython, WinForms, WPF | **Nothing.** They are accessible already. |

## Quickstart

tk-uia is **not on PyPI** — publishing is out of scope for now (see
[ROADMAP](ROADMAP.md)). Install it from a clone:

```bash
git clone https://github.com/HuzPro/tk-uia
cd tk-uia
pip install -e .
```

Then, once, after building your window:

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

What a UI Automation client reads, before and after that one call — measured
from a **separate process**, against the fixture app in this repo and
`probes/what_enable_alone_gives_you.py`:

| Widget | Bare Tk 8.6 | After `enable()` **alone** | With one more line |
|---|---|---|---|
| `tk.Button(text="New Task")` | `ButtonControl`, `Name=''` | `ButtonControl`, **`Name='New Task'`** | — |
| `tk.Label(text="Task list")` | **`ImageControl`**, `Name=''` | **`TextControl`**, **`Name='Task list'`** | — |
| `tk.Checkbutton(text="Done")` | `ButtonControl`, `Name=''` | **`CheckBoxControl`**, **`Name='Done'`**, **`ToggleState`** correct and live | — |
| `tk.Entry` (showing `buy milk`) | `PaneControl`, `Name=''`, no ValuePattern | **`EditControl`**, `Name=''`, ValuePattern **`''`** | `set_acc_name(e, "Title")` → `Name='Title'`; `bind_value_variable(e, var)` → ValuePattern `'buy milk'` |
| `tk.Canvas` (this package has no role for one) | `PaneControl`, `Name=''` | unchanged — the control group | — |

**Read the Entry row carefully.** An entry keeps neither its label nor its
contents on the widget: the label is a separate `tk.Label` this package has no
way to associate, and the contents live in a Tk variable. So `enable()` gives it
the right control type and a ValuePattern that did not exist before — and that
pattern reads `''` until an application says otherwise. That is the one place
where annotating alone leaves a client a *confident wrong answer* rather than no
answer, and it is two lines to fix.

Widgets with a `-text` option are named from it automatically. Everything else
takes one line:

| Call | What it does |
|---|---|
| `enable(root, roles=None)` | Annotate this application, and **return** which of `ANNOTATED` / `NATIVE` / `UNSUPPORTED` happened. |
| `set_acc_name(widget, name)` | The name a screen reader announces. Needed for anything with no `-text`. |
| `set_acc_value(widget, value)` | What a client reads out of an edit control. |
| `bind_text_variable(widget, variable)` | Keep the name in step with a `StringVar`, so a status line stays truthful. |
| `bind_value_variable(widget, variable)` | Keep the value in step with a `StringVar`, so an entry never reads back what it used to hold. |
| `set_acc_role(widget, Role.…)` | Override the inferred role. |
| `set_acc_description` / `set_acc_help` / `set_acc_action` / `set_acc_state` | The rest of the MSAA properties. |
| `set_automation_id(widget, number)` | An explicit, stable id for a test suite to pin to. |
| `add_acc_object(widget)` | Annotate one widget by hand, re-reading its `-text` — which is how a name is un-staled after `config(text=…)`. |
| `forget(widget)` | Take every annotation back off a widget, and stop following any variable bound to it. |
| `describe(root)` | Say what this application has told Windows about its widgets, and name every widget it did not. |
| `check_screenreader()` | Whether Windows believes something is reading the screen aloud. |

`enable()` **returns** its strategy rather than logging it, because "annotated"
and "the version gate mis-fired and this did nothing at all" are otherwise the
same silence. The fixture app in this repo asserts `Strategy.ANNOTATED` and
refuses to start otherwise, and a suite of your own should do the same.

Names are inferred, never invented. A widget with no `-text` gets its **role**
set and no name at all: a listbox announced as `.!listbox` is worse than one
announced as an unnamed list, because it looks like it worked.

## How it works

Windows has two accessibility APIs, and the newer one is built on top of the
older one. UI Automation serves any plain HWND through a built-in **MSAA proxy**
— which is why Tk shows up in the tree at all, unnamed. MSAA in turn lets any
process **annotate** the accessible properties of its own windows, through the
`IAccPropServices` COM interface in `oleacc.dll`. UI Automation reads those
annotations back out through an **Annotation Proxy** that takes priority over
the plain one.

So `enable()`:

1. Asks the Tcl interpreter for `tk windowingsystem` and `info patchlevel`, and
   decides between annotating, standing down for a native Tk, and doing nothing
   off Windows.
2. Binds `<Map>` and `<Destroy>` on the `all` bindtag with `add="+"`, so every
   widget Tk maps from then on is annotated as it appears, and every widget Tk
   destroys has its annotations cleared. `add="+"` matters: anything else
   silently replaces whatever Tk and your application already had bound.
3. Sweeps everything already on screen, because `<Map>` fires once, on the way
   up, and will not fire again for a window that was already showing.
4. For each widget, looks `winfo_class()` up in `ROLE_FOR_TK_CLASS` and writes
   `PROPID_ACC_ROLE`, plus `PROPID_ACC_NAME` from `-text` when there is one.

The roles come from `oleacc.h` and deliberately mirror the mapping Tk 9.1 uses,
so migrating later is close to deletion. The `41`/`42` split is load-bearing:
`ROLE_SYSTEM_STATICTEXT` (41) becomes a `TextControl`, and `ROLE_SYSTEM_TEXT`
(42) becomes an `EditControl` **and gains a ValuePattern that did not exist
before**. Annotating a role is not putting a label on an object; it changes
which patterns the bridge offers for it at all.

Two details in `_accprop.py` return `S_OK` and do nothing when they are wrong,
so neither is guessed at: every `PROPID_ACC_*` GUID is transcribed from
`oleacc.h` rather than recalled (`PROPID_ACC_HELP` is *not* the value intuition
suggests), and `MSAAPROPID` is a `typedef GUID`, so `idProp` is passed **by
value** — passing a pointer compiles, runs, returns `S_OK` and annotates
nothing.

### In-process only

`IAccPropServices` annotates **the calling process's own windows**. Reaching for
another process's HWND does not raise; it silently does nothing, and can
**corrupt an annotation that process made for itself**. There is no supported
way to annotate somebody else's Tk app, and attempting it can make a
well-behaved one worse.

`enable()` also records the thread it ran on and refuses calls from any other,
raising `AnnotationRefused` rather than corrupting anything. Tk and the COM
apartment both belong to the thread that entered them; marshal back with
`root.after(0, ...)`.

### `ttk` is strictly worse than classic `tk`

Counter-intuitive, and measured across all 15 themed widget types: **every
`ttk` widget is an anonymous `PaneControl`**, and `ttk.Button` has **no
InvokePattern at all** — where classic `tk.Button` at least arrives as a
`ButtonControl`. The modern-looking toolkit is the less accessible one.

`ROLE_FOR_TK_CLASS` covers both families (`Button` and `TButton`, `Entry` and
`TEntry`, and so on), so `enable()` fixes ttk as well. But if you are choosing:
choose classic `tk`. Annotation raises ttk to the same tree that classic Tk
gives you, and no higher.

### The limitation: findable and readable is not activatable

This is the sharpest thing to know before adopting this, and it was measured
against a real click counter rather than reasoned about.

An annotated `tk.Button` advertises an `InvokePattern` and a
`LegacyIAccessible` `DefaultAction` of `"Press"`. **Both lie.** Calling
`InvokePattern.Invoke()` or `LegacyIAccessible.DoDefaultAction()` returns
cleanly, with no exception and no error code — and the Tk command behind the
button never runs. The generic MSAA proxy synthesises Invoke from a posted
`BM_CLICK`, and every Tk button is owner-drawn (`BS_OWNERDRAW`), so that message
goes into the void.

There is a spec for exactly this
(`test_an_annotated_button_still_cannot_be_pressed_through_its_invoke_pattern`),
which watches a counter inside the fixture app stay at `presses 0` across both
calls, then move to `presses 1` when the application presses its own button — so
the counter is demonstrably live and the silence belongs to the client. If a
future Tk or Windows makes Invoke start working, that spec goes red and tells us
this section needs rewriting. That is the point of having it.

**The consequence.** Annotation makes your widgets *findable and readable*: a
screen reader can announce them, a test can locate them, a client can read their
values. Assistive technology and test tools that want to *act* must click and
type — synthesised mouse and keyboard input aimed at `BoundingRectangle`, which
is always correct. Annotating does not perturb hit-testing: `ElementFromPoint`
at every widget's centre returns the same HWND before and after, in all eight
cases probed.

Note that synthesised input is subject to Windows' User Interface Privilege
Isolation, and reading is not. The half of this that works is the durable half.

### The app you cannot modify

Because annotation is in-process, a Tk application whose source you cannot touch
cannot be annotated. There is one narrow rescue:

```python
ctypes.windll.user32.SetWindowTextW(ctypes.c_void_p(hwnd), "New Task")
```

`SetWindowTextW` works **cross-process**, populates UIA `Name` on every Tk
widget, and survives `config(text=…)`, resize and iconify. It is names only: it
does not change ControlType, so a label stays an `ImageControl` and an entry
stays a pane with no ValuePattern.

Two warnings, and they are not decorative. **Never point this at a process that
annotates itself** — MSAA annotation overrides the window text, so at best it
does nothing, and mixing the two mechanisms across processes is how a working
app ends up worse than it started. And **it stops working at Tk 9.1**: once Tk
answers `WM_GETOBJECT` itself, the oleacc proxy that was reading the window text
is out of the picture entirely.

### Caveats worth knowing

- **A plain `config(text=…)` leaves the accessible name stale, indefinitely.**
  Measured: a label annotated as `'Task list'` that later does
  `label.config(text="in progress")` goes on being read as **`'Task list'`** —
  the widget's `-text` is only ever read at `<Map>`, and nothing re-reads it
  until an unmap/remap fires `<Map>` again. Staleness is the worst way an
  accessibility tree can be wrong, because a stale answer is indistinguishable
  from a true one. Two ways out, both verified: call
  **`add_acc_object(widget)`** after the `config` and the name is re-read
  immediately (`'in progress'`), or drive the widget from a `StringVar` and
  **`bind_text_variable`** it, which is the durable answer and needs saying
  once.
- **Disabled state is not conveyed, and nothing tracks any state.** Measured: a
  `tk.Button(state=DISABLED)` reads back `IsEnabled=True` — the widget is greyed
  on screen and advertised to a client as usable. `set_acc_state(widget, 0x1)`
  (`STATE_SYSTEM_UNAVAILABLE`) does fix it — verified, `IsEnabled` becomes
  `False` — but it is a write, not a subscription: nothing here notices a widget
  being disabled or re-enabled, so an application that says it has to keep
  saying it. A `bind_state_variable` sibling is on the [ROADMAP](ROADMAP.md).
  **Checked state is the exception, and it works:** an annotated `Checkbutton`
  is a `CheckBoxControl` whose `ToggleState` is correct *and follows its
  variable* with no call to this package at all (measured: `1`, then `0` after
  the application set the variable to 0). That comes from the MSAA proxy, not
  from here.
- **Notebook tabs are reachable; other compound-widget items are not.** A
  `Listbox` is annotated as a `LIST` and its *rows* are not in the tree at all;
  the same goes for `Treeview` items. Tk gives one HWND per widget and
  annotation works on HWNDs, so exposing those means MSAA's `IAccessible`
  child-id model — a different piece of machinery. On the
  [ROADMAP](ROADMAP.md); not here yet.

  **A `ttk.Notebook`'s tabs are the exception, since 0.4.0.** Each one is given
  a real child window of its own, positioned over the tab and annotated
  `PAGE_TAB`, so a client sees a `TabControl` with named `TabItemControl`s under
  it — and a click at a tab's centre selects it, because that window is
  `WS_EX_TRANSPARENT` and passes the click straight through to Tk. Without this
  a test could read whichever page was open and could never change which one
  that was. The window is owner-drawn by a parent that ignores the message, so
  it paints nothing and the strip looks exactly as it did.

  Tk fires `<<NotebookTabChanged>>` when the *selection* moves and at no other
  time, so a tab **added** beside the open one, or **renamed** in place, needs
  `add_acc_object(notebook)` — the same escape hatch a `config(text=...)` needs,
  for the same reason. Selecting a tab, and removing the open one, are noticed
  on their own.
- **A widget Tk never maps is never annotated.** An unshown notebook tab, a
  window built and withdrawn — `<Map>` never fires, so nothing happens until it
  does. This is inherent to the event, and shared with Tk 9.1's own
  implementation.
- **`enable()` is idempotent, and one call covers the whole application.** A
  second call reports what the first did and installs nothing further; the
  bindings go on the `all` bindtag, so every window the application opens is
  already covered.
- **A window cannot be annotated by hand.** `set_acc_name(root, …)` raises
  `AnnotationRefused`. `winfo_id()` on a toplevel answers with the container
  child Tk puts every widget under, so the name would land on an inner pane and
  leave the window itself unnamed — use `root.title(…)`, which is where a
  window's accessible name comes from anyway.
- **Toplevels are deliberately excluded.** `wm title` already gives a window a
  correct accessible `Name`, and overriding it breaks resolving a window by its
  title, which is where every other query starts.
- **AutomationIds are explicit-only.** `enable()` never assigns one.
  `set_automation_id` writes `GWLP_ID`, which is the control id Win32 puts in
  `WM_COMMAND.wParam` and `WM_DRAWITEM.idCtl` — and Tk's owner-draw path
  receives `WM_DRAWITEM`. A non-zero existing id is never overwritten; the call
  raises instead. Auto-assigning from a widget path would also make every
  repack a breaking change for whoever locates by it.
- **Windows recycles window handles.** A stale annotation on a recycled handle
  puts a dead widget's name on an unrelated control, and looks exactly like a
  flaky locator. `<Destroy>` clears through the handle cached at map time, since
  `winfo_id()` may already be raising by then.
- **Rewriting the same property is skipped.** `<Map>` fires on every unhide, tab
  change and geometry shuffle; without a ledger the cost of annotating a window
  would be paid again on every repaint, forever, for no change to what a client
  reads.

## What your own application tells Windows

Every caveat above is general. `describe(root)` is those caveats applied to
*your* window, naming the widgets by their Tk paths:

```python
tk_uia.enable(root)
...
print(tk_uia.describe(root))     # the report
tk_uia.describe(root).widgets    # the same thing, as data
```

It walks the live widget tree and reads tk-uia's own annotation ledger. It does
**not** touch UI Automation, does not import `uiautomation`, and reads nothing
back from Windows — runtime dependencies stay at zero, which is what lets you
leave this call in a production application.

Run `python probes/what_your_app_tells_windows.py` for the whole thing. Abridged
(a deliberately mixed window: classic `tk` and `ttk`, a canvas, a listbox, a
notebook, a frame that is never packed, a second toplevel):

```
tk-uia 0.3.0 -- what this application has told Windows it is showing
enable() reported ANNOTATED. 18 widgets under .: 12 written to, 6 not.

WIDGET              CLASS      ROLE                NAME         VALUE               ID
------------------  ---------  ------------------  -----------  ------------------  ----
.                   Tk         -                   -            -                   -
.!label             Label      STATIC_TEXT (41)    'Task list'  -                   -
.!button            Button     PUSH_BUTTON (43)    'New Task'   -                   4207
    also written: DESCRIPTION='creates a task and clears the form'
.!entry             Entry      TEXT (42)           -            -                   -
.!entry2            Entry      TEXT (42)           'Title'      'Write the report'  -
    kept in step with a variable: value
.!label2            Label      STATIC_TEXT (41)    'ready'      -                   -
    kept in step with a variable: name
.!canvas            Canvas     -                   -            -                   -
.!listbox           Listbox    LIST (33)           -            -                   -
...

WHAT A CLIENT WILL NOT GET, AND WHY

  NEVER_MAPPED  (3)
    nothing was written: Tk has never mapped it, so <Map> never fired. A
    withdrawn window, an unshown notebook tab, or a widget the geometry
    manager could not fit.
      .!notebook.!frame2  (TFrame)
      .!frame  (Frame)
      .!frame.!label  (Label)

  NAME_MAY_BE_STALE  (1)
    the name written here is not what the widget's -text says now. A plain
    config(text=...) does not re-announce; call add_acc_object(widget), or
    drive it from a variable and bind_text_variable it.
      .!label3  (Label)   -text now says 'in progress'

  NO_VALUE  (2)
    no accessible value. The role gives this widget a ValuePattern it did
    not have before, and it reads '' until something writes one -- a
    confident wrong answer where bare Tk gave none. bind_value_variable().
      .!entry  (Entry)
      .!combobox  (TCombobox)
...

LEFT ALONE ON PURPOSE

  NAMED_BY_ITS_TITLE  (2)
    a window, and `wm title` already gives it a correct accessible name.
    ...

Everything above is what tk-uia believes it wrote. It is not evidence that
a client can read it: IAccPropServices accepts a write to a window handle
nobody owns, answers S_OK, and changes nothing. Reading the same window
back from another process is the only thing that proves the bridge carried
it.
```

**`NEVER_MAPPED` is the line to read first, and it was the surprise.** That
window sets a fixed `geometry()`, and the Tk packer silently drops whatever it
cannot fit: `<Map>` never fires, so those widgets are invisible to accessibility
— with no exception, no warning and nothing in any log. Four widgets in the
probe are in that state. There is no other way to find out.

Each reason is one of the caveats above, and the catalogue is closed by that
rule: a `Gap` member has to correspond to a caveat this README already
documents. The member *names* (`NO_VALUE`, `NEVER_MAPPED`, …) are stable — they
are what the recipe below matches on.

**A report that showed only successes would be worse than none.** On a machine
where `enable()` returned `NATIVE` or `UNSUPPORTED`, nothing is annotated at
all, and a report of what went right would render as a blank page an author
could read as a clean bill of health. So the strategy is the first line, before
a single row, and every widget is listed as unwritten.

**Nothing here is verification, and the report says so itself.** It reports what
tk-uia *believes* it wrote. `IAccPropServices` accepts a write to a window handle
nobody owns, answers `S_OK`, and changes nothing — so "we wrote it" and "a client
can read it" are different claims, and only the first is in this report.
`check_screenreader()` answers a different question again ("is anything even
listening?") and is deliberately not folded in.

### Closing the gap: compare it with what a client sees

Run `tk_uia.describe(root)` inside your application and a client-side dump —
[pytest-uia](https://github.com/HuzPro/pytest-uia)'s, or your own `uiautomation`
walk — from outside it. Every widget the first says it named must appear in the
second with that name; every widget the first reports as unwritten must appear
anonymous. Anything that disagrees is a write that returned `S_OK` and went
nowhere.

The script that does the comparison spans two repositories, so it stays a recipe
rather than becoming a feature in either. The most valuable half of it is
guarded here:
`tests/test_gui_description.py::test_every_name_the_description_says_it_wrote_is_a_name_a_client_in_another_process_can_read`
reads the description out of a live fixture app and checks every name it claims
against the real UI Automation tree.

## The forward path: this library is deliberately temporary

**TIP 733 is Final, and lands in Tk 9.1.** `win/tkWinAccessibility.c` is merged;
it is MSAA-based, uses the same role mapping this package does (Label →
StaticText), and auto-registers widgets on `<Map>` exactly as `enable()` does.
When you have Tk 9.1, you should be using Tk's own.

The runway is long, which is why this exists:

| | |
|---|---|
| Tk 9.1 | beta today; stable expected around **September 2026** |
| CPython 3.13 / 3.14 | bundle **Tk 8.6.15** — none of it |
| CPython 3.15 | bundles **Tk 9.0.4** — still none of it |
| Earliest bundled accessible Tk | realistically **CPython 3.16** |

`enable()` already gates on this. It asks the interpreter for `info patchlevel`
(by digit runs, so the `9.1b1` betas parse), and for Tk ≥ 9.1 it confirms the
`tk accessible` ensemble really exists — by handing `tk` a subcommand it cannot
have and reading the list of subcommands it complains back with, so that no
native accessibility command is ever *run*. Then it returns `NATIVE` and binds
nothing. A build with the feature compiled out still gets annotated, because
guessing `NATIVE` there would leave it mute.

The public surface deliberately mirrors TIP 733's vocabulary — `add_acc_object`,
`set_acc_role`, `set_acc_name`, `set_acc_value`, `set_acc_description`,
`set_acc_action`, `set_acc_help`, `set_acc_state`, `check_screenreader` — so
that migrating to Tk 9.1 is close to a rename. Wiring the native path (rather
than deferring to it) is a roadmap item, blocked on Tk 9.1 being installable.

## Prior art, honestly

Nothing else does this on Windows.

- **pywinauto issue #84**, "support for Tkinter applications", has been open
  since **2015**.
- **`tka11y`** (2009) is Linux/ATK-only, and dead.
- **`tkaria11y`** (2025) drives text-to-speech directly from a Tk app. It never
  touches the accessibility tree, so a screen reader still announces nothing and
  no UIA client can see anything. Different problem, opposite direction.

That is the extent of the claim. This is a small library filling a gap that Tk
itself closes in 9.1.

## Measured

Windows 11, Python 3.13.1, **Tk 8.6.15**, read from a separate process through
`uiautomation`. Everything below either comes from a spec in `tests/` or is
reproducible by running `probes/what_enable_alone_gives_you.py`.

| | |
|---|---|
| Widget types probed bare | 30 — `Name` and `AutomationId` empty on **all** of them |
| ttk widget types probed | 15 — **all** anonymous `PaneControl`; `ttk.Button` has no InvokePattern |
| Annotation calls, all returning `S_OK` and all reading back cross-process | 11 |
| `FrameworkId` of an annotated Tk window | `'Win32'` |
| `ProviderDescription` | `Main:Nested [… Annotation(parent link):Microsoft: Annotation Proxy …; Main:Microsoft: MSAA Proxy …]` |
| `set_automation_id(w, 4207)` read back cross-process | `AutomationId == '4207'` |
| `InvokePattern.Invoke()` on an annotated Tk button | returns cleanly; press counter unchanged |
| `LegacyIAccessible.DoDefaultAction()` | returns cleanly; press counter unchanged |
| Hit-testing after annotation | `ElementFromPoint` identical before and after, 8/8 widgets |
| `tk.Entry` showing `buy milk`, after `enable()` alone | `EditControl`, `Name=''`, ValuePattern **`''`** |
| Accessible name after `label.config(text="in progress")` | unchanged — still `'Task list'` |
| …and after `add_acc_object(label)` | `'in progress'` |
| `tk.Button(state=DISABLED)` after `enable()` | `IsEnabled` **`True`** — the greyed button reads as usable |
| …and after `set_acc_state(button, 0x1)` | `IsEnabled` `False` |
| Annotated `Checkbutton` `ToggleState` | `1`, then `0` when the application set its variable to 0 — correct, and live, with no call to this package |
| Write trace left on a `StringVar` after its bound widget is destroyed | **0** (`trace_info()` read inside the app) |
| `enable()` runtime dependencies | **0**, permanently |
| gui suite (12 specs, a real window each) | ~10 s |

The `ProviderDescription` line is the useful one for anybody writing a UIA
client: a Tk window is served by the MSAA proxy but reports `FrameworkId`
`'Win32'`, where WinForms — also served by the MSAA proxy, also owner-drawn —
reports `'WinForm'`. That pair is how a test tool can tell a provider whose
`Invoke` works from one whose `Invoke` lies.

## Not yet verified: a real screen reader

Everything above is read back through UI Automation. That is the API a screen
reader consumes, which makes it the right boundary to have reached first — but
**"NVDA can read this tree" and "NVDA says the right thing at the right moment"
are different claims, and only the first is evidenced here.** Nothing in this
repository has been heard out loud.

**`describe(root)` does not move a single checkbox in this list, and it is worth
being clear why.** It reports what this library *believes* it wrote, which is
strictly *less* verified than the cross-process readback the gui specs already
do. Comparing that belief against what a client sees is a real and useful
mechanism — it is what exposes an annotation that returned `S_OK` and went
nowhere — but it is a different and lesser thing than hearing a screen reader
say the right words at the right moment. Two gaps, both still open.

The gap matters because the failures it would catch are ones a tree assertion
cannot see: a name that is correct but announced at the wrong moment, a role
that reads correctly to a client and awkwardly to a listener, a control that is
announced twice, or focus that never moves at all. Closing it is the top item on
the [ROADMAP](ROADMAP.md), and this is what it involves:

- [ ] Install **NVDA** and a way to capture what it says — its own `nvda_speech`
      debug log, or the **NVDA Remote** add-on for reading speech off-machine.
- [ ] Confirm `check_screenreader()` reports `True` while NVDA is running, which
      is currently the one part of this library that talks about screen readers
      and has never met one.
- [ ] **Focus announcement:** tab to an annotated `tk.Button` and assert the
      speech contains its name *and* the word "button" — the role reaching a
      listener, not just a client.
- [ ] **Entry announcement:** tab to an annotated `tk.Entry` and assert both its
      name and its current value are spoken. This is the case most likely to
      disappoint: a value written through `PROPID_ACC_VALUE` reads correctly to
      UIA, and whether NVDA announces it on focus is a separate question.
- [ ] **Live updates:** change a bound `StringVar` and assert the new text is
      announced without re-focusing, which is what `bind_text_variable` and
      `bind_value_variable` exist to make possible.
- [ ] **Nothing announced twice.** Annotation overlays properties on a window
      that oleacc is already proxying; a duplicate announcement would be
      invisible to every assertion in this repo.
- [ ] **The control group:** run the same pass against a *bare* Tk window and
      capture what NVDA says without this library, so the before/after is
      evidence rather than assertion.
- [ ] **A second screen reader.** TIP 733 notes NVDA works best on Windows
      because it is MSAA-based, and that Narrator does not do as well. Since this
      library uses the same MSAA route, that caveat probably applies here too —
      worth confirming rather than repeating.
- [ ] Decide what, if any, of this can be automated. Screen-reader speech is
      timing-dependent and hard to assert on deterministically, so this may
      honestly belong as a recorded manual pass in the README rather than as CI.

Until those are ticked, the honest claim this project makes is the narrow one:
**the accessibility tree tells the truth.** Whether a blind user has a good time
is a claim it has not yet earned.

## Development

```powershell
git clone https://github.com/HuzPro/tk-uia
cd tk-uia
py -m venv .venv
.\.venv\Scripts\Activate.ps1
uv pip install -e ".[dev]"        # or: pip install -e ".[dev]"

pytest -m "not gui" -q            # instant; no windows, runs on any platform
pytest -m gui -q                  # launches a real Tk window, twelve times
pytest -q                         # everything

ruff check src tests probes
ruff format --check src tests probes
```

The unit suite runs against a `RecordingStore` and a `FakeWidget` — **no Tk, no
display, no Windows** — which is what lets it be the same suite on every
platform. The gui suite is the counterweight: `_accprop.py` is almost untested
by design, because a recording double would agree with a COM call that returned
`S_OK` and changed nothing, and that is the exact failure this package exists to
refuse. Its correctness comes from `tests/test_gui_annotations.py`, which
launches `tests/fixture_apps/annotated_app.py` into a process of its own and
reads it back with `uiautomation`. The one decision in it that *is* unit-tested
is what an application is told when a COM call refuses — which of the eleven
identical-looking annotation calls it was has to survive into the message, and
that is specifiable with no desktop and no live `oleacc`.

To run the platform-independence lane locally the way CI does — on a Python with
no `tkinter`, no `ctypes.windll` and no `uiautomation`:

```bash
wsl -- bash -lc 'cd /mnt/c/…/tk-uia && python3 -m venv .venv-linux \
  && ./.venv-linux/bin/pip install -e ".[dev]" && ./.venv-linux/bin/pytest -q'
```

On a distro whose `python3` ships without `ensurepip` there is nothing to
install: pytest is pure Python, so the Windows virtual environment's copy runs
there unchanged.

```bash
wsl -- bash -lc 'cd /mnt/c/…/tk-uia \
  && PYTHONPATH=src:.venv/Lib/site-packages python3 -m pytest -q'
```

Either way the twelve gui specs are not collected at all — `collect_ignore_glob`
in `tests/conftest.py` drops `test_gui_*.py` off Windows, because a `skipif`
marks a test but cannot stop pytest importing the module carrying it. The one
Windows-only unit spec (`tests/test_com_diagnostics.py`, which asks what an
application is told when a COM call refuses) skips there instead, since it needs
`ctypes.WINFUNCTYPE` but no desktop.

CI runs `ruff` on Ubuntu and `pytest -m "not gui"` on
{Ubuntu, Windows} × {3.10, 3.13}. The **Ubuntu lane is the meaningful one**: it
is what proves this package imports and runs where there is no Tk and no
Windows, which matters because it is installed at runtime inside somebody else's
application. The gui suite is local-only — it needs an interactive desktop.

### Probes

`probes/` holds the scripts behind the numbers in this README, so that a reader
who doubts one can re-run it rather than take it on trust. They are not tests
and CI does not run them; they print measurements.

```powershell
python probes/what_enable_alone_gives_you.py
python probes/what_your_app_tells_windows.py
```

The first launches a window that calls `enable(root)` and deliberately says
nothing else, then reads it back from this process — which is where the empty
ValuePattern, the stale name after `config(text=…)`, the disabled button that
reads as enabled, and the checkbox state that is right all along come from.

The second builds the deliberately mixed window quoted under *What your own
application tells Windows* and prints its description, so that every line of
that report can be re-run rather than taken on trust. It reads nothing back and
needs no client; it is the one probe that costs nothing but a window.

### Layout

```
src/tk_uia/
├── __init__.py     # the public surface; imports neither tkinter nor ctypes.windll
├── roles.py        # MSAA role numbers, and ROLE_FOR_TK_CLASS
├── annotate.py     # all the behaviour, over AccessibilityStore/TkWidget Protocols
├── describe.py     # what was written, what was not, and why — over the same Protocols
├── tkversion.py    # the Tk 9.1 capability gate
└── _accprop.py     # the ctypes/COM humble object — the only Windows in here
probes/            # the scripts behind the measurements above; not tests
```

Everything above `_accprop.py` talks to Protocols, which is why the whole unit
suite runs anywhere, and why the one module that cannot be unit-tested is also
the one module with no decisions in it.

## License

[MIT](LICENSE)
