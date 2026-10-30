# PBIPDocumenter — independent full-product code review

**Review date:** 2026-10-30
**Reviewed baseline:** `main` at `619d2e2` (after schema-layout PR #29)
**Review branch:** `review/full-product-20261030`
**Scope:** local PBIP/PBIR/TMDL extraction, TMDL parser, document content and native DrawingML, CLI, optional Jira/Power BI inventory, SharePoint download/cache, augmentation, product packaging, release workflow, automated verification, trust boundaries and failure handling
**Authoritative execution:** GitHub-hosted CI and rendered output. Local Zephyrus runs are used for read-only investigation and fault reproduction.

## Executive decision

**Core use case: functional and independently source-checked on the public Contoso example. Product-wide production assurance: NOT YET APPROVED.**

The public installed-wheel DOCX generation, model/page inventories, native editable Word diagrams and LibreOffice rendering gates work for the known synthetic Contoso fixture. The review found material failure/safety cases that existing CI did not cover. The highest-impact defects have been repaired in the associated PR. Several broader product-readiness risks remain open and should **not** be represented as resolved.

This is a product-wide, risk-based code review across all major subsystems. It is **not** a claim that every possible TMDL syntax, private Power BI project, authentication topology or Microsoft Word build has been exhaustively exercised.

## Tested baseline

- Repository: ~86 Python files / ~17,171 lines of Python, including tests, utilities and scripts.
- Existing `113` tests passed locally; Ruff and strict mypy passed.
- Existing package-only `--cov=pbip_documenter` baseline: **68% statement coverage (6,434 statements, 2,073 missed)**. This excludes the `copiloter.py` extractor module (2,510 lines), so it **overstates end-to-end extraction coverage**.
- Largest baseline coverage gaps: `services/document_service.py` **47%**, `docx_render/wireframe.py` **51%**, optional `downloads/service.py` **21%**, Power BI/Jira HTTP clients roughly **21–31%**, and augmentation service **0%**. Coverage is a map of untested paths, not an assertion that every missed line is defective.
- Reviewed existing `ci.yml`, `schema-layout-review.yml` and `release.yml`; CI currently builds/validates the installed wheel and Contoso source-fidelity and PDF geometry, but **does not establish general model compatibility or Microsoft Word-exact layout**.

## Verified defects corrected in review PR

| ID | Priority | Finding & direct evidence | Implemented correction | Verification |
|:--|:--|:--|:--|:--|
| FIX-01 | P1 | An existing PBIR `visual.json` containing malformed JSON was silently omitted. The public CLI returned exit **0** and produced output based on an incomplete visual count. `copiloter.py` swallowed JSON errors; `cli.py` only checked project structure. | Existing malformed/missing page or visual definition is explicitly surfaced as an extraction error; CLI refuses to report a successful DOCX for affected projects. | Disposable standalone PBIR fault fixtures, valid-PBIR control |
| FIX-02 | P1 | `--output` identical to `--template` replaced the user's editable Word template. Confirmed with a disposable template. | Reject template/output path collisions before document rendering. | Preserved source bytes; no build call |
| FIX-03 | P1 | Save errors could partially replace an existing valid output. | Generate a temporary DOCX in the destination directory and publish with `os.replace`, cleaning temporary files after errors. | Injected interrupted save; previous file remains unchanged |
| FIX-04 | P1/privacy | A live PBIR `connectionString` was copied wholesale into exportable structured summaries. Such strings may contain credentials. | Omit raw connection strings from exported report metadata; preserve non-secret `data_source`, `catalog`, and model-reference fields. | Synthetic `Password`/`Access Token` canaries absent from serialized summaries |
| FIX-05 | P1/security | The Power BI Admin API client sent its bearer token to server-supplied `@odata.nextLink` destinations without verifying scheme/host/service path. | Permit only HTTPS continuation URLs on the same Power BI Admin API host and path; reject malicious or malformed destinations before the next request. | Mocked adversarial continuation URLs; verified only the original host was contacted |
| FIX-06 | P2 | An incompletely downloading browser file could remain in the stabilization loop indefinitely, ignoring the configured total download timeout. | Pass a shared monotonic deadline into the stabilization loop and raise `TimeoutError`. | Simulated stuck `.crdownload` and advancing clock |
| FIX-07 | P2/security | A download cache name containing `..` could escape the configured cache root and overwrite unrelated files. | Resolve and restrict cache output to the configured cache directory; reject untrusted cache paths. | Traversal/absolute-path tests and valid-cache control |
| FIX-08 | P2 | Power BI and Jira pagination could loop on repeated continuation links/tokens. Power BI also assumed all API result payloads were objects. | Detect repeat continuation links/tokens and support list responses where valid. | Repeated-page and mixed object/list response tests |
| FIX-09 | P2 | Word portrait header/footer references were stored in module-global state and could leak from one generated DOCX to another. | Derive and restore original references from the current document on each landscape→portrait transition. | Consecutive DOCX builds with/without headers; no cross-document inheritance |

These fixes are deliberately narrow. They do not alter semantic-model relationship topology, diagram scoring, native DrawingML output, user PBIP sources or the approved Contoso fixture.

## Open findings requiring separate acceptance

| ID | Priority | Observation / source evidence | Suggested acceptance |
|:--|:--|:--|:--|
| OPEN-01 | P1 release | `.github/workflows/release.yml` publishes on `v*` tag pushes, independently of the full CI/Word-render gates. There is no explicit gated release decision or product acceptance check in that workflow. No PyPI distribution was verified in the previous public-repo audit. | Protect tag/release authority; ensure full matrix, supply-chain checks and installed-wheel/Word output pass for the **same tagged commit** before any publish. Do not trigger publish until validated. |
| OPEN-02 | P1 source fidelity | Most parser workflows rely on permissive `safe_read_text`/`safe_read_json`; malformed or missing TMDL sections may become partial summaries without a strict source-integrity result. The new fail-closed handling covers existing invalid PBIR pages/visuals, **not all TMDL syntax/structural failures**. | Introduce a parse diagnostics ledger (file, severity, parser mode, object count), strict/lenient CLI mode, TMDL boundary fixtures and mutation/fuzz-style tests. |
| OPEN-03 | P1 QA breadth | Core full Word generation and PBIR wireframes have low path coverage (47% and 51%), while `copiloter.py` is not included in the headline 68% coverage. Source-to-Word regression uses one primary Contoso fixture. | Add diverse PBIP fixtures for live connections, calculated tables, RLS, UDFs, composite/direct-query, bookmarks, custom visuals, malformed inputs and no-template mode; capture exact native Word and LibreOffice pages. |
| OPEN-04 | P2 feature truth | `augmentation/service.py::_try_generate_with_ai` always returns `None` despite AI provider/model configuration. Deterministic fallback is available; actual external AI augmentation is not currently implemented. | Either remove/disable misleading configuration and document fallback-only status, or implement and independently verify opt-in AI calls, redaction and provenance. |
| OPEN-05 | P2 optional legacy helper | `docx_render/msip.py` is an untested exported helper containing placeholder label identifiers, archive rewriting and permissive exception handling. It has no observed active core call path. | Decide whether to remove it or provide a valid, atomic, contract-tested implementation. Do not promise MIP labeling support before official validation. |
| OPEN-06 | P2 usability | `cli.py` silently falls back to scratch document generation when an explicitly requested `--template` is missing; invalid explicit inputs should generally fail instead of being ignored. | Explicit-template validation and user-facing diagnostics, with regression tests. |
| OPEN-07 | P2 provenance | Showcase checking compares the source fixture Git tree and image hashes, but does not prove the screenshots remain current when the renderer/source code changes without modifying the fixture. | Bind galleries to exact generator commit/build artifact and alert/regenerate on output-affecting code changes. |
| OPEN-08 | P2 security and privacy | Optional Jira/Power BI cache and browser-download flows involve credentials and potentially sensitive enterprise metadata; HTTP/service/cache branches have little direct test coverage. | Test auth refresh, retries/throttle, pagination limits, cache poisoning, retention/permissions, redaction, and error handling using mocked APIs and ephemeral test roots. |
| OPEN-09 | P2 maintainability | The core document writer contains one roughly 940-line `build_doc` function; `wireframe.py::insert_page_layout` and `copiloter.py` similarly combine parsing, layout and business/narrative concerns. | Refactor behind behavior-preserving golden-document acceptance once source coverage is increased; avoid cosmetic file splitting that risks content regressions. |

## Subsystem assessment

| Subsystem | Baseline result | Residual risk |
|:--|:--|:--|
| PBIP discovery and CLI | Public fixture works; newly corrected fail-closed paths and atomic output | More malformed file/exception boundaries and argument validation needed |
| TMDL/semantic model | Contoso tables/measures/relationships source checked | Many syntax/version/edge cases not sampled |
| PBIR reports | Contoso page inventory and 54 visuals source checked | Visual-specific metadata, custom objects, malformed/empty group structures |
| Word/DrawingML | Native editable diagrams verified; source-to-DOCX and PDF gates | Microsoft Word pagination/rendering differences; complex header/template scenarios |
| Analytical observations | Functional for sampled report | Generic scenarios should remain clearly separated from verified project facts |
| Optional AI | Deterministic fallback functions | Configured AI generation is a no-op |
| Inventory/matching | Scoring and normalization tests strong | HTTP/auth/pagination and cache refresh coverage weak |
| Browser downloads | Windows-only; timeout/path safety fixed | Browser attribution, auth/session management, shared-folder interference |
| Packaging and release | Installed-wheel CI checks green | Release tag workflow not bound to full acceptance gates |
| Security/privacy | No dynamic code execution or `shell=True` was found in inspected execution paths; additional explicit privacy/network protections added | Not a formal penetration test or complete dependency-vulnerability scan |

## Validation criteria for merging the fixes

1. Local fault-probe and targeted regression suite (all synthetic/test-only data).
2. Full Python unit suite + Ruff + mypy on Linux Python 3.10–3.13 via public GitHub runners.
3. Installed-wheel source-to-DOCX test with native DrawingML assertions.
4. Real DOCX→PDF page geometry and source fidelity acceptance using the public Contoso.
5. No package publishing and no changes to private/local Contoso work.
6. Any red CI gate must be repaired and rerun before merge.

## Decision and next priorities

**Recommended decision:** Merge the narrow fail-safe/privacy/network fixes only after all green gates. Keep unrestricted product-production certification **open** until OPEN-01, OPEN-02 and OPEN-03 have independent acceptance. Avoid expanding VQS scope; VQS is not part of this document-generation release gate.

Most valuable next wave: **(1) strict source fidelity beyond PBIR JSON, (2) actual release gating for tagged artifacts, (3) more representative fixtures and Word layout coverage**, then the optional AI and legacy helper decisions.

This report records source-derived findings, local reproducible probes, and outstanding risks. It intentionally does not claim that untested integrations or semantic-model variants were verified.
