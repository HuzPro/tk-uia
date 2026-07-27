# Changelog

## 0.6.0 — 2026-07-27

The cost of making a Tk application accessible just dropped. A widget that told
Tk which variable it shows is now followed with no call at all; the caption an
entry has always had on screen and never in the tree can be said in one call, or
inferred for a whole window at once; and `describe()` catches the fault no
single widget can show — two controls a client has no way to choose between. A
form that used to want a `set_acc_name` per entry and a `bind_text_variable` per
status line wants `enable(root)` and one line per unlabelled row.
`COOKBOOK.md` is new and is the ten-minute version of all of it.

- **`describe()` reports a progressbar's missing value.** Measured three ways
  from another process: an annotated `ProgressBarControl` answers `''` with
  nothing written, and still `''` after the widget's own `-value` moved from 10
  to 90 — the proxy never serves the number the bar is showing, and only
  `set_acc_value` reads back. A bar visibly at 40 percent tells a client
  nothing, which is the entry's failure mode exactly, so `PROGRESS_BAR` now
  takes the entry's `NO_VALUE` gap. The spinbox gained the same in this release
  by the same rule.

- **A declared `-textvariable` is followed automatically.** A widget built as
  `tk.Label(textvariable=status)` or `tk.Entry(textvariable=draft)` already
  named the variable driving it, and `cget("textvariable")` hands that name
  back — so asking the application to repeat itself through
  `bind_text_variable` was asking for something Tk could answer. `enable()`
  reads it at `<Map>` and keeps the annotation in step from then on. The
  **role** decides which property that is: in an `Entry`, a `Combobox` or a
  `Spinbox` — the three roles the MSAA bridge hands a ValuePattern to, measured
  in [COVERAGE.md](COVERAGE.md) — the variable is the **value**; in the eleven
  other classes carrying the option the widget shows the variable *instead of* a
  caption, so it is the **name**. Sixteen classes across both toolkits have it;
  `tk.Text` has none, and a `Listbox`'s `-listvariable` and a `Scale`'s
  `-variable` are deliberately not this — the rows of one are not in the tree
  and the other's role offers no pattern to write to. Measured, from another
  process: an entry driven by a variable now reads back its contents after
  `enable()` **alone**, where `probes/what_enable_alone_gives_you.py` used to
  measure `''`.

- **This closes the staleness hole for every widget driven by a variable.** A
  `textvariable` label was the worst case in the package: Tk keeps a classic
  label's `-text` in step with its variable, so the name was read once at
  `<Map>` and then quietly disagreed with the screen on every write — and
  `describe()` could only report `NAME_MAY_BE_STALE` and tell the author to go
  and bind it. It now reports the same widget as *kept in step*, which is what
  it is.

- **Your word wins, and it wins permanently.** `set_acc_name`, `set_acc_value`,
  `bind_text_variable` and `bind_value_variable` each **release** the automatic
  binding for that property rather than outranking it. Left in place, the next
  write to the application's own variable would take back the name it had just
  chosen, from inside a Tcl callback with no call of the application's anywhere
  in the traceback. Re-pointing a widget at another variable is followed too —
  `config(textvariable=other)` then `add_acc_object(widget)` — and the old
  binding is let go of, because two traces on one property do not compose: they
  take turns, and the widget would read as whichever variable was written last.
  Following is idempotent, so the `<Map>` that fires on every unhide, tab change
  and geometry shuffle costs no second trace, and `forget()` releases the
  automatic binding exactly as it releases a manual one.

- **Nothing here builds a `tkinter.Variable`, and that is the whole of the
  implementation risk.** The obvious way to reach an application's variable by
  name is `StringVar(master, name=...)`, and it destroys the application's data:
  `Variable.__del__` *unsets* the Tcl variable it names, so the wrapper takes
  the real variable with it when it is collected. Measured — the application's
  variable is unreadable afterwards, with no exception and nothing in any log,
  and removing the trace first makes no difference. The binding is made with raw
  `trace add variable` calls through a humble object (`_tkvars.py`) instead, and
  the trace command is registered against the toplevel rather than the widget,
  so that a widget destroyed by a route that skipped `forget()` meets the
  existing liveness guard instead of a `TclError` per write. Runtime
  dependencies stay at zero, and `annotate.py` still imports nothing
  platform-specific: the domain asks a seam for "the variable called this", and
  the whole of the decision is specified on a machine with no Tk.

- **New: `label_for(label, widget)`, the caption Tk records nowhere.** An entry
  has no words of its own and in Tk the label that names it is a *sibling* —
  nothing in the toolkit records which widget a caption speaks for, so no
  library can read the relationship back and every entry in a form cost a
  `set_acc_name` of its own. Measured on a real six-tab settings dialog: 15 of
  its 110 controls were nameless entries, every one of them captioned by the
  label beside it. One call now says it, the way Qt's `QLabel.setBuddy` and
  HTML's `<label for=...>` do. The trailing colon comes off — every caption in
  that dialog ends with one and none of them is part of a control's name — and
  where the label declares a `-textvariable`, the widget's name **follows** it
  through the same machinery `enable()` already uses, rather than copying a
  string across once. A label showing nothing at all raises `AnnotationRefused`
  rather than quietly naming the widget `''`, which is the confident wrong
  answer this package exists to refuse. The name counts as the application's
  own: it survives the `<Map>` that fires on every unhide and tab change, and it
  releases any variable this package had been following into that widget's name.

- **New: `infer_names_from_layout(root)`, the retrofit — and deliberately not
  part of `enable()`.** It walks the tree and applies the convention a form is
  already following: a **row** is a frame, or a window, since a status bar is
  packed straight onto a toplevel and a walk that visited only frames missed
  exactly the control that reports what went wrong; the row's **subject** is the
  first label in it that is not driven by a variable, or failing that the button
  that captions it; every **entry** in the row takes that subject as its name,
  through the same association `label_for` records; and every **button** whose
  caption says nothing on its own — `Browse...`, `Reset to Default`, `?` — is
  qualified with it, as `Browse... for GUI Executable`, because two identical
  captions in one window are indistinguishable to a screen reader user and to a
  locator alike. Measured: applying this took that dialog from 83 of 110
  controls addressable to **110 of 110**. The variable rule is a measurement
  too — a subject taken from a variable-driven label produced a button announced
  as `Reset to Default for C:\Example\stopped.ico`. It is a separate call
  because everything else this package writes is read off the widget being
  annotated, and this is read off the widgets *around* it: a layout is not a
  statement, so inferring from one is a guess. The library never guesses on its
  own; asked for by name, it is a convention the author has recognised in their
  own window. It returns what it named, widget by widget, read back out of what
  was really written rather than out of what it meant to write — so on a Tk
  where `enable()` stood down it reports naming nothing, which is the truth.

- **What the convention writes is your word, not a guess it can lose.** The
  obvious implementation writes these names as *inferred*, ranked below anything
  an application said. Measured, that is unusable: `<Map>` re-runs the automatic
  annotation, which names a widget from its own `-text`, so a button qualified
  `Browse... for GUI Executable` was back to `Browse...` after the first tab
  change — silently, on an event the application never sees, in exactly the
  dialog this feature was measured on. The convention was asked for, so what it
  writes is the application's own word; `set_acc_name` still wins either way,
  before the call by being left alone and after it by replacing what was
  written.

- **New: `describe()` names the widgets a client cannot tell apart.** Gap
  `NAME_NOT_UNIQUE`. Measured on that same dialog: four buttons — two
  `Browse...`, two `Reset to Default` — every one of them correctly typed,
  correctly named, and correctly named *the same thing*. Nothing about any one
  of them is wrong, which is exactly why no per-widget check could ever have
  seen it and why this is the one reason computed after the whole walk: a client
  asking for "the Browse... button" reaches one of them at random, and a
  screen-reader user hears the same announcement for controls that do different
  things. It is counted **per toplevel window**, because that is how a client
  resolves one — it finds the window by its title and searches inside it — so a
  dialog's `Confirm` and the main window's `Confirm` are two answers to two
  different questions and not a collision. A widget's window is read out of the
  walk itself, from the Tk paths, on segment boundaries: `.!toplevel22` merely
  reads like `.!toplevel2` and is not inside it. And it is **added** to whatever
  else a widget is missing rather than replacing it, unlike
  `UNMAPPED_SINCE_ANNOTATED`: two buttons that cannot be told apart are still
  two buttons that cannot be pressed. The reason it points at is the one the
  layout convention already applies — qualify the caption, or
  `infer_names_from_layout(root)`. There is no gui spec: this is reasoning over
  a walk that is already gui-proven, and it is specified end to end on a machine
  with no Tk.

- **Fixed: `describe()` understated a spinbox.** `SPIN_BUTTON` was missing from
  the roles a missing accessible value is reported for, so an annotated
  `tk.Spinbox` or `ttk.Spinbox` that nobody had written a value to escaped
  `NO_VALUE` entirely — while reaching a client as a `SpinnerControl` carrying a
  ValuePattern, which [COVERAGE.md](COVERAGE.md) has measured from another
  process all along. That set is now read off its `patterns` column rather than
  recalled: `Value` is measured on six widget classes across the two toolkits
  and three roles cover them. A `ttk.Progressbar` is the one other cell carrying
  it and is deliberately still not reported, since nothing has yet read back
  what a `ProgressBarControl` answers with when no value was written, and a
  diagnostic that guesses is the thing this package exists to refuse.

- **New: [COOKBOOK.md](COOKBOOK.md) — one form, and the calls that make it
  announce itself.** The README is the reference and reads like one; somebody
  deciding whether to adopt this has ten minutes, and the three changes above
  are what made a short page possible to write honestly. It builds a small
  complete form the way a Tkinter programmer builds one, then shows both routes
  to naming it — a `label_for` per unlabelled row, or
  `infer_names_from_layout(root)` for a form that already exists — and says
  which fits when. Every line of output in it was **run rather than written**,
  which is what makes the middle of it worth reading: `describe()` on that
  window reports `NAME_NOT_UNIQUE` against the two identically captioned
  `Browse...` buttons the per-row route leaves behind, and the retrofit route's
  report has that heading gone and is otherwise unchanged. The gotcha it
  documents was measured the same way — `describe(root)` called between building
  the window and `mainloop()` reports nine of the form's twelve widgets as
  `NEVER_MAPPED`, because `<Map>` is the event that annotates and it has not
  happened yet.

- **Packaged to release-readiness, and deliberately not published.** The sdist
  and the wheel build clean from `pyproject.toml`; the wheel carries `py.typed`,
  the package and nothing else — no `tests/`, no `probes/` — and installs into a
  virtual environment that has never seen this repository with **zero
  dependencies**, where `enable()` on a withdrawn root reports `ANNOTATED`. That
  last assertion is the one worth having: an install that imports cleanly and
  annotates nothing would pass any weaker check. [RELEASING.md](RELEASING.md) is
  new and writes down the rest, including the two steps nobody but the
  maintainer can take — the PyPI API token, and the first upload, which is what
  *claims* the name rather than merely using it. The README still tells you to
  clone and `pip install -e .`, because until that upload happens that is the
  true instruction and a README claiming an install command that does not work
  is worse than one that undersells.

- **The README's `describe()` sample was three versions stale, and a count
  beside it was wrong.** It was pasted from 0.3.0 and predated the canvas
  getting a role, a notebook's tabs becoming reachable, and two new gaps, so it
  showed a window that no longer exists. It is re-run and re-pasted from
  `probes/what_your_app_tells_windows.py`. The count is the more embarrassing
  half: the prose said four widgets in that probe were never mapped and blamed
  the window's fixed `geometry()`, and the report printed beneath it said three
  — a frame nobody packed, its child, and the notebook tab nobody opened, none
  of which the packer dropped. The packer warning is true and is still there,
  as the thing to fear rather than as what happened here.

## 0.5.0 — 2026-07-27

Every widget class both toolkits ship now has a role, and two bugs that quietly
threw annotations away are fixed. `COVERAGE.md` is new and measures the whole of
it: it is regenerated by `probes/coverage_matrix.py`, not written by hand.

- **Eight widget classes gained a role**, and the numbers were measured rather
  than chosen: `Canvas` → `GRAPHIC` (reads back as `ImageControl`), `Menubutton`
  and `TMenubutton` → `SPLITBUTTON` (`SplitButtonControl`), `Panedwindow` and
  `TPanedwindow` → `GROUPING`, `TSeparator` → `SEPARATOR`, `TSizegrip` → `GRIP`
  (`ThumbControl`), `Menu` → `MENUPOPUP`. Three plausible alternatives —
  `DIAGRAM`, `CLIENT` and `PANE` — were tried for the canvas and every one was
  accepted with `S_OK` and left the widget the anonymous `PaneControl` it
  already was. That is exactly the silent no-op this package exists to refuse,
  so the numbers are pinned by gui specs that read them back from another
  process, not by unit specs that would only prove the table says what it says.
  Measured along the way: **the role alone decides the control type** — a
  `tk.Frame` carrying `GRAPHIC` is an `ImageControl` too.

- **A `Menu` has a role it can never be given, and that is the point.** Menus
  are posted rather than mapped, so nothing is ever written to one. Without the
  entry `describe()` blamed the missing role, which reads as "add one and this
  will work"; with it the report says `NEVER_MAPPED`, which is true and is not
  fixable.

- **A `tk.Scale` is named from its `-label`.** It is the one widget in either
  toolkit with no `-text` option at all, so an inference that read only `-text`
  left the one widget built differently as the one widget announced as an
  unnamed slider.

- **Fixed: an inferred name or role silently overwrote one the application
  chose.** `Button(text="OK")` announced as `"Confirm order"` reverted to `"OK"`
  the next time Tk mapped it — a notebook tab reopened, a `pack_forget` undone —
  because `<Map>` re-runs the automatic annotation. The application never sees
  that event, so the name it deliberately set came back wrong with nothing
  raised anywhere. An inferred value now never overwrites one that was said.
  Found by a fixture that annotated two Menubuttons and got its captions back.

- **Fixed: `describe()` reported a widget as written after Tk had unmapped it.**
  New gap `UNMAPPED_SINCE_ANNOTATED`. Measured against a real tabbed dialog: one
  tab change left 23 widgets holding the same window handles and every
  annotation intact, and a client could read none of them — UI Automation does
  not list an unmapped window. The report called all 23 written. It is reported
  instead of the per-property reasons, because "no accessible name" is not what
  an author needs to hear about a widget nothing can currently see.

- **`COVERAGE.md`, and the probes behind it.** `probes/every_classic_tk_widget.py`
  and `probes/every_ttk_widget.py` hold one of every widget class each;
  `probes/coverage_matrix.py` reads both windows three times — bare, after
  `enable()`, and after the naming a well-behaved application adds — and joins
  the views **by rectangle**, because a widget with no role has no name to join
  on and those are the rows worth having. Bare ttk gives a usable control type
  to 0 of 20 widgets; after `enable()` and the application's own names, 20 of 20
  are typed, named and queryable, and classic tk reaches 17 of 18. The holdout
  is a `Toplevel`, which `wm title` already names correctly.

## 0.4.0 — 2026-07-27

A notebook's tabs are now controls a client can see, name and press. Until now
`enable()` gave you a `TabControl` with nothing inside it: a test could read
whichever page happened to be open and had no way at all to change which one
that was, which for a tabbed settings dialog is most of the window.

- **Every `ttk.Notebook` tab is given a window handle of its own.** Tk paints
  the whole tab strip inside the notebook's own window, so there is no handle
  for `SetHwndProp` to annotate — which is why the ROADMAP's answer to this was
  MSAA's child-id model, meaning an `IAccessible` COM server answering
  `WM_GETOBJECT`. Measured, there is a smaller answer: a real child window over
  each tab *is* a handle, so the machinery already here annotates it. Each is
  created `WS_EX_TRANSPARENT` and `SS_OWNERDRAW` with a parent that ignores
  `WM_DRAWITEM`, so it paints nothing, the strip looks unchanged, and a click at
  a tab's centre passes straight through to Tk and selects that tab. Runtime
  dependencies stay at zero; the whole addition is four Win32 calls behind a
  seam.

- **Two measurements shaped the scan, and both would have been wrong to guess.**
  ttk draws the *selected* tab standing two pixels proud at the top **and**
  bottom, so the first row of the strip that answers belongs to that tab alone —
  a scan across it finds one tab and reports the notebook done. The scan crosses
  the strip's middle instead, and gives every tab the extent they cover between
  them rather than its own, so that picking a different tab does not move every
  rectangle on the strip. Tk also lays a strip out on idle, so a tab added a
  moment ago is not yet where it will be; the scan lets the layout settle before
  it measures anything.

- **What announces itself, and what an application has to say.** Tk fires
  `<<NotebookTabChanged>>` for a change of *selection* and nothing else —
  measured, adding a tab fires no event of any kind. Selecting a tab and
  removing the open one are therefore noticed on their own; a tab **added**
  beside the open one, or **renamed** in place, needs `add_acc_object(notebook)`,
  which now refreshes a notebook's tabs as well as re-reading its `-text`. This
  is the same contract a `config(text=...)` has always had.

- **`describe(root)` stops calling a notebook hollow when it is not.**
  `ITEMS_NOT_IN_THE_TREE` is no longer reported for a notebook whose tabs were
  found and given handles; the row lists them instead. It is still reported for
  a `Listbox`, a `Treeview`, and for a notebook whose strip nothing could be
  found on — which is what a notebook Tk has not laid out yet looks like.

- **The bound of the idea, stated because it is the obvious next question.**
  This does not generalise to `Listbox` rows or `Treeview` items. Those scroll,
  there can be thousands, and a window per row would be absurd where a window
  per tab is four. They still want the server, and are still on the ROADMAP.

## 0.3.0 — 2026-07-26

One new call, and it answers a question the library previously left an
application with no way to ask.

- **`describe(root)` says what this application has told Windows, and names
  every widget it did not.** Until now `enable()` returned a strategy and
  nothing else: an author who wanted to know whether their listbox had been
  annotated, or why their entry was going to read back `''`, had no way to find
  out from inside their own process. `describe(root)` returns a frozen
  `Description` — `print()` it for a report, read `.widgets` for the same thing
  as data — with a row per widget carrying the role, name, value, automation id
  and everything else that was written, and, for every widget it did **not**
  write or wrote incompletely, a named and enumerated reason. It walks the live
  widget tree and reads tk-uia's own annotation ledger. It touches neither UI
  Automation nor COM, imports neither `tkinter` nor `ctypes`, and runtime
  dependencies stay at zero — measured, the whole report renders on a Linux
  CPython with no `tkinter` and with `windll`, `oledll`, `WinDLL`, `OleDLL`,
  `WINFUNCTYPE` and `HRESULT` deleted from `ctypes`.

- **The reason a widget carries nothing is the product, not the table.** The
  ledger supplies four columns; the live walk supplies the diagnosis. The
  highest-value one was a surprise: a window with a fixed `geometry()` leaves
  the Tk packer silently dropping whatever it cannot fit, so `<Map>` never fires
  and those widgets are invisible to accessibility with no exception, no warning
  and nothing in any log. In `probes/what_your_app_tells_windows.py` four
  widgets are in that state — an unshown notebook tab, a frame that was never
  packed and its child, and there is no other way to discover it. The ten
  reasons are a closed catalogue by rule: a `Gap` member has to correspond to a
  caveat the README already documents, which is what stops the taxonomy
  sprawling into a second, worse README.

- **A report that showed only successes would be worse than no report.** Where
  `enable()` reported `NATIVE` or `UNSUPPORTED` nothing in the window was
  annotated at all, and a report of what went right would render that as a blank
  page an author could read as a clean bill of health. So the strategy is the
  first line, ahead of a single row, and every widget is listed as unwritten.
  Same rule for the widgets: one that was never touched is named with the reason
  rather than left out, and a ledger entry the walk never reached is named too.

- **Nothing in it is presented as verification, and there is a spec that fails
  if that ever changes.** `IAccPropServices` accepts a write to a window handle
  nobody owns, answers `S_OK` and changes nothing, so "tk-uia wrote it" and "a
  client can read it" are different claims. The report closes by saying so, in
  as many words, and `set_automation_id`'s number is reported as what was asked
  for rather than read back out of `GWLP_ID` — reading it back would have
  dragged the COM store into a module that has no business importing `ctypes`.
  The comparison that *does* close the gap spans two repositories and stays a
  recipe; the half of it that fits here is a gui spec that reads the description
  out of a live fixture app and checks every name it claims against the real UI
  Automation tree. Measured against a deliberate fault — annotations written one
  past the right window handle, which is what a cross-process write looks like —
  it names all eight claimed names as unreadable.

- **The annotation ledger now records where each property came from, which is
  what makes the staleness check usable.** Without it, `NAME_MAY_BE_STALE` fires
  on a pattern the README encourages: `Button(text="OK")` named `"Confirm
  order"` leaves the ledger and the widget's `-text` legitimately disagreeing.
  A property is now recorded as inferred from the widget, said once by the
  application, or kept in step by a variable, and only the first can go stale.
  The one behavioural change this needed is in the annotator's hot path and was
  made carefully: `_write`'s early return became a guard around the COM write
  **only**, so the redundant write on every `<Map>` is still skipped — that is
  the ledger's whole job — while the recorded source stays current for a binding
  whose first announcement happens to match what was already there. The cost is
  one dict assignment per `<Map>`, against three Tcl round-trips already being
  paid on the same path.

- **Internals: two Extract Class refactors, both to seams that already existed
  as fields.** `Ledger` was three raw dicts on the annotator, and `describe` now
  depends on its interface rather than on the annotator's privates. `OwningThread`
  was the thread guard, and `describe` needs the same rule for a different
  reason — it makes six kinds of trip into the Tcl interpreter per widget, and
  doing that from a foreign thread corrupts it quietly — but could not inherit
  it from the annotator, because on an unsupported Tk the annotator is an
  `InertAnnotator` whose entire job is to refuse nothing. `enable(root,
  roles=...)`'s merged table is now read by the report as well, so a caller who
  has already added a role for their canvas is never told to go and add one.

## 0.2.1 — 2026-07-26

Bug fixes and documentation. No new API.

- **A bound variable no longer keeps firing at a widget that has gone.**
  `bind_text_variable` and `bind_value_variable` registered a Tcl `write` trace
  and nothing ever removed it — and a trace lives on the *variable*, which
  routinely outlives every widget that displayed it. Reproduced against 0.2.0 in
  a real Tk: destroy a bound label, write the variable, and Tcl raises
  `TclError: bad window path name ".!label"` inside its own callback, where the
  application has no call of its own to wrap it in. It lands as an unhandled
  traceback on stderr, on every write, for the life of the process. The quieter
  half was worse: because the trace also survived `forget()`, the next write
  silently put the annotation back on a widget the caller had just taken away —
  in 0.2.0, `forget()` released **none** of the traces registered on a variable.
  `trace_add`'s return is now kept per widget and handed back to `trace_remove`
  in `forget()`, which is where `<Destroy>` already routes. A liveness check
  inside the announce closure (`winfo_exists`, which answers `0` rather than
  raising for a path Tk no longer has) is the second line, for a widget that
  dies by a route which never reaches `forget` — but removal is the fix, since a
  guard alone would leave the registration on the variable forever. Three
  specs, one of them a gui spec that reads the application's own
  `trace_info()` count out of the window through UI Automation and watches it go
  from `1` to `0`.

- **`enable()` is idempotent.** A second call used to stack a second pair of
  `<Map>`/`<Destroy>` bindings over the first (`[<Map>+, <Destroy>+, <Map>+,
  <Destroy>+]`), leaving a stale annotator auto-annotating widgets that
  `forget()` — which reached only the newest — could no longer take back, and
  leaking one never-released `IAccPropServices` per call. It now reports what
  the first call did and installs nothing further. That is not a compromise:
  the bindings go on the `all` bindtag, so one installation already covers every
  window the application will open.

- **The thread guard fires before Tk is touched, not after.** `add()` asked the
  widget for `winfo_class()`, `keys()` and `cget()` — three trips into the Tcl
  interpreter — and only then let `_write` refuse a caller from the wrong
  thread. So the spec that claimed to prove the store was protected was passing
  while Tk had already been poked from the wrong thread, which is the half that
  corrupts rather than merely misplaces. The refusal moved to the top of `add`,
  and the widget double now refuses a foreign caller itself, so the spec fails
  if anything reaches Tk first. It is deliberately stricter than Tk, which
  mostly answers and corrupts quietly instead.

- **A failing COM call says which call failed.** Every prototype declared
  `ctypes.HRESULT` as its `restype`, which looks like the honest choice and is
  the wrong one: ctypes raises an `OSError` of its own on any negative HRESULT
  *before* the caller sees the value, so `_checked` never ran and the carefully
  built `SetHwndPropStr(NAME)` context was unreachable code. Measured, the
  message an application got was a bare `[WinError -2147024891] Access is
  denied` with no way to tell which of eleven identical-looking annotation calls
  refused. Read as a plain `c_long` the code reaches `_checked`, which now
  reports `SetHwndPropStr(NAME) failed 0x80070005` — and also catches the
  positive non-`S_OK` answers that `ctypes.HRESULT` waves through as success.

- **Naming a window by hand is refused.** The rule that toplevels are left to
  `wm title` guarded only the automatic path; `set_acc_name(root, …)` walked
  straight past it. `winfo_id()` on a toplevel answers with the container child
  Tk puts every widget under, so the name landed on an inner pane while the
  window itself stayed unnamed — a confident wrong answer, and the failure mode
  this package exists to refuse. It now raises `AnnotationRefused` and says
  where a window's accessible name really comes from.

- **The README stops overclaiming, which matters more here than elsewhere: an
  accessibility library that oversells misleads exactly the people who depend on
  it.** The headline said *"One call fixes it"*; measured, after `enable()`
  alone an entry displaying `buy milk` is an `EditControl` whose ValuePattern
  reads `''` — a confidently wrong answer where bare Tk gave no answer at all.
  It now says what the project can prove: **one call makes it findable and
  readable.** The quickstart table gained a column separating what `enable()`
  does on its own from what takes another line, because its `Entry` row was
  quietly showing the result of two extra hand-written calls. Three gaps that
  were undocumented or buried are now caveats beside the `Invoke` limitation:
  a name goes stale after `config(text=…)` until `add_acc_object(widget)`
  re-reads it (`bind_text_variable` being the durable answer); a
  `tk.Button(state=DISABLED)` reads back `IsEnabled=True` and no state is ever
  tracked; and compound-widget items — `Listbox` rows, `Treeview` items,
  `Notebook` tabs — are not in the tree at all. One claim did **not** survive
  measurement and is documented as working rather than broken: an annotated
  `Checkbutton`'s `ToggleState` is correct *and follows its variable* with no
  call to this package, so the state gap is really about disabled, selected and
  read-only. Also: a CI badge, ten public functions that no longer answer
  `help()` with nothing, and the last two `v0.1` strings.

- **`probes/` ships the scripts behind the numbers.** Several measurements in
  the README were made out-of-band, which is an odd thing for a project whose
  whole argument is falsifiability.
  `probes/what_enable_alone_gives_you.py` launches a window that calls
  `enable(root)` and deliberately says nothing else, reads it back from another
  process, and prints the empty ValuePattern, the stale name, the disabled
  button that reads as enabled and the checkbox state that was right all along.
  A reader who doubts a row can now re-run it instead of taking it on trust.

## 0.2.0 — 2026-07-26

- **`bind_value_variable(widget, variable)` keeps a widget's accessible value in
  step with the variable behind it, exactly as `bind_text_variable` already did
  for its name.** The symptom it removes is a stale value, which is the worst
  way an accessibility tree can be wrong: the box on screen shows what was just
  typed while UI Automation goes on answering with whatever was written at
  startup, and no client can tell a stale value from a true one — a value is
  also the property a screen reader and a test tool re-read more than any other.
  The mechanism is the one already proven for names: a `write` trace on the
  variable, writing `PROPID_ACC_VALUE` through the same `AccessibilityStore`
  seam, and writing once immediately on binding, because a trace fires on the
  *next* change and never for the one already made. What it fixes for a
  consuming application is six lines of hand-rolled `trace_add` plus a handler
  it has to remember to call once by hand, per entry, collapsing to
  `tk_uia.bind_value_variable(entry, draft)`. The trace-and-say-it-now mechanism
  common to both bindings now sits in one place, so the two read as the siblings
  they are. Specified against the recording store and fake widgets with no Tk,
  no display and no Windows, and proven end to end by a ninth gui spec that
  watches a real entry's ValuePattern follow a `StringVar` from
  `'Write the report'` to `'Write the quarterly report'`, read from another
  process.

- **The gui spec covering the *name* case is now named for the name.**
  `test_a_value_bound_to_a_tk_variable_follows_it_when_the_application_changes_it`
  always watched a status label's `Name` follow a `StringVar`, so it is now
  `test_a_name_bound_to_a_tk_variable_follows_it_when_the_application_changes_it`
  and the old name belongs to its value-side twin. Neither spec's assertions
  changed. The fixture app's entry is now driven by a `StringVar` and bound with
  the new call, so the value read cross-process is the binding's work rather
  than a one-off `set_acc_value` at startup.

## 0.1.0 — 2026-07-26

First release. A library that makes Tkinter widgets visible to Windows
accessibility clients: one `enable(root)` call, and a window full of unnamed,
mis-roled controls starts announcing itself to screen readers and to UI
Automation.

- **The problem, stated precisely, because the usual version of it is wrong.**
  Tk is not absent from the accessibility tree. Tk 8.6.15 creates one real HWND
  per widget, every one of them is present, and every `BoundingRectangle` is
  correct — probed across 30 widget types. What is missing is identity: `Name`
  and `AutomationId` are empty on **all thirty**, `tk.Label` arrives as an
  `ImageControl` rather than as text, and `tk.Entry`, `Text`, `Canvas`,
  `Listbox` and all fifteen `ttk` widget types arrive as anonymous
  `PaneControl`. There is structure, and nothing to announce or match on. No
  client can fix that from outside, because there is no name to search for.

- **`enable(root)` annotates the application through MSAA, and Windows bridges
  it to UI Automation.** `IAccPropServices` lets a process annotate the
  accessible properties of its own windows; UI Automation reads them back
  through an Annotation Proxy that takes priority over the plain one. Roles come
  from `winfo_class()` via `ROLE_FOR_TK_CLASS`, names from `-text`, and both are
  overridable. The `41`/`42` split is load-bearing: `ROLE_SYSTEM_STATICTEXT`
  becomes a `TextControl`, and `ROLE_SYSTEM_TEXT` becomes an `EditControl` **and
  gains a ValuePattern that did not exist before it** — a role is not a label on
  an existing object, it decides which patterns the bridge offers for it at all.
  Widgets are picked up as Tk maps them, through `<Map>`/`<Destroy>` bound on
  the `all` bindtag with `add="+"`, plus a one-time sweep of everything already
  on screen, since `<Map>` fires once on the way up and never again for a window
  that was already showing.

- **`enable()` returns what it did.** `Strategy.ANNOTATED`, `NATIVE` or
  `UNSUPPORTED`. This is the only way a caller or a spec can tell "annotated"
  from "the version gate mis-fired and this silently did nothing at all", and
  the two are otherwise the same silence. The fixture app in this repo asserts
  `ANNOTATED` and refuses to start otherwise, so a mis-fired gate fails a test
  rather than quietly degrading a suite into measuring bare Tk.

- **Raw `ctypes`, and no runtime dependencies — permanently.** This is installed
  inside somebody else's application, which must not inherit a test tool's
  dependency tree in order to make its buttons announceable. `comtypes` was
  refused for the same reason, and because it has no bundled `IAccPropServices`
  and its `GetModule("oleacc.dll")` writes generated code into `site-packages`
  on first run. Two details in the COM layer return `S_OK` and do nothing when
  they are wrong — the exact failure this package exists to refuse — so neither
  was guessed at: every `PROPID_ACC_*` GUID is transcribed from `oleacc.h`
  rather than recalled (`PROPID_ACC_HELP` is not the value intuition suggests),
  and `MSAAPROPID` is a `typedef GUID`, so `idProp` is passed **by value**;
  passing a pointer compiles, runs, returns `S_OK` and annotates nothing.

- **The honest limitation, under test rather than only in prose.** An annotated
  `tk.Button` advertises an `InvokePattern` and a default action of "Press", and
  **both lie**: `InvokePattern.Invoke()` and
  `LegacyIAccessible.DoDefaultAction()` each return cleanly, with no exception
  and no error code, and the Tk command behind the button never runs. The proxy
  synthesises Invoke from a posted `BM_CLICK`, and every Tk button is
  owner-drawn, so that message goes into the void.
  `test_an_annotated_button_still_cannot_be_pressed_through_its_invoke_pattern`
  watches a counter inside the fixture app stay at `presses 0` across both
  calls, then move to `presses 1` when the application presses its own button —
  so the counter is demonstrably live and the silence belongs to the client. If
  a future Tk or Windows makes Invoke start working, that spec goes red and says
  the documentation needs rewriting. Annotation makes widgets **findable and
  readable, not activatable**; assistive technology and test tools must click.

- **Proven from a separate process, which is the only place it can be proven.**
  `_accprop.py` has no unit tests by design: it holds no decision worth one, and
  a recording double would agree happily with a COM call that returned `S_OK`
  and changed nothing. Eight gui specs launch a real Tk window into a process of
  its own and read it back with `uiautomation` from the pytest process. Measured
  there: `ButtonControl`/`'New Task'`, `TextControl`/`'Task list'`,
  `EditControl`/`'Title'` with ValuePattern `'Write the report'`, `AutomationId`
  `'4207'` from an explicit `GWLP_ID`, and a name bound to a `StringVar`
  following it from `'ready'` to `'task created'`. The control group is a
  `tk.Canvas` — the one widget class with no entry in `ROLE_FOR_TK_CLASS`, so
  `enable()` walks straight past it and it stays the anonymous `PaneControl`
  bare Tk hands out. `forget()` turns an annotated label back into a nameless
  `ImageControl` and an annotated entry back into a nameless pane, which is
  `ClearHwndProps` proven from outside the process that wrote the annotations.

- **`ttk` is strictly worse than classic `tk`,** which is counter-intuitive and
  worth knowing before starting a Tk project. Measured across all fifteen themed
  widget types: every one is an anonymous `PaneControl`, and `ttk.Button` has no
  `InvokePattern` at all, where classic `tk.Button` at least arrives as a
  `ButtonControl`. `ROLE_FOR_TK_CLASS` covers both families, so `enable()` fixes
  ttk too — but it raises ttk to where classic Tk already was, and no higher.

- **A version gate, shipped now rather than retrofitted.** TIP 733 is Final for
  Tk 9.1, which implements MSAA natively with the same role mapping and the same
  `<Map>` registration. `enable()` reads `info patchlevel` by digit runs so the
  `9.1b1` betas parse, and for Tk ≥ 9.1 confirms the `tk accessible` ensemble
  really exists — by handing `tk` a subcommand it cannot have and reading the
  list it complains back with, so that no native accessibility command is ever
  *run*. It then returns `NATIVE` and binds nothing; a 9.1 build with the
  feature compiled out is still annotated, because guessing `NATIVE` there would
  leave it mute. The runway is long — CPython 3.13/3.14 bundle Tk 8.6.15 and
  CPython 3.15 bundles Tk 9.0.4, which has none of it, so the earliest bundled
  accessible Tk is realistically CPython 3.16 — but the gate ships now, because
  retrofitting one means debugging it in the field.

- **Failures that are loud rather than quiet.** A destroyed widget's handle is
  cleared through the HWND cached at map time, since `winfo_id()` may already be
  raising by the time `<Destroy>` arrives — and Windows recycles handles, so a
  stale annotation on a recycled one puts a dead widget's name on an unrelated
  control and looks exactly like a flaky locator. A widget rebuilt at the same
  Tk path on a new handle releases the old one first. An identical rewrite is
  skipped, because `<Map>` fires on every unhide, tab change and geometry
  shuffle. A call from a thread other than the one that ran `enable()` raises
  `AnnotationRefused`, because Tk and the COM apartment both belong to the
  thread that entered them. `set_automation_id` refuses to overwrite a non-zero
  existing control id rather than silently stopping an owner-drawn widget from
  being painted.

- **A unit suite with no Tk, no display and no Windows in it,** and a CI lane
  that keeps it that way. All behaviour sits above the `AccessibilityStore`,
  `TkWidget` and `TkInterpreter` Protocols and is specified against a
  `RecordingStore` and a `FakeWidget`; `__init__.py` imports neither `tkinter`
  nor `ctypes.windll`, and `_accprop.py` uses plain `ctypes` types rather than
  `ctypes.wintypes`, which does not import on Linux at all. CI runs
  `pytest -m "not gui"` on {Ubuntu, Windows} × {3.10, 3.13}; the Ubuntu lane is
  the meaningful one, since this package is installed at runtime inside somebody
  else's application. The gui suite is local-only in v0.1 — it needs an
  interactive desktop.

- **Verification stops at the accessibility tree.** That is what a screen reader
  consumes, so it is the right boundary to have reached first, but it is a
  boundary: nothing here has yet been heard out loud. Driving NVDA and asserting
  on captured speech is the first item on [ROADMAP.md](ROADMAP.md).
