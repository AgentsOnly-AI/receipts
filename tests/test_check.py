# Tests for tools/check.py. Standard library only:
#   python3 -m unittest
# Each fixture is a small sidecar written to a temporary directory, one per
# checker gap listed in PR #2 ("Spec vs checker gaps").

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "tools" / "check.py"
EXAMPLE = ROOT / "examples" / "rounding-toward-alarming" / "report.md.receipts.jsonl"
RAW = b"line one\nline two\nline three\n"

# Every field SPEC v0.2 requires, under the names §4.6 suggests.
V02 = {"schema": "receipts/0.2-draft", "performer": "a@example.test",
       "parties": [{"name": "a@example.test", "did": "wrote", "answers_for": "claim"}],
       "compellable_by": "the reader", "obligation_date": "2026-09-01",
       "measures": "lines in raw.txt", "carried": [], "pointed": ["raw.txt"]}


def receipt(id, supersedes=None, v02=True, **source):
    r = {"id": id, "claim": f"claim {id}", "source": {"uri": "raw.txt", **source},
         "author": "a@example.test", "date": "2026-09-01", "supersedes": supersedes}
    return {**V02, **r} if v02 else r


def run(receipts, *args, raw=RAW):
    """Write a sidecar (list of dicts, or raw text) beside raw.txt and check it."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "raw.txt").write_bytes(raw)
        sidecar = Path(d) / "report.md.receipts.jsonl"
        if isinstance(receipts, str):
            sidecar.write_text(receipts)
        else:
            sidecar.write_text("".join(json.dumps(r) + "\n" for r in receipts))
        return subprocess.run([sys.executable, str(CHECK), str(sidecar), "--today", "2026-09-27", *args],
                              capture_output=True, text=True)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Example(unittest.TestCase):
    """Backward compatibility: the worked example gives the same verdicts as v0.1."""

    def test_example_verdicts_unchanged(self):
        p = subprocess.run([sys.executable, str(CHECK), str(EXAMPLE)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)
        self.assertIn("[  OK   ] r-001", p.stdout)
        self.assertIn("[  OK   ] r-003", p.stdout)
        self.assertIn("[MISSING] r-004", p.stdout)
        self.assertNotIn("r-002", p.stdout)

    def test_example_all_shows_superseded(self):
        p = subprocess.run([sys.executable, str(CHECK), str(EXAMPLE), "--all"], capture_output=True, text=True)
        self.assertIn("[  OK   ] r-002 (superseded)", p.stdout)
        self.assertEqual(p.returncode, 1)


class Gap1Canonical(unittest.TestCase):
    def test_declared_canonical_form_is_never_ok(self):
        p = run([receipt("r-1", sha256=sha(RAW), canonical="nfc-text")])
        self.assertIn("[UNREADABLE] r-1", p.stdout)
        self.assertIn("'nfc-text'", p.stdout)
        self.assertIn("not one this checker can reproduce", p.stdout)
        self.assertEqual(p.returncode, 1)

    def test_absent_canonical_means_raw_bytes(self):
        p = run([receipt("r-1", sha256=sha(RAW))])
        self.assertIn("[  OK   ] r-1", p.stdout)
        self.assertNotIn("diagnostic:", p.stderr)
        self.assertEqual(p.returncode, 0)

    def test_named_raw_bytes_is_ok(self):
        p = run([receipt("r-1", sha256=sha(RAW), canonical="raw-bytes")])
        self.assertIn("[  OK   ] r-1", p.stdout)
        self.assertNotIn("UNREADABLE", p.stdout)
        self.assertEqual(p.returncode, 0)

    def test_all_unreadable_run_is_a_loud_failure(self):
        p = run([receipt("r-1", canonical="nfc-text")])
        self.assertIn("[UNREADABLE] r-1", p.stdout)
        self.assertIn("diagnostic: every checked receipt is UNREADABLE or UNFETCHED", p.stderr)
        self.assertIn("this run read no source and is not a pass", p.stdout)
        self.assertEqual(p.returncode, 1)


class Gap2LineRangeHashing(unittest.TestCase):
    def test_lines_hash_joined_with_newline_no_trailing_newline(self):
        p = run([receipt("r-1", lines="2-3", form_used="lines-utf8-nl",
                         sha256=sha(b"line two\nline three"))])
        self.assertIn("[  OK   ] r-1", p.stdout)
        self.assertIn("raw.txt lines 2-3", p.stdout)
        self.assertIn("form_used=lines-utf8-nl", p.stdout)

    def test_trailing_newline_is_not_part_of_the_region(self):
        p = run([receipt("r-1", lines="2-3", form_used="lines-utf8-nl",
                         sha256=sha(b"line two\nline three\n"))])
        self.assertIn("[CHANGED] r-1", p.stdout)

    def test_line_range_without_named_form_is_unreadable(self):
        p = run([receipt("r-1", lines="2-3", sha256=sha(b"line two\nline three"))])
        self.assertIn("[UNREADABLE] r-1", p.stdout)
        self.assertIn("undeclared form", p.stdout)
        self.assertEqual(p.returncode, 1)

    def test_canonical_may_supply_form_used_when_not_raw_bytes(self):
        p = run([receipt("r-1", lines="2-3", canonical="lines-utf8-nl",
                         sha256=sha(b"line two\nline three"))])
        self.assertIn("[  OK   ] r-1", p.stdout)
        self.assertIn("form_used=lines-utf8-nl", p.stdout)

    def test_hash_matching_only_under_another_form_is_unreadable(self):
        # Named raw-bytes (whole file) but sha256 is the line-range digest.
        p = run([receipt("r-1", lines="2-3", form_used="raw-bytes",
                         sha256=sha(b"line two\nline three"))])
        self.assertIn("[UNREADABLE] r-1", p.stdout)
        self.assertIn("matches under 'lines-utf8-nl'", p.stdout)
        self.assertIn("wrong-form match is not OK", p.stdout)
        self.assertNotIn("[CHANGED]", p.stdout)
        self.assertEqual(p.returncode, 1)

    def test_whole_file_ok_surfaces_form_used_raw_bytes(self):
        p = run([receipt("r-1", sha256=sha(RAW))])
        self.assertIn("[  OK   ] r-1", p.stdout)
        self.assertIn("form_used=raw-bytes", p.stdout)


class Gap3Span(unittest.TestCase):
    def test_span_is_not_applied_and_says_so(self):
        p = run([receipt("r-1", span="5-12", sha256=sha(RAW))])
        self.assertIn("[  OK   ] r-1", p.stdout)
        self.assertIn("span '5-12' not applied", p.stdout)

    def test_span_note_travels_with_a_mismatch(self):
        p = run([receipt("r-1", span="5-12", sha256=sha(b"line"))])
        self.assertIn("[CHANGED] r-1", p.stdout)
        self.assertIn("not applied", p.stdout)


class Gap4RemoteUris(unittest.TestCase):
    def test_url_is_unfetched_not_missing_or_unreadable(self):
        p = run([receipt("r-1", uri="https://example.test/raw.txt")])
        self.assertIn("[UNFETCHED] r-1", p.stdout)
        self.assertNotIn("[UNREADABLE]", p.stdout)
        self.assertNotIn("MISSING", p.stdout)
        self.assertIn("diagnostic: every checked receipt is UNREADABLE or UNFETCHED", p.stderr)
        self.assertIn("not a pass", p.stdout)
        self.assertEqual(p.returncode, 1)

    def test_urn_is_unfetched_not_missing(self):
        p = run([receipt("r-1", uri="urn:example:raw")])
        self.assertIn("[UNFETCHED] r-1", p.stdout)
        self.assertNotIn("[UNREADABLE]", p.stdout)
        self.assertEqual(p.returncode, 1)

    def test_ok_beside_unfetched_is_not_the_all_unreadable_diagnostic(self):
        p = run([receipt("r-1", sha256=sha(RAW)), receipt("r-2", uri="https://example.test/raw.txt")])
        self.assertIn("[  OK   ] r-1", p.stdout)
        self.assertIn("[UNFETCHED] r-2", p.stdout)
        self.assertNotIn("diagnostic:", p.stderr)
        self.assertEqual(p.returncode, 1)

    def test_mixed_unreadable_and_unfetched_is_a_loud_failure(self):
        p = run([receipt("r-1", sha256=sha(RAW), canonical="nfc-text"),
                 receipt("r-2", uri="urn:example:raw")])
        self.assertIn("[UNREADABLE] r-1", p.stdout)
        self.assertIn("[UNFETCHED] r-2", p.stdout)
        self.assertIn("diagnostic: every checked receipt is UNREADABLE or UNFETCHED", p.stderr)
        self.assertNotEqual(p.returncode, 0)


class Gap5SourceUri(unittest.TestCase):
    def test_missing_uri_is_a_schema_error(self):
        r = receipt("r-1")
        del r["source"]["uri"]
        p = run([r])
        self.assertIn("missing required field 'source.uri'", p.stderr)
        self.assertNotIn("MISSING", p.stdout)
        self.assertNotEqual(p.returncode, 0)


class Gap6IdsAndSupersedes(unittest.TestCase):
    def test_duplicate_ids_are_an_error(self):
        p = run([receipt("r-1"), receipt("r-1")])
        self.assertIn("reuses id 'r-1' from line 1", p.stderr)
        self.assertNotEqual(p.returncode, 0)

    def test_supersedes_resolves_chains_in_file_order(self):
        p = run([receipt("r-1"), receipt("r-2", "r-1"), receipt("r-3", "r-2")])
        self.assertIn("3 receipts, 2 superseded, sampling 1", p.stdout)
        self.assertIn("] r-3:", p.stdout)
        self.assertEqual(p.stderr, "")

    def test_supersedes_pointing_later_is_ignored_and_flagged(self):
        p = run([receipt("r-1", "r-2"), receipt("r-2")])
        self.assertIn("r-1 supersedes r-2, which comes later in the file; ignored", p.stderr)
        self.assertIn("0 superseded", p.stdout)

    def test_dangling_supersedes_is_flagged(self):
        p = run([receipt("r-1", "r-9")])
        self.assertIn("warning: r-1 supersedes r-9, which is not in this file", p.stderr)
        self.assertEqual(p.returncode, 0)

    def test_dangling_supersedes_is_an_error_under_strict(self):
        p = run([receipt("r-1", "r-9")], "--strict")
        self.assertIn("error: r-1 supersedes r-9", p.stderr)
        self.assertNotEqual(p.returncode, 0)


class Gap7Sampling(unittest.TestCase):
    RECEIPTS = [receipt(f"r-{i}") for i in range(10)]

    def test_seed_and_method_are_printed(self):
        p = run(self.RECEIPTS, "--sample", "3", "--seed", "42")
        self.assertIn("sample: random.Random(42).sample of 3 from 10 current receipts", p.stdout)
        self.assertIn("from: sidecar sha256 ", p.stdout)
        self.assertIn("checked: 2026-09-27", p.stdout)

    def test_unseeded_sample_prints_a_seed_that_reproduces_it(self):
        first = run(self.RECEIPTS, "--sample", "3")
        seed = first.stdout.split("random.Random(")[1].split(")")[0]
        again = run(self.RECEIPTS, "--sample", "3", "--seed", seed)
        self.assertEqual(first.stdout, again.stdout)

    def test_full_check_says_no_random_draw(self):
        p = run(self.RECEIPTS)
        self.assertIn("sample: all 10 current receipts, no random draw", p.stdout)


class Gap8ReviewBy(unittest.TestCase):
    def reviewed(self, review_by, **kw):
        return {**receipt("r-1", **kw), "review_by": review_by, "review_conditions": "rerun count"}

    def test_past_review_by_is_stale_and_fails(self):
        p = run([self.reviewed("2026-09-26")])
        self.assertIn("[ STALE ] r-1: review_by 2026-09-26 has passed as of 2026-09-27", p.stdout)
        self.assertEqual(p.returncode, 1)

    def test_review_by_today_is_not_stale(self):
        p = run([self.reviewed("2026-09-27")])
        self.assertNotIn("STALE", p.stdout)
        self.assertEqual(p.returncode, 0)

    def test_today_flag_makes_runs_reproducible(self):
        p = run([self.reviewed("2026-10-01")], "--today", "2026-10-02")
        self.assertIn("STALE", p.stdout)

    def test_superseded_receipt_is_not_stale(self):
        p = run([self.reviewed("2026-09-01"), receipt("r-2", "r-1")], "--all")
        self.assertNotIn("STALE", p.stdout)

    def test_bad_review_by_is_an_error(self):
        p = run([self.reviewed("soon")])
        self.assertIn("not a YYYY-MM-DD date", p.stderr)
        self.assertNotEqual(p.returncode, 0)

    def test_review_by_without_conditions_warns(self):
        r = {**receipt("r-1"), "review_by": "2026-12-01"}
        p = run([r])
        self.assertIn("review_by has no review_conditions beside it (§7)", p.stderr)


class Gap9DerivedMarks(unittest.TestCase):
    def read(self, **kw):
        return {**receipt("r-1"), "kind": "read", "subject": "s", "authorizer": "a",
                "reader": "r", "window": "2026-09-01/2026-09-30", **kw}

    def test_unwitnessed_when_witness_absent(self):
        p = run([self.read()])
        self.assertIn("[UNWITNESSED] r-1: read has no witness", p.stdout)
        self.assertIn("no party_registry bound; transitional string-compare", p.stdout)
        self.assertEqual(p.returncode, 1)

    def test_authorizer_cannot_be_witness(self):
        p = run([self.read(witness="a")])
        self.assertIn("the authorizer cannot be the witness", p.stdout)

    def test_distinct_witness_is_not_marked_but_window_is_noted(self):
        p = run([self.read(witness="w-hand")])
        self.assertNotIn("UNWITNESSED", p.stdout)
        self.assertIn("witness window not checked", p.stdout)
        self.assertIn("no party_registry bound; transitional string-compare", p.stdout)
        self.assertEqual(p.returncode, 0)

    def test_subject_who_authorized_needs_no_witness(self):
        p = run([self.read(subject="a")])
        self.assertNotIn("UNWITNESSED", p.stdout)

    def test_report_says_what_it_implements(self):
        p = run([receipt("r-1")])
        self.assertIn("SPEC v0.2-draft subset", p.stdout)


class RegistryBoundWitness(unittest.TestCase):
    """Kama #forge narrowing: witness must resolve in party_registry (§11.3)."""

    def read(self, **kw):
        return {**receipt("r-1"), "kind": "read", "subject": "s", "authorizer": "a",
                "reader": "r", "window": "2026-09-01/2026-09-30",
                "party_registry": "guests.txt", **kw}

    def run_with_registry(self, receipts, guests, *args):
        import tempfile, subprocess, sys, json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "raw.txt").write_bytes(RAW)
            (Path(d) / "guests.txt").write_text(guests)
            sidecar = Path(d) / "report.md.receipts.jsonl"
            sidecar.write_text("".join(json.dumps(r) + "\n" for r in receipts))
            return subprocess.run(
                [sys.executable, str(CHECK), str(sidecar), "--today", "2026-09-27", *args],
                capture_output=True, text=True)

    def test_witness_in_registry_is_not_unwitnessed(self):
        p = self.run_with_registry(
            [self.read(witness="w-hand")],
            "# guest list\ns\na\nr\nw-hand\n")
        self.assertNotIn("UNWITNESSED", p.stdout)
        self.assertIn("witness window not checked", p.stdout)
        self.assertNotIn("transitional string-compare", p.stdout)
        self.assertEqual(p.returncode, 0)

    def test_witness_missing_from_registry_is_unwitnessed(self):
        p = self.run_with_registry(
            [self.read(witness="stranger")],
            "s\na\nr\nw-hand\n")
        self.assertIn("[UNWITNESSED] r-1", p.stdout)
        self.assertIn("does not resolve in party_registry", p.stdout)
        self.assertEqual(p.returncode, 1)

    def test_unreadable_registry_is_unwitnessed(self):
        p = run([self.read(witness="w-hand", party_registry="missing-guests.txt")])
        self.assertIn("[UNWITNESSED] r-1", p.stdout)
        self.assertIn("cannot be read", p.stdout)
        self.assertEqual(p.returncode, 1)

    def test_other_slot_not_in_registry_is_noted_not_a_clear(self):
        p = self.run_with_registry(
            [self.read(witness="w-hand", subject="not-on-list")],
            "a\nr\nw-hand\n")
        self.assertNotIn("[UNWITNESSED]", p.stdout)
        self.assertIn("subject 'not-on-list' not in party_registry", p.stdout)
        self.assertEqual(p.returncode, 0)


class Gap10NewRequiredFields(unittest.TestCase):
    def test_missing_v02_fields_warn_by_default(self):
        p = run([receipt("r-1", v02=False, sha256=sha(RAW))])
        self.assertIn("warning: r-1 (line 1) lacks v0.2 fields: schema (§4.5)", p.stderr)
        self.assertIn("[  OK   ] r-1", p.stdout)
        self.assertEqual(p.returncode, 0)

    def test_missing_v02_fields_are_errors_under_strict(self):
        p = run([receipt("r-1", v02=False)], "--strict")
        self.assertIn("error: r-1 (line 1) lacks v0.2 fields", p.stderr)
        self.assertEqual(p.stdout, "")
        self.assertNotEqual(p.returncode, 0)

    def test_complete_receipt_passes_strict(self):
        p = run([receipt("r-1", sha256=sha(RAW))], "--strict")
        self.assertEqual(p.stderr, "")
        self.assertEqual(p.returncode, 0)

    def test_party_needs_did_and_answers_for(self):
        p = run([{**receipt("r-1"), "parties": [{"name": "a"}]}])
        self.assertIn("each party needs 'did' and 'answers_for'", p.stderr)

    def test_continuity_names_which_sameness(self):
        p = run([{**receipt("r-1"), "continuity": "same"}])
        self.assertIn("continuity must be party, process, or both", p.stderr)


class KindAndDispute(unittest.TestCase):
    def test_subject_and_authorizer_without_kind_is_not_a_read(self):
        r = {**receipt("r-1"), "subject": "s", "authorizer": "a", "reader": "r"}
        p = run([r])
        self.assertNotIn("UNWITNESSED", p.stdout)
        self.assertEqual(p.returncode, 0)

    def test_unknown_kind_warns(self):
        p = run([{**receipt("r-1"), "kind": "invoice"}])
        self.assertIn("kind is not one of the §11 classes", p.stderr)
        self.assertEqual(p.returncode, 0)

    def test_bad_window_warns_and_strict_fails(self):
        r = {**receipt("r-1"), "kind": "read", "subject": "s", "authorizer": "s", "window": "w"}
        warned = run([r])
        self.assertIn("window must be YYYY-MM-DD/YYYY-MM-DD", warned.stderr)
        self.assertEqual(warned.returncode, 0)
        strict = run([r], "--strict")
        self.assertNotEqual(strict.returncode, 0)

    def test_disputed_annotation_is_reported_not_computed_away(self):
        p = run([{**receipt("r-1", sha256=sha(RAW)), "disputed": "claim overreaches the log"}])
        self.assertIn("[  OK   ] r-1", p.stdout)
        self.assertIn("[DISPUTED] r-1: human mark, not computed: claim overreaches the log", p.stdout)
        self.assertEqual(p.returncode, 1)

    def test_disputed_false_is_not_a_mark(self):
        p = run([{**receipt("r-1", sha256=sha(RAW)), "disputed": False}])
        self.assertNotIn("DISPUTED", p.stdout)
        self.assertEqual(p.returncode, 0)

    def test_sampling_warrant_is_on_the_report(self):
        p = run([receipt("r-1", sha256=sha(RAW))])
        self.assertIn("sampling_warrant: this run licenses nothing about receipts it did not read", p.stdout)



if __name__ == "__main__":
    unittest.main()
