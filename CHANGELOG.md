# Changelog

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
