# DUST_WINDOWS_MICROMAMBA_PLAN.md

**Goal:** make the Phase T2 dust / ISM `query.py` subcommands runnable on a **native-Windows**
checkout — where `pip install dustmaps` fails because `healpy` has no native-Windows pip wheel — by
serving the dust path from an isolated **micromamba** environment, reached transparently over a
subprocess boundary (**Option B**). The native Python install and every non-dust feature stay
exactly as they are; **WSL / Linux / macOS are unaffected (no micromamba, no behavior change).**

- **Status:** **CODE SHIPPED on WSL** — Parts B (shim), C (docs), D (tests) and E1 (WSL no-op
  verification) are **done and committed to `main`**. The requirements audit found **no changes
  needed**. What remains is the **native-Windows setup (Part A) + Windows verification (Part E2)**.
  → **When you load this on Windows, START AT [Part A](#part-a) below.** Moves to `completed_plans/`
  once Windows verification is green.
- **Date:** 2026-09-07
- **Target platform for the setup steps:** native Windows only. WSL/Linux/macOS need none of Part A.
- **Branch/commit policy:** commit directly to `main` (standing directive — repo is main-only).

---

## 0. Decision summary

| Question | Decision |
|---|---|
| Package that blocks Windows | `healpy` — no native-Windows **pip** wheel (`dustmaps` hard-requires it). Unchanged as of Sept 2026 (healpy docs still say Linux/macOS only, Windows via WSL). |
| Native-Windows route that *does* exist | **conda-forge `win-64`** build of healpy (currently 1.20.0, 2026-07-25). Not pip. |
| Tool | **micromamba** (single static binary, no base env, touches no global PATH) — chosen over Miniforge for an isolated, non-interactive, subprocess-invoked env. |
| Routing model | **Option B** — a re-dispatch shim *inside* `query.py`, keyed on "can this interpreter `import healpy`?". No change to the consumer contract, the sister repo's `bin/sfq`, or the skill's Q21. |
| opt 59 (fetch) | **No code change** (explicitly removed from scope). The map fetch is a one-time step done via manual resumable download or a one-time env-side fetch. |

**One sentence:** *serve dust in-process if you can; otherwise hand it to a Python that can* — and
because Unix already can, the shim is a pure no-op there.

---

## 1. Background (why this is needed and why it's shaped this way)

- `core/dust.py` is the **only** module that imports `dustmaps`/`healpy`, and it does so **lazily**
  (function-local). That is what keeps the stellar layer importable on a Windows checkout that never
  installed the extra. The dust *query* subcommands are `query.py`-only.
- On native Windows, `pip install -r requirements-dust.txt` fails at the `healpy` build step (no
  wheel). So today the dust subcommands there return the curated
  `_DUST_EXTRA_MSG` ("… dustmaps needs healpy, which has no native-Windows pip wheel").
- conda-forge **does** ship a `win-64` healpy, so a conda/micromamba env can run the dust code
  natively on Windows. The problem is purely "how does the native-Python app reach a package that
  lives in a different interpreter's environment?" — and the answer is **a subprocess boundary**,
  because compiled C-extensions (healpy links HEALPix C++ + conda-forge libs, built against conda's
  numpy ABI) are **not** importable across interpreters/ABIs. A `sys.path` hack does not work.
- `query.py` is already a subprocess-invoked JSON dispatcher (that is how the sister repo calls it),
  so a subprocess hop for the dust subset is natural and invisible to callers.

---

## 2. Architecture of the fix

A single shim in `query.py`, invoked after argument parsing and before `args.func(args)`:

```
raw_argv = list(sys.argv[1:]) if argv is None else list(argv)   # captured at top of main()
args = parser.parse_args(argv)
...
if _needs_dust(args):
    _redispatch_to_dust_env(raw_argv)   # either sys.exit()s (routed) or returns (serve in-process)
try:
    args.func(args)
except Exception as e:
    _out({"error": str(e)})
```

**`_needs_dust(args)`** — true only for the dust-map-loading paths:
- `getattr(args, "func", None) in (cmd_dust_sightline, cmd_dust_between)`, **or**
- `getattr(args, "weight", None) in ("dust", "blend")` — covers the 5 routing forks
  (`optimal-tour`/`jump-route`/`multi-stop`/`nearest-neighbor`/`trade-route`) **and**
  `network-centrality --weight dust`. `blend` is included because `compute_jump_route_blend` also
  loads the dust map.

**`_redispatch_to_dust_env(raw_argv)`** — decides in this order:
1. **Recursion guard:** if `os.environ.get("SPACE_APP_DUST_SUBPROCESS") == "1"` → `return` (we ARE
   the child; run in-process; never spawn again).
2. **Capability check:** `import core.dust; if core.dust._dustmaps_available(): return` (serve
   in-process) — the **same gate the app itself uses** (checks `dustmaps` AND `healpy`), so it can't
   drift from the real requirement or falsely serve in-process on a `healpy`-present/`dustmaps`-absent
   box. This is the branch that makes the shim a **no-op on WSL/Linux/macOS** and inside the conda child.
3. **Route:** read `SPACE_APP_DUST_PYTHON`. If unset → `return` (fall through to the existing curated
   `_DUST_EXTRA_MSG`). If set → launch the child, wrapped so a launch failure becomes curated JSON:
   ```
   if os.name == "nt":                                    # keep C:\ backslashes AND strip matched quotes
       parts = [strip_surrounding_quotes(p) for p in shlex.split(cmd, posix=False)]
   else:
       parts = shlex.split(cmd)
   try:
       child = subprocess.run(
           [*parts, os.path.abspath(__file__), *raw_argv],
           env={**os.environ, "SPACE_APP_DUST_SUBPROCESS": "1"},
       )                                                   # stdout/stderr inherited → child JSON passes through
   except Exception as e:
       _out({"error": f"Could not launch … ({cmd!r}): {e}"})   # curated JSON, not a traceback (_out exits 1)
   sys.exit(child.returncode)                              # preserves _out()'s 0/1 exit contract
   ```
   **The child's stdout is relayed verbatim**, so `SPACE_APP_DUST_PYTHON` must name an interpreter that
   prints **nothing** to stdout — prefer the env's `python.exe` directly (no launcher output) over an
   activation wrapper (see Part A4).

**Cross-platform behavior (falls out of the capability check, no OS branching):**

| environment | `import healpy` here? | result |
|---|---|---|
| WSL / Linux / macOS (dust extra pip-installed) | ✅ | in-process — **byte-identical to today** |
| Windows native + micromamba env (`SPACE_APP_DUST_PYTHON` set) | ❌ → route | conda child runs it in-process, JSON relayed, exit code preserved |
| Windows native, nothing configured | ❌, unset | curated `_DUST_EXTRA_MSG` (as today) |
| inside the conda child | ✅ (+ sentinel set) | in-process; guard blocks re-spawn |

**Notes / invariants:**
- The child runs the **same `query.py`** from the **same repo checkout**, so it shares `data/space_app.db`
  and the `data/dust/` cache automatically (both derived from `__file__`).
- Overhead is one extra Python startup (~0.5–1 s) **only** for dust commands on Windows — negligible
  against loading a multi-GB dust cube.
- The shim uses a cheap local `import healpy` (not `import core.dust`) so non-dust calls never pay the
  numpy/astropy load, preserving the lazy-import performance property `query.py` already relies on.

---

## 3. Ownership split — who runs what

Because this session runs in **WSL** and cannot (and should not) install a package manager, download
~5.6 GB of maps, or set a persistent user env var on your **Windows** box, the work is split:

| Part | Who | Where | Status |
|---|---|---|---|
| **A. System setup** (micromamba install, env, map fetch, env var) | **Greg** runs the commands below | Windows host (PowerShell) | ⬜ **TODO on Windows** |
| **B. Code** (the `query.py` shim) | Claude | repo (WSL) | ✅ done |
| **C. Docs** | Claude | repo (WSL) | ✅ done |
| **D. Tests** (offline, mock-based) | Claude | repo (WSL) | ✅ done (8/8 pass) |
| **E1. Verification — WSL no-op regression** | Claude | repo (WSL) | ✅ done |
| **E2. Verification — Windows routing** | **Greg** runs the commands below | Windows host | ⬜ **TODO on Windows** |

All Part-A and Windows Part-E commands are copy-paste ready below.

---

<a id="part-a"></a>

## PART A — System setup on the native-Windows host  *(Greg runs these — ⭐ START HERE on Windows)*

> **This whole part is Windows-only and runs in a native PowerShell window** (not WSL). You need it
> **only if you intend to run the app on native Windows** — if you run it from WSL, skip Part A
> entirely: the WSL venv **already has the dust extra installed and working** (confirmed: healpy 1.19.0
> + dustmaps import cleanly), so the shim stays a no-op there and nothing needs installing.
> Substitute `C:\path\to\SpaceAndScienceFictionApp` with your actual **Windows** checkout path.
> These commands install into their own directory and set **one user env var** — they do **not**
> modify PATH or your native Python, and everything is reversible (see **Part F**).
>
> *(You can technically fire these from WSL via `powershell.exe -Command "…"`, but for a package-manager
> install, a ~5.6 GB download, and a persistent env var — where Windows vs `/mnt/c` path alignment
> matters — open a real PowerShell window on Windows and run them there.)*

### A1. Install micromamba (isolated, no shell init, no PATH change)

```powershell
# Install location for the binary + the env root prefix
$Root = "$HOME\micromamba"
New-Item -ItemType Directory -Force -Path $Root | Out-Null

# Download the latest win-64 micromamba (a .tar.bz2 containing Library\bin\micromamba.exe)
curl.exe -L -o "$env:TEMP\micromamba.tar.bz2" "https://micro.mamba.pm/api/micromamba/win-64/latest"

# Extract just the executable (Win10+ ships bsdtar, which reads .tar.bz2)
tar -xf "$env:TEMP\micromamba.tar.bz2" -C $Root Library/bin/micromamba.exe

# Remember the exe path
$Mm = "$Root\Library\bin\micromamba.exe"
& $Mm --version        # sanity: prints a version like 2.x
```

*(Alternative: `Invoke-Expression ((Invoke-WebRequest -Uri https://micro.mamba.pm/install.ps1 -UseBasicParsing).Content)` — the official installer, but it may offer to touch your profile/PATH. The manual binary above avoids that entirely. Reference: <https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html>.)*

### A2. Create the `dust` environment from conda-forge

```powershell
& $Mm create -y -r $Root -n dust -c conda-forge `
    python=3.12 dustmaps healpy h5py scipy numpy astropy astroquery requests pyvo `
    progressbar2 six tqdm
```

- `dustmaps` pulls `healpy`/`h5py`/`scipy`/`astropy`/`numpy` as dependencies; they are listed
  explicitly for reproducibility.
- This mirrors the **science subset of `requirements.txt` + all of `requirements-dust.txt`**.
- **No PySide6** — `query.py`'s dust path is Qt-free.
- Verify healpy imports in the env:
  ```powershell
  & $Mm run -r $Root -n dust python -c "import healpy, dustmaps; print('healpy', healpy.__version__)"
  ```

### A3. Fetch the dust maps (one-time, ~5.6 GB total)

The cache lives in the repo at `data\dust\` (gitignored) and both interpreters read the same files.
Two routes — **A3-Option-2 (manual resumable) is recommended** because Zenodo throttles large
downloads and dustmaps' own fetcher can't resume.

**A3-Option-1 — let dustmaps fetch (simple, but no resume; painful for the 3.2 GB Edenhofer):**
```powershell
cd C:\path\to\SpaceAndScienceFictionApp
& $Mm run -r $Root -n dust python -c "import core.dust as d, json; print(json.dumps(d.compute_dust_fetch(map_sel='auto'), indent=2, default=str))"
```

**A3-Option-2 — manual resumable download into the exact cache paths (recommended):**
```powershell
cd C:\path\to\SpaceAndScienceFictionApp
New-Item -ItemType Directory -Force -Path "data\dust\leike_2020","data\dust\edenhofer_2023" | Out-Null

# aria2c resumes (-c) and parallelizes (-x4) past Zenodo's per-connection throttle.
# Install it once if needed:  winget install aria2.aria2   (or: scoop install aria2)

# Leike 2020  (~2.4 GB, md5 1ea998fdaef58f53da639356362223ba)  ->  data\dust\leike_2020\mean_std.h5
aria2c -c -x4 -d "data\dust\leike_2020" "https://zenodo.org/record/3993082/files/mean_std.h5"

# Edenhofer 2023/2024 (~3.2 GB)  ->  data\dust\edenhofer_2023\mean_and_std_healpix.fits
aria2c -c -x4 -d "data\dust\edenhofer_2023" "https://zenodo.org/record/8187943/files/mean_and_std_healpix.fits"
```
*(No aria2c? `curl.exe -L -C - -o "data\dust\leike_2020\mean_std.h5" "https://zenodo.org/record/3993082/files/mean_std.h5"` resumes with `-C -`. Same for the Edenhofer URL into `data\dust\edenhofer_2023\mean_and_std_healpix.fits`.)*

**Confirm the cache (no healpy needed — `get_dust_map_status` is pure-pathlib):**
```powershell
& $Mm run -r $Root -n dust python -c "import core.dust as d, json; print(json.dumps(d.get_dust_map_status(), indent=2, default=str))"
```
Expected: both maps present with sizes ≈ 2400 MB and ≈ 3200 MB.

### A4. Point the app at the env (one persistent user env var)

**Recommended — the env's `python.exe` directly.** No launcher runs, so nothing can print to stdout
ahead of the JSON the consumer parses (query.py relays the child's stdout verbatim), and it works for
healpy/numpy/astropy:
```powershell
# Persist for future shells (does NOT change PATH or native Python):
setx SPACE_APP_DUST_PYTHON "$Root\envs\dust\python.exe"

# Also set it for the CURRENT shell (setx only affects new shells):
$env:SPACE_APP_DUST_PYTHON = "$Root\envs\dust\python.exe"
```
The stored value expands to something like `C:\Users\greg\micromamba\envs\dust\python.exe`.

*(Fallback — `micromamba run`, only if a package needs full env activation:
`setx SPACE_APP_DUST_PYTHON "$Mm run -r $Root -n dust python"`. It performs proper activation but
**must stay silent on stdout** — `micromamba run` normally is, but a stdout-echoing shell
profile/activation hook would prepend to and corrupt the relayed JSON. The shim accepts either form.
Prefer a path without spaces; if unavoidable, the shim strips matched surrounding quotes on Windows,
and a bad/not-found interpreter is reported as a curated `{"error"}`, not a traceback.)*

### A5. Env smoke test (before touching the app)

```powershell
cd C:\path\to\SpaceAndScienceFictionApp
& $Mm run -r $Root -n dust python query.py dust-sightline --star "Vega" --dist-end 50 --steps 10
```
Expected: a JSON sightline result with `units: "A_V (mag, R_V=3.1)"` and per-bin values — **not**
the `_DUST_EXTRA_MSG` error. (This proves the env + maps work before the shim is even involved.)

---

## PART B — Code changes  *(Claude implements; one file)*

### B1. `query.py` — the re-dispatch shim

- **New import(s)** at the top of `query.py`: `os` (likely already imported), `shlex`, `subprocess`.
- **New helpers** (place near the other private helpers, e.g. just after `_out`):
  - `_needs_dust(args) -> bool` — as specified in §2.
  - `_redispatch_to_dust_env(raw_argv) -> None` — as specified in §2 (recursion guard → `import
    healpy` capability check → `SPACE_APP_DUST_PYTHON` route → `sys.exit(child.returncode)`; returns
    without exiting when it decides to serve in-process).
- **Wire into `main()`** (currently query.py:1901; dispatch tail at ~4335–4342):
  - At the top of `main()`, capture `raw_argv = list(sys.argv[1:]) if argv is None else list(argv)`
    **before** `parser.parse_args`.
  - After `args = parser.parse_args(argv)` and the existing CR-19 `gaia_timeout` block, add:
    `if _needs_dust(args): _redispatch_to_dust_env(raw_argv)`.
- **Windows path safety:** `shlex.split(cmd, posix=(os.name != "nt"))` so backslash paths in
  `SPACE_APP_DUST_PYTHON` are not mangled.
- **~35 lines total.** No other logic in `main()` changes.

### B2. No other code changes

- `core/dust.py`, `core/dust_routing.py`, `main.py`, the GUI, and `requirements*.txt` are **untouched**.
- The existing `_DUST_EXTRA_MSG` remains the honest fallback when nothing is configured.
- **opt 59 (CLI + GUI) is explicitly out of scope** — no `dust-fetch`/`dust-status` subcommands, no
  micromamba wiring in the fetch panel. Fetch is the one-time Part-A3 step.

---

## PART C — Documentation  *(Claude implements)*

1. **`requirements-dust.txt`** — add a short "Native Windows via conda-forge/micromamba" note pointing
   at this plan and naming `SPACE_APP_DUST_PYTHON`.
2. **`docs/integration.md`** (Dust / ISM section, near line ~3259 where the Windows gate is described) —
   document the Option-B routing: the `SPACE_APP_DUST_PYTHON` env var, the `SPACE_APP_DUST_SUBPROCESS`
   internal sentinel, the "import-healpy → in-process, else route" rule, and that WSL/Linux/macOS are
   unaffected.
3. **`CLAUDE.md`** — one sentence in the Phase T dust-path paragraph: native Windows can now serve the
   dust subcommands via a micromamba env + the `query.py` shim (`SPACE_APP_DUST_PYTHON`), while the
   pip extra stays WSL/Linux-only.
4. This plan file itself documents the full setup (Part A) and moves to `completed_plans/` on ship.

---

## PART D — Tests  *(Claude implements + runs in WSL; all offline)*

New `tests/test_dust_redispatch.py` — **9 tests**, all offline + OS-independent (mock the capability
probe `core.dust._dustmaps_available` and `subprocess.run`; no network/conda/Qt):

- **`test_needs_dust_*`** (×3) — `_needs_dust` true for `cmd_dust_sightline`/`cmd_dust_between` and for
  `weight in {"dust","blend"}`; false for a plain `distance`/`hops` route and a non-dust command.
- **`test_noop_when_dust_available`** — probe returns True → `_redispatch_to_dust_env` returns without
  spawning (even with `SPACE_APP_DUST_PYTHON` set), and it **delegates to `core.dust._dustmaps_available`**
  (asserts the gate was consulted). Proves the WSL/Linux/macOS path is unchanged and can't drift.
- **`test_sentinel_blocks_recursion`** — with `SPACE_APP_DUST_SUBPROCESS=1`, the shim returns immediately
  **before** the probe (asserts the probe was not even called).
- **`test_falls_through_when_no_dust_python`** — probe False + `SPACE_APP_DUST_PYTHON` unset → returns,
  no spawn (curated `_DUST_EXTRA_MSG` still surfaces downstream).
- **`test_routes_when_configured`** — probe False + env set → `subprocess.run` called once with
  `[*parts, <query.py>, *argv]` and `SPACE_APP_DUST_SUBPROCESS=1` in the child env; exits with the child's
  code (`test_routes_preserves_nonzero_exit` pins the non-zero case).
- **`test_launch_failure_yields_curated_error`** — `subprocess.run` raises → the shim emits curated
  `{"error"}` JSON (naming `SPACE_APP_DUST_PYTHON`) and exits 1, **never a raw traceback**.

Update **`docs/testing.md`** with the new file's entry. Run:
```bash
venv/bin/python -m pytest tests/test_dust_redispatch.py -q
venv/bin/python -m pytest -q      # full offline suite stays green (baseline 3362 passed / 89 skipped)
```

---

## PART E — Verification

### E1. WSL no-op regression  *(Claude runs)*
- Confirm `import healpy` succeeds in the project venv (dust extra is installed on the WSL box), so the
  shim is dormant, and existing dust behavior is unchanged:
  ```bash
  venv/bin/python query.py dust-sightline --star "Vega" --dist-end 50 --steps 10   # unchanged output
  ```
- Full offline pytest stays green.

### E2. Windows routing  *(Greg runs, after Part A)*
```powershell
cd C:\path\to\SpaceAndScienceFictionApp

# 1) Native python, dust command -> transparently routed to micromamba, returns JSON (not the extra error)
python query.py dust-sightline --star "Vega" --dist-end 50 --steps 10

# 2) A dust-weighted route -> also routed
python query.py jump-route --origin Sol --destination "Sirius" --max-jump 5 --weight dust

# 3) A NON-dust command -> runs on native python, no subprocess, fast, unchanged
python query.py distance --star1 Sol --star2 "Alpha Centauri"

# 4) Graceful fallback: temporarily clear the var in a fresh shell -> curated "dust extra" error, not a crash
#    (open a new shell WITHOUT the var, or:  Remove-Item Env:\SPACE_APP_DUST_PYTHON )
python query.py dust-sightline --star "Vega" --dist-end 50
```
Expected: (1) and (2) return JSON results; (3) is fast and identical to today; (4) returns the curated
`_DUST_EXTRA_MSG`.

---

## PART F — Rollback / uninstall (everything is isolated)

Nothing here touches native Python's site-packages, PATH, the registry (beyond one user env var), or
any tracked repo file. Each piece backs out independently and non-destructively.

**Code (repo side) — one commit, one file:**
```bash
git revert <shim-commit-sha>     # undoes query.py shim + docs + test file
```
Even without reverting, the code is inert unless `SPACE_APP_DUST_PYTHON` is set (falls through to the
existing curated error) and is a no-op wherever `healpy` is importable — so "back out" can be as light
as unsetting the env var.

**System (Windows side):**
```powershell
# 1) Remove the env var (empty string also disables it — the shim treats empty as "unset"):
[Environment]::SetEnvironmentVariable("SPACE_APP_DUST_PYTHON", $null, "User")

# 2) Delete the micromamba binary + the 'dust' env in one shot (no installer/registry to clean):
Remove-Item -Recurse -Force "$HOME\micromamba"

# 3) (optional) reclaim the ~5.6 GB map cache — gitignored, never tracked:
Remove-Item -Recurse -Force "C:\path\to\SpaceAndScienceFictionApp\data\dust"
```

**If a setup step fails midway:**
- **Env create fails** → the partial env is isolated under `$HOME\micromamba\envs\dust`; run
  `& $Mm env remove -r $Root -n dust -y` (or just delete `$HOME\micromamba`) and retry.
- **Map download interrupted** → `aria2c -c` / `curl -C -` **resume** rather than corrupt, and dustmaps
  verifies md5 on load; re-run the A3 command.
- **After any failure, native Python is untouched** — no pip installs ever ran against it, so there is
  nothing to repair on that side.

---

## 4. Risks, caveats, non-goals

- **Compiled-extension boundary is real:** the split MUST be at the interpreter/process line. Do not
  attempt to `sys.path`-inject the conda env into native Python — ABI/DLL mismatch. (This is why the
  shim spawns a subprocess rather than importing.)
- **Same checkout required:** the micromamba env and native Python must run the **same** `query.py` from
  the **same** repo directory (shared DB + `data/dust/`). On a machine where Greg keeps separate Windows
  and WSL checkouts, each has its own `data/dust/`; Part A fetches into the **Windows** checkout.
- **`micromamba run` vs direct `python.exe`:** both accepted by the shim; `micromamba run` preferred for
  activation robustness. If a direct-`python.exe` value ever fails to find a DLL, switch the env var to
  the `micromamba run` form.
- **setx limits:** value < 1024 chars (fine here); doesn't affect the current shell (set `$env:` too).
- **No behavior change off Windows:** guaranteed by the `import healpy` capability check, not an OS
  test — so nothing to special-case for WSL/Linux/macOS.
- **Non-goals:** no opt-59 changes; no `dust-fetch`/`dust-status` subcommands; no GUI dust support on
  native Windows (the `FetchDustMapPanel` stays gated on the extra); no attempt to produce a Windows pip
  wheel.

---

## 5. Build order

1. ✅ **B1** — shim added to `query.py` (`_needs_dust` / `_redispatch_to_dust_env`, wired into `main()`).
2. ✅ **D** — `tests/test_dust_redispatch.py` (8 tests, all pass); `docs/testing.md` updated.
3. ✅ **C** — docs (`requirements-dust.txt`, `docs/integration.md`, `CLAUDE.md`).
4. ✅ **Requirements audit** — both files up to date, no packages missing (no change needed).
5. ✅ **E1** — WSL no-op verified (shim returns in-process with healpy importable; non-dust dispatch intact).
6. ✅ **Commit to `main`.**
7. ⬜ **Greg:** run **Part A** (Windows setup) + **E2** (Windows verification) on the Windows host.
8. ⬜ On green Windows verification, move this file to `completed_plans/` and index it in its README.
