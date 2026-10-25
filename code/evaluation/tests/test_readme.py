"""T14: the README in code.zip quotes only commands that exist, and every number it quotes comes
from a real
artifact: the run itself, the loader check, the generated reports, or the measured design
documents."""

import csv
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
README = (ROOT / "README.md").read_text(encoding="utf-8")


def commands():
    return [
        re.split(r"\s+#", l)[0].strip() for l in re.findall(r"^python3 code/\S+.*$", README, re.M)
    ] + re.findall(r"`(python3 code/[^`]+)`", README)


class Commands(unittest.TestCase):
    def test_every_quoted_command_and_flag_parses(self):
        cmds = commands()
        self.assertGreaterEqual(len(cmds), 8)
        for c in cmds:
            argv = c.split()[1:]
            if argv[0] == "code/package.py":  # no argparse; running it builds the zip
                self.assertTrue((ROOT / argv[0]).is_file())
                continue
            p = subprocess.run(
                [sys.executable] + argv + ["--help"], capture_output=True, text=True, cwd=ROOT
            )
            self.assertEqual(p.returncode, 0, f"{c}: {p.stderr[-300:]}")

    def test_every_quoted_path_exists(self):
        sys.path.insert(0, str(ROOT / "code"))
        import package

        published = {name for name, _ in package.docs()}
        for path in set(re.findall(r"`((?:code|docs)/[\w./-]+)`", README)):
            self.assertTrue((ROOT / path).exists() or path in published, path)


class Numbers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = Path(tempfile.mkdtemp()) / "o.csv"
        cls.stdout = subprocess.run(
            [sys.executable, "code/main.py", "--out", str(out)],
            capture_output=True,
            text=True,
            cwd=ROOT,
        ).stdout
        cls.rows = list(csv.DictReader(open(out, newline="", encoding="utf-8")))

    def test_counts_quoted_in_the_readme_match_the_real_run(self):
        self.assertIn(f"({len(self.rows)} rows)", README)
        empty = sum(
            1
            for r in self.rows
            if r["deletion_status"] == "INCOMPLETE" and json.loads(r["steps_json"]) == []
        )
        self.assertIn(f"{empty} eval rows are affected", README)
        tied = int(re.search(r"tied (\d+)", self.stdout).group(1))
        self.assertIn(f"{tied} eval cases have tied account candidates", README)
        adrs = sorted(p.name[:4] for p in (ROOT / "docs" / "adr").glob("0*.md"))
        self.assertIn(f"ADR {adrs[0]}–{adrs[-1]}", README)
        self.assertIn(f"All {len(adrs)} live in `docs/adr/`", README)


def _read(*parts):
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


REPORT = _read("code", "evaluation", "evaluation_report.md")
USAGE = _read("code", "evaluation", "usage_report.md")
SOURCES = (
    REPORT
    + USAGE
    + "".join(
        _read("docs", n)
        for n in ("JEV_SPIKE.md", "JEV_HANDCHECK.md", "02_DATA_NOTES.md", "LOSS_LEDGER.md")
    )
    + "".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "docs" / "adr").glob("0*.md")))
)

# (snippet quoted in the README, document that holds the measured fact, snippet in that document)
DOC_FACTS = [
    (
        "19 of them are near-copies",
        "docs/02_DATA_NOTES.md",
        "19 of the unknown ones are near-copies",
    ),
    ("22 unknown emails", "docs/02_DATA_NOTES.md", "**22 unknown emails**"),
    ("23/23", "docs/adr/0003-account-recovery-from-activity.md", "**23/23**"),
    ("0.75–1.23 h", "docs/adr/0003-account-recovery-from-activity.md", "0.75–1.23 h"),
    (
        "23/32 on samples, with 1 wrong pick",
        "docs/adr/0004-ties-are-unresolved.md",
        "23/32 on samples, but with 1 wrong pick",
    ),
    (
        "about 136–160 account steps",
        "docs/adr/0004-ties-are-unresolved.md",
        "about 136–160 gold-style steps",
    ),
    ("from 19/32 to 21/32", "docs/adr/0002-strict-audit-cutoff.md", "from 19/32 to 21/32"),
    (
        "7 sample cases cite a file captured exactly at the cutoff",
        "docs/adr/0002-strict-audit-cutoff.md",
        "equal in 7 cases",
    ),
    (
        "all 12 such accounts are VERIFY-only",
        "docs/adr/0006-no-evidence-no-complete.md",
        "**12/12** primary accounts",
    ),
    (
        "**7 contradictions**",
        "docs/adr/0014-coverage-is-weak-evidence.md",
        "Fixes the 7 contradictions",
    ),
    (
        "5 from non-empty bundle collections",
        "docs/adr/0014-coverage-is-weak-evidence.md",
        "contradict gold in **5** cases",
    ),
    (
        "4 gold absences that are proven only by omission",
        "docs/adr/0014-coverage-is-weak-evidence.md",
        "loses the 4 gold absences proven only by omission",
    ),
    (
        "8/8 against gold on untagged sample records",
        "docs/adr/0009-support-category-from-activity.md",
        "**agrees with gold 8/8**",
    ),
    (
        "with the explicit tag 31/31 on the tagged records",
        "docs/adr/0009-support-category-from-activity.md",
        "**31/31** agree",
    ),
    (
        "around 5% of an estimated 3,050 gold-style steps",
        "docs/adr/0004-ties-are-unresolved.md",
        "about 5% of about 3,050",
    ),
    (
        "8/8 on the untagged sample support records",
        "docs/adr/0009-support-category-from-activity.md",
        "For 8 of the 9",
    ),
    (
        "cited by 9 different sample cases",
        "docs/adr/0007-one-file-structure-not-a-feature.md",
        "is cited by 9 sample cases",
    ),
    (
        "15 lowest-scored steps were checked by hand against raw evidence: **0 real engine "
        "mistakes**",
        "docs/JEV_HANDCHECK.md",
        "**Result: 0 real engine mistakes out of 15.**",
    ),
    ("varied by 0.090", "docs/JEV_SPIKE.md", "**0.090**"),
    ("max round difference 0.030", "docs/JEV_SPIKE.md", "| 0.030 |"),
    ("Decoy owner +0.12 / +0.16", "docs/JEV_SPIKE.md", "+0.12…+0.20"),
    (
        "1,083 cited eval steps and 62 cited sample steps",
        "docs/BOARD.md",
        "1,083 eval + 62 sample cited steps",
    ),
]


class EveryNumber(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = Path(tempfile.mkdtemp()) / "o.csv"
        run = subprocess.run(
            [sys.executable, "code/main.py", "--out", str(out)],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        cls.stdout = run.stdout
        cls.rows = list(csv.DictReader(open(out, newline="", encoding="utf-8")))
        cls.loaders = subprocess.run(
            [sys.executable, "code/evaluation/main.py", "loaders"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        ).stdout

    def test_status_counts_and_linking_numbers_match_the_run(self):
        from collections import Counter

        c = Counter(r["deletion_status"] for r in self.rows)
        self.assertIn(
            f"COMPLETE {c['COMPLETE']}, INCOMPLETE {c['INCOMPLETE']}, NOT_APPLICABLE "
            f"{c['NOT_APPLICABLE']}",
            README,
        )
        m = re.search(
            r"linked (\d+), tied (\d+) \(UNRESOLVED_LINK\), no candidate (\d+)", self.stdout
        )
        self.assertIn(
            f"{m.group(1)} cases linked, {m.group(2)} tied, {m.group(3)} with no candidate", README
        )
        m = re.search(
            r"intent decisions \((\d+) unique texts\): rules \(clear\) (\d+), cache (\d+)",
            self.stdout,
        )
        self.assertIn(f"{m.group(1)} unique request texts", README)
        self.assertIn(
            f"The rules settle {m.group(2)} of them, and only {m.group(3)} texts need the model",
            README,
        )

    def test_loader_table_matches_the_loader_check(self):
        rows = dict(re.findall(r"^  (\S+)\s+files=\s*(\d+) built\s+obs=\s*\d+", self.loaders, re.M))
        stats = {
            k: tuple(int(x) for x in v)
            for k, *v in re.findall(
                r"^  (\S+)\s+files=\s*(\d+) built\s+obs=\s*(\d+) coverage=\s*(\d+)",
                self.loaders,
                re.M,
            )
        }
        readme = {
            "sql": "SQL snapshots",
            "json:snapshots": "JSON snapshot bundles",
            "json:service_exports": "JSON service exports",
            "json:records": "JSON record lists",
            "log:observability": "Observability logs",
            "log:readback": "Readback logs",
            "log:record_lookup": "Record-lookup logs",
            "txt:handover": "Handover text",
            "pdf": "PDFs",
            "png": "Screenshots",
        }
        self.assertEqual(set(readme), set(rows))
        for kind, label in readme.items():
            line = next(l for l in README.split("\n") if l.startswith("| " + label))
            self.assertTrue(
                line.rstrip().endswith("| " + " | ".join(str(x) for x in stats[kind]) + " |"),
                (kind, line),
            )
        self.assertIn(f"| **Total** | **{sum(int(v) for v in rows.values())}** |", README)
        self.assertIn("unknown signatures: 0", self.loaders)
        m = re.search(r"SQL DRIFT: (\d+) replica-only resources in (\d+) files", self.loaders)
        self.assertIn(
            f"{m.group(1)} records exist only in a replica, across {m.group(2)} files", README
        )
        m = re.search(r"gold-cited pairs: (\d+) checked, (\d+) ok", self.loaders)
        self.assertIn(f"{m.group(1)} checked, {m.group(2)} ok", README)

    def test_metric_and_ledger_tables_equal_the_generated_report(self):
        for line in README.split("\n"):
            m = re.match(
                r"\| "
                r"(status_accuracy|finding_f1|policy_accuracy|evidence_accuracy|strict_step_f1|step_f1_unordered|"
                r"field_acc_mean|sequence_exact|sequence_lcs_mean|proxy) \|",
                line,
            )
            if m:
                self.assertIn(line.strip(), REPORT, line)
        for reason, n in re.findall(
            r"^\| ((?:fully|unresolved|resolved|unlabeled|unproven|contradicted|unknown)[^|]*?) \| "
            r"(\d+) \|",
            README,
            re.M,
        ):
            key = {
                "unlabeled:DELETION_PENDING": "unlabeled:DELETION_PENDING (ADR 0010)",
                "unlabeled:legal hold": "unlabeled:legal hold (ADR 0011)",
                "unlabeled:INCOMPLETE []": "unlabeled:INCOMPLETE [] (ADR 0015)",
            }.get(reason, reason)
            self.assertIn(f"| {key} | {n} |", REPORT, reason)
        self.assertIn("13/13 hold", REPORT)
        self.assertIn("12/12 pass", REPORT)
        self.assertEqual(len(re.findall(r"^\| I\d\.\S+ \| .+ \| 0 \|$", REPORT, re.M)), 9)
        self.assertIn("19/32 exact, 0 wrong", REPORT)
        m = re.search(r"(\d+) steps emitted, ~(\d+) gold-style steps expected missing", REPORT)
        self.assertIn(f"{m.group(1)} steps emitted", README)
        self.assertIn(f"about {m.group(2)} gold-style steps expected missing", README)

    def test_every_decimal_and_dollar_amount_has_a_source(self):
        for x in set(re.findall(r"(?<![\w.])[+]?0\.\d+", README)):
            self.assertIn(x.lstrip("+"), SOURCES, x)
        for x in set(re.findall(r"\$\d+\.\d+", README)):
            self.assertIn(x, USAGE + _read("docs", "JEV_SPIKE.md"), x)
        for x in ("399 calls", "364,270", "20,214", "12 cache hits", "11,450"):
            self.assertIn(x.split()[0], USAGE, x)

    def test_sort_order_claim_is_computed_from_the_dataset(self):
        ids = [
            r["case_id"]
            for r in csv.DictReader(
                open(ROOT / "dataset" / "deletion_requests.csv", newline="", encoding="utf-8")
            )
        ]
        moved = sum(a != b for a, b in zip(ids, sorted(ids), strict=True))
        three = sum(len(i.split("_")[1]) == 3 for i in ids)
        two = sum(len(i.split("_")[1]) == 2 for i in ids)
        self.assertEqual(
            ids, sorted(ids, key=lambda c: int(c.split("_")[1]))
        )  # the input is in numeric order
        self.assertIn(
            f"A lexical sort moves all {moved} ids; the {three} three-digit ids sort ahead of the "
            f"{two} two-digit ones",
            README,
        )
        self.assertEqual(moved, len(ids))

    def test_regime_catalog_and_sample_numbers_are_computed(self):
        from datetime import datetime

        def hours(r):
            t = lambda x: datetime.fromisoformat(x.replace("Z", "+00:00"))  # noqa: E731
            return (t(r["reported_at"]) - t(r["requested_at"])).total_seconds() / 3600

        def rows(name):
            return list(csv.DictReader(open(ROOT / "dataset" / name, newline="", encoding="utf-8")))

        generated = {"case_09"} | {
            f"case_{i}" for i in range(11, 33)
        }  # docs/03_ID_RECOVERY_PROTOTYPE.md §1
        s_n = sum(
            r["case_id"] in generated and hours(r) in (24, 48, 72)
            for r in rows("sample_deletion_requests.csv")
        )
        ev = rows("deletion_requests.csv")
        e_n = sum(hours(r) in (24, 48, 72) for r in ev)
        self.assertEqual(s_n, len(generated))
        self.assertIn(
            f"the {s_n} generated sample cases, case_09 and case_11 to case_32, plus the {e_n} of "
            f"{len(ev)} eval cases",
            README,
        )
        self.assertIn(f"in every one of those {s_n} sample cases", README)
        self.assertIn(
            "samples case_09, case_11 to case_32 (23)", _read("docs", "03_ID_RECOVERY_PROTOTYPE.md")
        )
        out = subprocess.run(
            [sys.executable, "code/evaluation/main.py", "linking"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        ).stdout
        from collections import Counter

        c = Counter(
            re.findall(r"^  activity_\d+ .*?: (CONFIRMED|CONTRADICTED|UNCONFIRMED)", out, re.M)
        )
        self.assertIn(
            f"Of the {sum(c.values())} `LINK_RESOURCE_IDENTITY` rows, the engine's artifact check "
            f"finds "
            f"{c['CONFIRMED']} confirmed, {c['CONTRADICTED']} contradicted, {c['UNCONFIRMED']} "
            f"unconfirmed",
            README,
        )
        gold = list(
            csv.DictReader(
                open(ROOT / "dataset" / "sample_output.csv", newline="", encoding="utf-8")
            )
        )
        n92 = sum(
            any(st["evidence_id"] == "evidence_92" for st in json.loads(r["steps_json"]))
            for r in gold
        )
        self.assertIn(
            f"One evidence file (evidence_92) is cited by {n92} different sample cases", README
        )
        self.assertIn("the other 13 get none", README)
        self.assertEqual(len(gold) - 19, 13)
        sys.path.insert(0, str(ROOT / "code"))
        from evaluation import final, scorer

        self.assertIn(
            f"the equal-weight mean of {'nine' if len(scorer.PROXY) == 9 else len(scorer.PROXY)} "
            f"headline metrics",
            README,
        )
        self.assertIn(f"2 suites × {len(final.matrix_configs())} configurations", README)

    def test_quoted_document_facts_are_in_the_documents(self):
        for readme_snippet, doc, doc_snippet in DOC_FACTS:
            self.assertIn(readme_snippet, README, readme_snippet)
            self.assertIn(doc_snippet, _read(*doc.split("/")), (doc, doc_snippet))

    def test_test_counts_are_current(self):
        loader = unittest.TestLoader()
        solver = loader.discover(
            str(ROOT / "code" / "tests"), top_level_dir=str(ROOT / "code" / "tests")
        ).countTestCases()
        evaluation = loader.discover(
            str(ROOT / "code" / "evaluation" / "tests"), top_level_dir=str(ROOT / "code")
        ).countTestCases()
        self.assertIn(f"{solver} solver tests", README)
        self.assertIn(f"{evaluation} evaluation tests", README)

    def test_structure_toc_and_diagrams(self):
        headings = re.findall(r"^## (\d+)\. ", README, re.M)
        self.assertEqual(headings, [str(i) for i in range(1, 16)])
        self.assertGreaterEqual(README.count("```mermaid"), 3)
        for h in re.findall(r"^## (\d+\. .+)$", README, re.M):
            anchor = "#" + re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-")
            self.assertIn(f"]({anchor})", README, h)


if __name__ == "__main__":
    unittest.main()
