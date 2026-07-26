# Roadmap

Direction: this library exists to be deleted. Tk 9.1 implements MSAA natively
(TIP 733), with the same role mapping and the same `<Map>` registration, so
every item below either shortens the gap until that lands, or raises confidence
that what ships today is really being announced to a person rather than merely
present in a data structure. Breadth of MSAA surface comes second to that, and
performance does not come into it at all: annotating a window is a handful of
COM calls, paid once per widget.

## Shipped in v0.1

Role and name annotation for every classic and themed Tk widget, driven by
`<Map>`, with a version gate that stands down for a Tk that answers for itself,
and a package that costs an application nothing to install.

- **`enable(root)`, and it reports what it did.** `ANNOTATED`, `NATIVE` or
  `UNSUPPORTED`, returned rather than logged, because "annotated" and "the gate
  mis-fired and this did nothing" are otherwise the same silence.
- **Roles inferred from `winfo_class()`, names from `-text`**, both overridable,
  and names never invented for a widget that has none.
- **Auto-registration** on `<Map>`/`<Destroy>` on the `all` bindtag with
  `add="+"`, plus a one-time sweep of everything already on screen, because
  `<Map>` fires once and will not fire again for a window that was already up.
- **Handles released on destroy**, through the HWND cached at map time, so a
  handle Windows recycles does not arrive wearing a dead widget's name.
- **A thread guard.** Tk and the COM apartment both belong to the thread that
  entered them, and an annotation made from another one is written where no
  client will look. `AnnotationRefused`, rather than silence.
- **Proven from another process.** Eight gui specs launch a real Tk window and
  read it back through UI Automation, including the one that pins the honest
  limitation: `InvokePattern.Invoke()` returns cleanly and presses nothing.
- **Zero runtime dependencies**, and a unit suite that runs with no Tk, no
  display and no Windows — enforced by the Ubuntu CI lane.

## Next

- **Verify with a real screen reader.** Verification today stops at the
  accessibility tree. That is what a screen reader consumes, so it is the right
  boundary to have reached first — but "NVDA can read this tree" and "NVDA says
  the right thing at the right moment" are different claims, and only the first
  is evidenced. What is missing is a run against NVDA with its speech captured
  (the `nvda_speech` log, or the NVDA Remote add-on), asserting that moving
  focus to the button announces "New Task button" rather than merely that the
  tree says so. The README states the boundary; this is the item that moves it.
- **Wire the Tk 9.1 native path.** `enable()` detects the `tk accessible`
  ensemble and defers to it — binding nothing and calling nothing, deliberately,
  because those commands have never been run here or anywhere else. Turning
  `NATIVE` into "call Tk's own commands, so one API covers both eras" is the
  main outstanding piece of work, and it is blocked on Tk 9.1 being installable
  rather than on any open design question.
- **`IAccPropServer` for dynamic properties.** Everything today is *pushed*: a
  value is written when the application says so, and `bind_text_variable` exists
  precisely because otherwise a status line goes stale. An `IAccPropServer` is
  *pulled* — the client asks, and the application answers with the current
  truth. That removes the whole class of "the tree says something the window
  stopped showing", and it is the right shape for a listbox or a treeview, whose
  contents are far too large to push on every change.
- **Compound widgets, not just the HWND they live in.** A `Listbox` is annotated
  as a `LIST` and its *items* are invisible; the same goes for `Treeview` rows
  and `Notebook` tabs. Exposing them means child ids under one HWND — MSAA's
  `IAccessible` child model, which is a different piece of machinery from
  annotating a window handle.
- **Publishing to PyPI.** Out of scope for v0.1 by decision, not by omission.
  The name is free.

## Non-goals

These are deliberate, not oversights. Each is a decision that was made, and the
reason it was made.

- **Non-goal: making Tk widgets activatable.** `InvokePattern` on an owner-drawn
  Tk button returns cleanly and fires nothing, and no amount of annotation
  changes that — the pattern is synthesised by the MSAA proxy from a posted
  `BM_CLICK`, and Tk does not listen for one. The fix belongs in Tk, or in Tk
  9.1's own provider, not here; shipping an API for it would be shipping an API
  that silently does nothing, which is the failure mode this package exists to
  refuse. Clients must click. A spec fails the day this stops being true.
- **Non-goal: annotating other processes.** `IAccPropServices` annotates the
  calling process's own windows. Reaching across does not raise — it silently
  does nothing, and can corrupt an annotation the other process made properly.
  The README documents the `SetWindowTextW` names-only rescue for applications
  you cannot modify, with that warning attached; it will not be wrapped in an
  API here, because an API is an invitation.
- **Non-goal: non-Windows platforms.** MSAA is a Windows API. `enable()` returns
  `UNSUPPORTED` off Windows so that cross-platform applications can call it
  unconditionally, and the whole unit suite runs there — but that exists to keep
  the design honest, not because an ATK port is planned. Linux accessibility for
  Tk is a different project with a differently shaped hole in the middle of it.
- **Non-goal: runtime dependencies.** Permanently empty, and that is a feature:
  this is installed inside somebody else's application, which must not inherit a
  test tool's dependency tree in order to make its buttons announceable. It also
  rules out `comtypes`, which has no bundled `IAccPropServices` anyway, and
  whose `GetModule("oleacc.dll")` writes generated code into `site-packages` on
  first run.
- **Non-goal: automatic AutomationIds.** `enable()` never assigns one. `GWLP_ID`
  is the control id Win32 puts in `WM_COMMAND.wParam` and `WM_DRAWITEM.idCtl`,
  and every Tk button is owner-drawn — so an id written over an existing one can
  stop a widget being painted. An id derived from a widget path would also make
  every repack a breaking change for whoever locates by it.
- **Non-goal: touching toplevels.** `wm title` already gives a window a correct
  accessible name, and overriding it breaks resolving a window by its title,
  which is where every other query starts.
