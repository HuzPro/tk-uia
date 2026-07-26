# Changelog

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
