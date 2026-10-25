"""T12 loaders: PDF documents (pdftotext, pypdf fallback) and screenshots (committed transcriptions
keyed by
the PNG's sha256). The real dataset files are used directly: PDFs and PNGs cannot be excerpted
line by line."""

import hashlib
import unittest
from _path import DATA
from ghostaudit import loaders
from ghostaudit.loaders import pdf, screens, screens_data
from ghostaudit.store import Observation

DOCS, IMGS = DATA / "evidence" / "documents", DATA / "evidence" / "images"


def load(path, fid="F1", cap="2026-09-30T12:00:00Z"):
    return loaders.load_bytes(fid, cap, path.read_bytes())


def by_res(r):
    return {o.resource_id: o for o in r.observations}


class Pdf(unittest.TestCase):
    def test_uploaded_attachment_names_its_resource_and_owner(self):
        # evidence_58: support_001, Priya Raman, uploader customer -> SUPPORT_ATTACHMENT content
        # (case_07)
        r = load(DOCS / "delivery_correction_attachment.pdf", "E58", "2026-09-12T07:30:00Z")
        self.assertEqual(r.signature, "pdf")
        self.assertEqual(
            r.observations,
            [
                Observation(
                    "E58",
                    "2026-09-12T07:30:00Z",
                    "support_platform",
                    "support_001",
                    "document",
                    "PRESENT",
                    pii_fields=("name", "email", "phone"),
                    identifiers=("+91 98765 73142", "priya.raman@gmail.com"),
                    locator="text line 2",
                    attrs=(
                        ("file", "delivery_address_correction.pdf"),
                        ("ticket", "CS-4827"),
                        ("uploader", "customer"),
                    ),
                )
            ],
        )

    def test_signed_audit_extract(self):
        o = by_res(load(DOCS / "security_retention_extract.pdf", "E55", "2026-09-05T06:30:00Z"))[
            "audit_record_003"
        ]
        self.assertEqual(
            (
                o.system_id,
                o.state,
                o.identifiers,
                o.pii_fields,
                o.locator,
                dict(o.attrs)["retain_until"],
            ),
            (
                "security_service",
                "PRESENT",
                ("user_03",),
                (),
                "text line 16",
                "25 Aug 2027 04 03 UTC",
            ),
        )

    def test_documents_without_a_resource_id_produce_units_not_observations(self):
        r = load(DOCS / "legal_retention_register_20260529.pdf")
        self.assertEqual(r.observations, [])
        self.assertEqual(len(r.unattributed), 6)  # one per register row, user_08 ... user_29
        self.assertIn("user_08", r.unattributed[0].raw)
        self.assertEqual(r.unattributed[0].reason, "no resource id")
        s = load(DOCS / "account_history_report_20260718.pdf")
        self.assertEqual(
            (s.observations, [u.reason for u in s.unattributed]), ([], ["no resource id"])
        )

    def test_no_text_backend_is_a_hard_error_for_a_pdf_outside_the_committed_cache(self):
        # dataset PDFs come from pdf_text_cache.py (see test_degrade); anything else needs a real
        # backend
        with self.assertRaises(pdf.PdfTextUnavailable):
            pdf.extract_text(b"%PDF-1.4 unknown document", backends=())


class Screens(unittest.TestCase):
    def test_every_dataset_png_has_a_committed_transcription(self):
        hashes = {hashlib.sha256(p.read_bytes()).hexdigest() for p in IMGS.glob("*.png")}
        self.assertEqual(len(hashes), 11)
        self.assertEqual(hashes, set(screens_data.SCREENS))

    def test_unknown_png_is_a_hard_error(self):
        with self.assertRaises(loaders.UnknownSignature):
            loaders.load_bytes(
                "F1", "2026-09-30T12:00:00Z", b"\x89PNG\r\n\x1a\n not a known screen"
            )

    def test_marketing_console_shows_another_person(self):
        # evidence_60: the visible identity is NOT the person activity_4008 claims (ADR 0005)
        o = by_res(load(IMGS / "marketing_profile_console.png", "E60", "2026-09-16T07:20:00Z"))[
            "marketing_001"
        ]
        self.assertEqual(
            o,
            Observation(
                "E60",
                "2026-09-16T07:20:00Z",
                "marketing_platform",
                "marketing_001",
                "screen",
                "PRESENT",
                pii_fields=("name", "email", "phone"),
                identifiers=("+82 10-5837-9451", "sj.park@naver.com"),
                locator="screen header",
                attrs=(("email_opt_in", "yes"), ("status", "Live")),
            ),
        )

    def test_search_console_keeps_the_lookalike_row_separate(self):
        o = by_res(load(IMGS / "search_index_inspector_20260901.png"))
        self.assertEqual(o["search_428"].identifiers, ("g.silva76@gmail.com", "user_13"))
        self.assertEqual(o["search_1874"].identifiers, ("g.silva76.jr@gmail.com",))

    def test_connector_console_flows_are_active(self):
        o = by_res(load(IMGS / "connector_management_console_20260807.png"))
        self.assertEqual(
            {k: (v.state, v.identifiers) for k, v in o.items()},
            {
                "data_flow_1121": ("ACTIVE", ("jain.aditi@gmail.com",)),
                "data_flow_9846": ("ACTIVE", ("lucia-torres@gmail.com",)),
            },
        )

    def test_screens_without_a_resource_id_are_units(self):
        r = load(IMGS / "object_storage_browser_20260213.png")
        self.assertEqual(r.observations, [])
        self.assertIn("delivery_confirmation_19.pdf", r.unattributed[0].raw)
        t = load(IMGS / "deleted_account_reference_20260310.png")
        self.assertEqual((t.observations, "user_17" in t.unattributed[0].raw), ([], True))

    def test_backup_console_shows_no_restore_flag(self):
        o = by_res(load(IMGS / "backup_restore_console_20260429.png"))["backup_9287"]
        self.assertEqual(
            (o.state, o.identifiers, dict(o.attrs)["retention_end"]),
            ("PRESENT", ("areed1433@gmail.com",), "2026-07-26"),
        )


if __name__ == "__main__":
    unittest.main()
