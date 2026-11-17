# Things that broke, and why (keep this updated)

Per the Build Manual, Section 10 rule 6: *"Record failures. A
`docs/failures.md` listing what broke and why is worth marks, and it is the
first thing a good reviewer asks for."*

Nothing is ever deleted from this file.

---

## 1. `field_confidence()` conflated logprobs and raw probabilities

**What broke:** the first version tried to auto-detect whether
`token_logprobs` held natural-log probabilities (real model output, always
<= 0) or already-0..1 confidences (a first pass at adapting Tesseract's word
confidences), by checking whether every value fell in `[0, 1]`. A logprob of
exactly `0.0` means "completely certain" (`exp(0) = 1`), and a probability of
`0.0` means "completely uncertain". The two are indistinguishable at that
value, so a maximally confident real-model input and a maximally
*un*confident local input took the same code path and produced the wrong
score. A fully certain input scored 0.5 instead of 1.0.

**Fix:** stop inferring units. `pipeline/extract.py` converts Tesseract's
0..100 word confidences into log space (`math.log(max(c/100, 1e-6))`) before
they leave the extractor, so `confidence.py` applies one formula
unconditionally regardless of which extractor produced the input.

**Guarded by:** `tests/test_confidence.py::test_field_confidence_all_signals_agree_is_high`,
which asserts 1.0 for an all-agreeing, fully certain input.

---

## 2. `get_second_opinion`'s local fallback ran OCR three times per document

**What broke:** the first draft of the local second-opinion path called
`extract_local_ocr()` twice inside itself, once into an unused variable, on
top of the extraction `extract()` had already done. Three full Tesseract
passes per document. Harmless for a handful of files, but it roughly tripled
the runtime of the 320-document evaluation, which is exactly the kind of
latency problem the `runs` table and the latency column exist to surface.

**Fix:** the local second-opinion path now runs exactly one extra pass,
against a lightly Gaussian-blurred copy of the image. Blurring is a cheap way
to get a *genuinely different* reading rather than a guaranteed-identical
one, which is the point of the agreement signal.

---

## 3. `_find_labeled("total")` silently matched the "Subtotal" line

**What broke:** the first full evaluation run came back with `total_amount`
precision of **7.2%** and, more tellingly, an *inverted* calibration curve:
the 0.9 to 1.0 confidence bin had the worst empirical accuracy in the table.

**Root cause:** `_find_labeled(label)` searched for `label.lower() in
line.lower()`. Searching for `"total"` also matches `"subtotal"`, and
`"Subtotal ..."` is printed above `"Total ..."` on every invoice, so the
search returned the subtotal's value every single time `total_amount` was
looked up. Every invoice's total was wrong in a way that still looked
plausible: a real number, just the wrong field.

**Why the calibration table found it and accuracy would not have:** a model
that is genuinely uncertain spreads its errors across confidence levels. A
deterministic bug produces errors that are systematic *and* confidently
scored, so they pile into the top bin. Confident-and-wrong in a clean
pattern is a bug signature, not a model-quality signature. This is the
concrete case for treating calibration as a debugging instrument and not
only as a reporting metric.

**Also found in the same run:** the dataset's first version rendered invoice
text with PIL's built-in bitmap font, which Tesseract could barely read;
`invoice_number` precision was 1.3%. Not a code bug, just an unrealistically
hard synthetic image. Fixed by rendering with a real TrueType font.

**Fix:** `_find_labeled` matches the label as a whole word (`\btotal\b`),
plus a defensive check that discards `total_amount` when it comes out
numerically identical to `subtotal`, which is the signature of the same line
matching twice. Precision went from 7.2% to 100% and ECE from 0.321 to 0.074
on the regression subset.

**Guarded by:** `tests/test_extract_local_ocr.py::test_total_does_not_capture_the_subtotal_line`.

---

## 4. Docker Hub unreachable in the build sandbox

**What broke:** `docker compose build` and `up` fail immediately.
`registry-1.docker.io` is not on the sandbox's outbound allowlist, so pulling
`python:3.11-slim`, `postgres:16-alpine` and friends returns 403 at the
egress proxy. In the most recent session the Docker *client* is installed but
no daemon is running either, so the path is doubly blocked.

**What was done instead:** every service the compose file would start
(PostgreSQL 16, Redis, the FastAPI app, the Celery worker, the Vite/React
frontend) was installed natively and exercised for real. The full pipeline,
API, review UI, evaluation harness and load test all ran live against those
native services.

**What that does and does not verify:** the application code is the code
that ships, and it is genuinely exercised. What remains unverified is the
container build itself and the compose networking between services. The
compose file is parsed and validated (`docker compose config` succeeds), and
the Dockerfiles are standard, but "it builds on a clean machine" is a claim
this environment cannot make. Run `docker compose up -d --build` on any
normal network to close that gap.

---

## 5. Ollama model registry unreachable, so the real VLM path is unmeasured

**What broke:** `https://ollama.com/install.sh` and
`https://registry.ollama.ai/v2/` both return `403` from the egress proxy
(`CONNECT tunnel failed`). The vision-language extraction path cannot be
installed, let alone run, in this environment.

**Consequence, stated plainly:** every accuracy and calibration number in
`eval/RESULTS.md` comes from the Tesseract OCR path
(`EXTRACTOR_MODE=mock`). The Ollama client in `pipeline/extract.py` is
written to the Build Manual's specification and is switched by one
environment variable, but it has never been executed against a live model
server, so no claim is made about its accuracy or its calibration. The
`vendor_gstin` field, which OCR reads poorly, is the clearest place where
the VLM would be expected to change the result.

**To close it:** on a machine with network access and ~5 GB of free RAM,
`ollama pull qwen2.5vl:7b`, set `EXTRACTOR_MODE=ollama`, and run
`python3 eval/run_eval.py --rebuild`. The harness is extractor-agnostic, so
the comparison is direct.

---

## 6. No real invoices, so the evaluation set is synthetic

**What broke:** nothing technically. This is a scope limitation recorded
here because it is the single largest threat to the validity of every number
this project reports.

The 320-document evaluation set is generated, not collected. It has one
layout family, no logos, stamps, handwriting or multi-column tables, and its
degradations are parametric transformations rather than photographs of
damaged paper. The numbers characterise the *pipeline and its calibration
machinery*, which is what they were built to do. They are not a measurement
of production accuracy on real scanned invoices.

**To close it:** collect 100+ real invoices, type their ground truth by
hand, drop them into `eval/dataset/` in the same two-file format, and re-run
the harness unchanged.

---

## 7. The pinned numpy version could not install on current Python

**What broke:** found by unzipping the delivered project on a clean machine
and installing it exactly as a new user would. `requirements.txt` pinned
`numpy==1.26.4`, which has no prebuilt wheel for Python 3.13 or later. pip
therefore fell back to compiling it from source. That happened to succeed on
the test machine, which has a C toolchain, but it takes minutes and would
fail outright on a typical Windows or macOS machine without build tools.

The project had never caught this because development installed packages
individually rather than from `requirements.txt`, so the pinned file itself
was never exercised end to end.

**Fix:** make the pin conditional on the Python version, so older Python
keeps the tested 1.26.4 and newer Python gets a numpy 2 wheel:

```
numpy==1.26.4; python_version < "3.13"
numpy>=2.1,<3;  python_version >= "3.13"
```

numpy 2 was verified against every other pinned library here (OpenCV, SciPy,
scikit-learn, PyMuPDF, Pillow) before the change was made. Install time on
Python 3.13 went from a multi-minute source build to about seven seconds,
and all 53 tests still pass.

---

## 8. The pinned redis version made every upload fail

**What broke:** the same clean-room install, taken one step further. The API
started, `/health` answered normally, and the first upload returned a 500.
The traceback:

```
kombu.exceptions.VersionMismatch: Redis transport requires redis-py
versions 6.1.0 or later. You have 5.2.1
```

**Root cause:** `requirements.txt` pinned `redis==5.2.1`, but `celery==5.4.0`
depends on kombu with an open upper bound, and a later kombu raised its
redis-py floor to 6.1.0. The pins were mutually consistent when first
written and drifted apart afterwards. Nothing in the project changed; the
dependency ecosystem moved underneath it.

This is worth recording because of where it failed. The health check passed,
the database connected, the worker started without complaint, and the fault
only appeared at the moment the API tried to put a job on the queue. A
smoke test that stopped at "the server starts" would have declared the
system working.

**Fix:** `redis>=6.1,<7`. Re-verified afterwards end to end: upload accepted,
worker picked the job up, document extracted, scored, routed to
`needs_review` with `vendor_gstin` flagged, and a run row written with
duration, page count, token count and cost.

**Lesson, written down because it generalises:** pinning some dependencies
and leaving their transitive dependencies to float is not reproducibility.
A pinned file that is never installed from is not a tested file.

---

## 9. The project cannot be installed on Python 3.14

**What broke:** a teammate following `SETUP.md` on Windows hit
`Error: pg_config executable not found` while installing dependencies. The
immediate cause was `psycopg2-binary==2.9.10`, which publishes Windows
builds for Python 3.9 through 3.13 only, so pip fell back to compiling it
from source and stopped for want of PostgreSQL's build tools.

**The real problem was larger than that one package.** Checking the wheel
coverage of every pinned dependency showed that on Python 3.14:

| Package | Windows build for 3.14 |
|---|---|
| psycopg2-binary | only from 2.9.11 |
| numpy | only from 2.3.2 |
| scipy | only from 1.16.1 |
| scikit-learn | only from 1.7.2 |
| pillow | only from 11.3.0 |
| **opencv-python-headless** | **none at any version** |
| **pymupdf** | **none at any version** |

OpenCV does every image operation in `pipeline/preprocess.py` and PyMuPDF
turns PDFs into images. Neither is optional, and neither can realistically
be compiled from source on a student laptop. So Python 3.14 is not a pinning
problem to be solved, it is a version the project cannot run on until those
two projects publish builds for it.

**Fix:** `SETUP.md` now states Python 3.11, 3.12 or 3.13 explicitly, warns
against 3.14 by name, explains the symptom so it is recognisable, and shows
how to select an older interpreter with the `py` launcher without
uninstalling anything.

**Lesson:** "3.11 or newer" was the wrong way to write a version
requirement. The tested range has an upper bound as well as a lower one, and
leaving the top open quietly promised support for interpreters the
dependencies had never been built for.

---

## 10. The invoice number parser matched the word "Invoice" itself

**What broke:** a teammate ran the test suite on Windows and got one
failure that had never appeared on the development machine:

```
assert invoice.invoice_number == "INV-9001"
AssertionError: assert 'oice' == 'INV-9001'
```

**Root cause.** The pattern was a single alternation:

```python
r"(?:Invoice\s*#|Invoice\s*No\.?|INV[-\s]?)\s*[:\-]?\s*([A-Z0-9\-]+)"
```

with `re.IGNORECASE`. The third branch, `INV[-\s]?`, happily matches the
first three letters of the word **Invoice**. Normally it never gets the
chance, because the second branch consumes "Invoice No" first. But her
Tesseract read the label as something slightly different, perhaps "Ne" or
"N0". Both earlier branches then failed, the third matched the "Inv" of
"Invoice", and the capture group took the remaining letters: `oice`.

Reproduced directly against the regex, with no OCR involved:

| Input text | Old result |
|---|---|
| `Invoice No: INV-9001` | `INV-9001` |
| `Invoice Ne: INV-9001` | `oice` |
| `Invoice N0: INV-9001` | `oice` |
| `INV-9001` | `9001` |

The last row is a second, quieter bug found while investigating the first:
a bare invoice code with no label silently lost its `INV-` prefix, because
the branch consumed the prefix before the capture group began.

**Why it never showed up here.** The development machine's Tesseract read
the label correctly every time, so the faulty branch was never reached. The
bug was latent, and an identical codebase passed on one machine and failed
on another. Every reported number was still correct, because the evaluation
set does get the label read correctly, but the parser was one OCR wobble
away from returning nonsense with high confidence.

**Fix.** Two patterns applied in order, in `find_invoice_number()`. First a
code that stands on its own, `\bINV[-\s]?\d[A-Z0-9\-/]*`, where requiring a
digit immediately after `INV` makes it structurally impossible to match the
word "Invoice". Then, for documents not using an INV prefix, whatever
follows an invoice-number label, with the capture required to contain a
digit so the word "invoice" in ordinary prose cannot yield a number.

**Fix to the test, which was also at fault.** The failing test asserted an
exact character-level OCR reading, so it was really testing the local
Tesseract build rather than the project. It now asserts only what the
parser is responsible for, and twelve new tests pin the parsing rules
deterministically with fixed strings and no OCR, including every misread
label above. The suite went from 53 tests to 65.

**Lesson:** a test that depends on a third-party binary reading an image
perfectly is a test that passes or fails by luck of the machine. Pin the
logic you own with deterministic inputs, and let the end to end test check
only that the pieces are wired together.

---

## 11. The Windows font fallback silently rendered unreadable pages

**What broke:** after the section 10 fix, the same teammate's Windows run
still had one failing test, now on a different field:

```
assert invoice.invoice_date.isoformat() == "2025-06-15"
AssertionError: assert '2025-08-15' == '2025-06-15'
```

A 6 read as an 8. That looks like ordinary OCR noise, and it is, but the
reason it happened on her machine and never here is not ordinary.

**Root cause.** Both the test and `eval/generate_dataset.py` rendered their
pages with this helper:

```python
for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", ...):
    ...
return ImageFont.load_default()
```

Those paths exist only on Linux. On Windows and macOS every candidate fails
and the function returns PIL's built-in bitmap font: tiny, low resolution,
and exactly the font that section 3 of this file already records as the
cause of `invoice_number` precision dropping to 1.3 percent. The earlier fix
named a real font but only for one operating system, so the same defect
survived on every other platform, hidden behind a silent fallback.

**Why this was worse than a failing test.** The test failure was the
harmless symptom. `eval/generate_dataset.py` shared the helper, so anyone
generating the evaluation set on Windows or macOS would have produced 320
documents in an unreadable font, run the full twenty minute evaluation
against them, and received a complete set of precision, calibration and
automation figures that looked entirely normal and meant nothing. Nothing
would have crashed or warned.

**Fix.** `backend/textfont.py` searches the standard font directories of
Windows, macOS and Linux, and **raises by default** instead of returning the
bitmap font, with a message naming the problem and how to install a font.
`generate_dataset.py` now also prints which font it rendered with, so two
machines reporting different numbers can be compared directly. The test
assertions were loosened to what the parser is responsible for, with eight
further deterministic tests pinning the date and money patterns against
fixed strings. The suite is now 73 tests.

**Lesson:** a silent fallback to a degraded mode is worse than a crash,
because the degraded mode still produces output that looks like a result.
If a fallback would invalidate every number downstream, it should not be a
fallback at all.
