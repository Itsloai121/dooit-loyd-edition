# Dooit: problems, changes, and what still needs checking
​
**Review date:** 10 October 2026  
**Tool:** Dooit 3.3.4, from `dooit loyd edition.rar`  
**Status:** Source-only review and candidate hardening patch. **Not runtime-verified.**
​
## Read this first
​
- The requested **DevSecOps Checklist (Expanded Edition).pdf was not attached** and was not found in the archive. This review cannot claim compliance with that checklist. Upload it for an exact requirement-by-requirement assessment.
- I reviewed the attached code and made changes in a separate copy. Your original archive is unchanged.
- Project execution was blocked by the environment safety check. Approval to install the project's locked dependencies and run its tests was requested but had not been received when these files were produced. No baseline test, unit test, integration test, live port scan or GitHub workflow was run.
- The changed Python files were checked for syntax without importing/executing the application. This is useful, but does not prove the fixes work.
- Use the patched copy as a **review/test candidate**, not as a production-certified release.
​
## About the ports
​
I found no direct TCP/UDP listener, socket creation, HTTP client or server call in the application's `dooit/` source. This is static evidence, not proof about a running installation. In particular, SQLAlchemy's `listen(...)` is an event hook, not a listening network port.
​
The documentation project has development/preview commands that can start a local web server when someone explicitly runs them. The lockfile also includes development server packages; their presence alone does not mean the todo app opens ports.
​
### What I changed
​
- Added a hardcoded Python audit-hook policy that rejects IPv4/IPv6 socket creation, IP bind/connect operations and DNS lookups on normal CLI/TUI startup. There is no configuration or environment toggle to turn it off.
- Disabled automatic external Python config execution during startup, and rejected external config paths through the CLI and TUI constructor.
- Disabled the app's external-URL-opening action.
- Made the bundled documentation `docs:dev` and `docs:preview` scripts exit with an error instead of starting a server. Static documentation builds are still available.
​
### What this does NOT mean
​
I did **not** close existing ports on your computer, change a firewall, stop other programs, or scan a live machine. The guard applies to ordinary Python socket APIs in the Dooit process after installation; it is **not an OS sandbox**. Native code, child processes, code editing the guard, direct library-only use, external tools and servers launched outside the patched commands are not covered. Unix-domain sockets remain allowed for local event-loop support. The process-wide policy may affect other code if Dooit is embedded in the same interpreter.
​
For a stronger deployment guarantee, an administrator must separately apply and verify OS-level network isolation and prevent unnecessary listeners. Do not blindly block all ports on a remote host: that can disconnect administration or break unrelated services.
​
## Problems and how the source was changed
​
### F01 - Migration can erase or partially replace existing todos
​
**Priority:** High  
**Where:** `dooit/backport/migrate_from_v2.py:11, 75-93, 97-141; dooit/utils/database.py:5-10; dooit/api/manager.py:53-58` (original archive line numbers)
​
**What was wrong:** Migration opens a database at import time, commits deletion before reading and converting all legacy data, and saves each item in separate commits. A malformed later record can leave the old rows erased and only some new rows saved. The old YAML backup uses a fixed .bak name that can collide with an earlier backup.
​
**Why it matters:** User data loss during an explicitly confirmed migration. This is a local data-integrity risk, not remote exploitation.
​
**What I changed / how to fix it:** Removed the import-time connection. Migration now reads the top-level YAML first, creates unique owner-only legacy and SQLite backups before row replacement, and wraps delete/save operations in one Manager.transaction(). Failed conversions roll back row changes. Legacy cleanup happens only after commit and reports cleanup failures separately.
​
**What is verified:** Source patch supplied; runtime migration and restore tests pending.
​
**What is still left:** Schema/file creation is not rolled back with row changes. A failed first migration can leave an empty database file. Full nested schema validation, YAML size/depth limits, concurrent-writer handling and backup-restore exercises are still needed.
​
### F02 - Stylesheet identifiers can escape the cache directory
​
**Priority:** Medium  
**Where:** `dooit/utils/css_manager.py:73-94` (original archive line numbers)
​
**What was wrong:** Caller-provided stylesheet IDs are joined directly into file paths. An ID such as ../escape can target a .tcss file outside the intended stylesheets directory. The same problem affects deletion. Existing symlinks can also redirect writes.
​
**Why it matters:** A local caller or trusted Python extension can overwrite/delete reachable .tcss files. No remote or unauthenticated path to this API was found.
​
**What I changed / how to fix it:** All ID-based operations now use one validator allowing only 1-128 letters, digits, underscores or hyphens. Final-component symlinks are rejected. New injections use exclusive creation and O_NOFOLLOW where available. Reads accept only regular .tcss files.
​
**What is verified:** Source patch supplied; traversal/symlink regression tests added, not run.
​
**What is still left:** Duplicate stylesheet IDs now fail rather than overwrite. The shared cache design and main dooit.tcss write path were not fully redesigned; same-user filesystem races and concurrent app instances remain outside the fix.
​
### F03 - User configuration is executable Python
​
**Priority:** High / conditional  
**Where:** `dooit/ui/api/plug.py:40-45; dooit/ui/api/loader.py:28-40; dooit/__main__.py:11-20` (original archive line numbers)
​
**What was wrong:** Startup automatically imports the user config.py and executes its top-level code. Explicit --config does the same. This is an intended extension feature, but unsafe if a user runs a downloaded config or another actor can modify the config file.
​
**Why it matters:** An untrusted configuration can act with the user's permissions, including reading files or launching child processes. Severity depends on the trust of the config; the application is not a network service.
​
**What I changed / how to fix it:** The hardened startup scans only the bundled defaults. CLI and direct TUI construction reject external config paths. Automatic external URL opening is also disabled for the offline edition.
​
**What is verified:** Hardening source patch supplied; startup behavior test pending.
​
**What is still left:** This intentionally removes custom config/plugin convenience from normal startup. The internal loader API is still executable code and must remain trusted. This is not a sandbox for malicious Python or native extensions.
​
### F04 - Database privacy depends on the process umask
​
**Priority:** Medium  
**Where:** `dooit/api/_vars.py:4-8; dooit/api/manager.py:23-29` (original archive line numbers)
​
**What was wrong:** Default directories and SQLite files are created without explicit owner-only modes. With a typical 022 umask, the data directory/file may be readable by other local users when parent-directory access permits. Symlink database paths are not rejected.
​
**Why it matters:** Potential disclosure of plaintext todo contents to other users on the same computer. Actual exposure depends on deployment permissions; no user database was supplied.
​
**What I changed / how to fix it:** Added private storage helpers. The application-owned data directory is 0700 on POSIX; database files are precreated/tightened to 0600. Ownership, parent write permissions, regular-file type and final symlinks are checked. SQLite URLs are constructed with URL.create instead of string interpolation.
​
**What is verified:** Source patch supplied; POSIX permission/symlink tests added, not run.
​
**What is still left:** Windows ACLs and encrypted storage are not implemented. These checks do not replace an OS sandbox. Parent/ancestor trust, SQLite sidecar behavior and migration backup permissions need deployment verification. Existing default-directory permissions will be tightened.
​
### F05 - Configuration loader changes the global import search path
​
**Priority:** Medium  
**Where:** `dooit/ui/api/loader.py:18-25, 32-36` (original archive line numbers)
​
**What was wrong:** register() appends a config directory before entering the temporary context. The context removes a matching path even when that entry existed before the call. Exceptions and duplicate entries can leave or remove unexpected entries in global sys.path.
​
**Why it matters:** Import resolution can change after loading config; nearby modules may shadow expected imports. This is an import-integrity and reliability issue, conditional on trusted config use.
​
**What I changed / how to fix it:** Removed the extra append. The context snapshots sys.path and restores the same list contents in finally, including when a loaded module raises an exception.
​
**What is verified:** Source patch supplied; normal/exception restoration test added, not run.
​
**What is still left:** sys.path is process-global. Concurrent module loading is not synchronized; external Python execution remains trusted-only and is disabled in normal hardened startup.
​
### F06 - Inserting an item shifts unrelated sibling groups
​
**Priority:** Medium  
**Where:** `dooit/api/hooks/fix_hooks.py:15-24, 33-42` (original archive line numbers)
​
**What was wrong:** Both insertion hooks update every row whose order_index is high enough, without restricting the update to the inserted item's parent. Adding an item under workspace A can change ordering values under workspace B.
​
**Why it matters:** Cross-workspace ordering corruption. This is a business-logic/data-integrity bug, not SQL injection; the original values are parameterized.
​
**What I changed / how to fix it:** Workspace updates now filter by parent_workspace_id. Todo updates filter by both parent_workspace_id and parent_todo_id using null-safe SQLite IS comparisons. Updates remain parameterized.
​
**What is verified:** Source patch supplied; cross-parent ordering tests added, not run.
​
**What is still left:** Concurrent insertion and nested-copy ordering have not been stress-tested. SQLAlchemy relationship/FK timing must be confirmed by the regression suite.
​
### F07 - Input and fallback handling has reliability edge cases
​
**Priority:** Low  
**Where:** `dooit/utils/date_parser.py:6-10; dooit/utils/css_manager.py:65-69; dooit/api/manager.py:41-46` (original archive line numbers)
​
**What was wrong:** Date parsing catches only ParserError, so overflow errors can escape. Unknown theme names store a class instead of an instance. Manager.has_changed() expires the global manager session rather than the current instance.
​
**Why it matters:** Malformed large dates can interrupt UI processing. Inconsistent fallback types and the wrong session target can break integrations or independent Manager instances.
​
**What I changed / how to fix it:** Date parsing catches ValueError and OverflowError and returns an invalid-input result. The theme fallback uses a DooitThemeBase instance. Database change detection now expires self.session.
​
**What is verified:** Source patch supplied; date regression test added, not run.
​
**What is still left:** These are targeted edge-case fixes, not an exhaustive UI or parser correctness review. Additional timezone, recurrence and multi-instance tests are recommended.
​
### F08 - Test/lint CI does not gate pull requests or main
​
**Priority:** Medium  
**Where:** `.github/workflows/pytest.yml:3-10, 22-26; .github/workflows/ruff.yml:4-11, 26-29; .github/workflows/vitepress_deploy.yml:38-41` (original archive line numbers)
​
**What was wrong:** Test and lint workflows run only for pushes to develop; pull_request triggers are commented out. Dependency setup is not explicitly lock-enforcing, and Ruff is installed without a version. Docs build uses bun install without frozen-lock enforcement.
​
**Why it matters:** Changes can reach main without repository-defined test/lint checks. Builds may drift from the checked-in dependency resolutions.
​
**What I changed / how to fix it:** Enabled main/develop push and pull-request triggers with read-only token permissions for test/lint workflows. Tests use uv sync/run --locked; Ruff is pinned to the existing lock version 0.13.1; docs installs use --frozen-lockfile.
​
**What is verified:** Workflow source updated; no GitHub jobs executed and no branch rules changed.
​
**What is still left:** Require these checks through repository branch protection/rulesets. GitHub permissions and actual job behavior must be verified. The binary release pipeline remains separate and unremediated.
​
### F09 - Release dependencies and workflow actions are mutable
​
**Priority:** Medium  
**Where:** `.github/workflows/app.yml:18-35, 59-68; .github/workflows/python-publish.yml:21-37; .github/workflows/vitepress_deploy.yml:21-34; pyproject.toml:17-41` (original archive line numbers)
​
**What was wrong:** Release packaging installs a Git repository without a commit pin and resolves packages from ranges. Most action references use mutable version tags rather than full commit SHAs. Publishing uses a long-lived secret token. Test/lock checks are not release prerequisites.
​
**Why it matters:** A changed upstream dependency or action can alter a release without changes to this repository. Exposure is a supply-chain possibility, not proof of compromise or a confirmed dependency CVE.
​
**What I changed / how to fix it:** No unverified action SHA or upstream commit was invented. This finding is intentionally left open. Verify and pin action SHAs and the extras commit, use locked release dependency inputs, enforce protected release gates, and evaluate PyPI trusted publishing with a protected environment.
​
**What is verified:** OPEN - owner-approved supply-chain changes required.
​
**What is still left:** No live vulnerability database scan, PyPI audit, npm/Bun audit, full Git-history secret scan, SBOM generation, signing or provenance validation was completed. Existing lock hashes do not establish absence of vulnerabilities.
​
## Important behavior changes
​
1. **Custom Python configs no longer run automatically.** Existing custom themes, key bindings and extensions configured this way will not load. The bundled defaults remain.
2. **No normal Python IP networking.** Network-dependent extensions will fail with PermissionError. This is deliberate, but untested here.
3. **Safer stylesheet IDs.** Only letters, numbers, `_` and `-` are allowed; length is 1-128. A duplicate ID no longer overwrites the old stylesheet.
4. **Private storage.** On POSIX systems, the app-owned default data directory is tightened to 0700 and DB files to 0600. Custom DB parent directories must be owned by the current user and not writable by other users. Windows needs ACL checks.
5. **Migration backups are unique.** Backup files include a random suffix. Keep them until a successful restore exercise confirms your data is safe. If migration fails, a new empty DB file may remain; row rollback is not file/schema rollback.
6. **Docs servers are disabled through package scripts.** Documentation builds still work; manually launching VitePress outside these scripts is not blocked.
​
## How to verify before using the changes
​
These are proposed checks, not successful results from this review.
​
1. Extract `dooit-hardened-source.zip` into a new folder. Do not overwrite your only copy.
2. Back up your real Dooit database, old YAML and configuration. Test only against disposable copies first.
3. Install a trusted `uv` tool and use the lockfile:
​
```sh
uv sync --locked
uv run --locked pytest
uv run --locked pytest tests/security/test_hardening.py -q
uv run --locked ruff check .
uv run --locked ruff format --check .
```
​
4. If format-only checks fail, format the candidate in a reviewed branch, inspect the diff, and rerun the checks. No formatter or runtime test was run here.
5. Check normal startup, creating/editing/deleting todos, search, sorting and clipboard support. Use a temporary HOME/XDG config/data/cache environment so real data is untouched.
6. Exercise valid migration, malformed later records, declined overwrite, backup failure, duplicate backup names, and post-commit cleanup failure. Confirm rollback preserves old rows. Restore from both YAML and SQLite backups.
7. Verify the Python guard denies IPv4/IPv6 TCP and UDP sockets and DNS, and verify the actual Dooit process owns no TCP/UDP listeners with your OS tools. Also check spawned processes separately. Do not treat static search as a port scan.
8. Run CI in GitHub. Require the test/lint jobs in branch rules. Review and pin release actions/dependencies with the repository owner.
9. Scan resolved runtime and development dependencies against a current vulnerability database. Review the docs dependency graph separately. Review complete Git history for secrets; rotate any real secret found rather than just deleting it.
10. Upload the missing checklist so every original control can be mapped to evidence, status and remaining work.
​
## Checklist status
​
Because the checklist PDF is missing, the categories below are only a provisional index, not a checklist score:
​
- Code/input safety: targeted patches supplied; runtime verification pending.
- Data privacy: POSIX mode hardening supplied; Windows ACLs/encryption unassessed.
- Backup/recovery: migration source patched; restore testing pending.
- Network exposure: no core listener calls found statically; Python guard added; live/OS checks pending.
- CI quality gates: workflow edits supplied; hosted jobs and branch rules unverified.
- Supply chain: open release-chain issues; CVE audit, SBOM and provenance not completed.
- Secrets: targeted patterns found no match in the reviewed current files outside `.git`; this is not a complete secret scan or proof that no secrets exist.
- Deployment/IAM/monitoring/incident response: no live deployment, account or operational evidence supplied; not assessed.
​
## Files and evidence
​
- `dooit-security-audit.pdf`: designed technical report.
- `dooit-findings-and-fixes.md`: this plain-language explanation.
- `dooit-hardened-source.zip`: candidate modified source, existing tests and new unrun security regression tests; excludes Git history and environment files. Preserves the original license.
- `dooit-hardening.patch`: unified diff for reviewing/applying the code changes against the original working tree.
- `audit-manifest.json`: original archive hash, changed files, source hashes and validation limits.
​
**Source integrity:** Original archive SHA-256: `3d4d177ec4f82ca500937e52c8f215e4dbebd3f6732338715c4146783ab2c8ec`.
​
No runtime pass count or full compliance result is claimed. Original source line references identify the evidence reviewed; line numbers shift in the patched copy.
​
