# 02b — PDF documents and PNG screenshots

This file covers every file in `dataset/evidence/documents/` (4 PDFs) and `dataset/evidence/images/` (11 PNGs).

- PDF text was extracted with `pdftotext -layout`, with trailing whitespace and repeated blank lines squeezed out.
- PNGs were read by eye, because no OCR tool (`tesseract`) is installed. The machine-readable transcriptions are in `scratch/proto_png_transcripts.py`.
- "Capture" is the manifest `captured_at` from `evidence_files.csv`.
- Times shown on screens are partial (no year, or only a time of day) unless stated.

---

## 1. PDFs: full text

### evidence_18 — `account_history_report_20260718.pdf`

Origin `account_history_service`, capture **2026-07-18T11:00:00Z**.

```text
NORTHSTAR SHOP - CUSTOMER STATEMENT
Statement NST-2026-0718-1842

Customer and order
 Record                        Customer Ingrid Dahl
 Detail                        user_18
 Detail                        ingrid.dahl@outlook.com
 Detail                        statement NST-2026-0718-1842
 Detail                        order ORD-20261260
 Item                          Smart desk lamp, SKU LAMP-SD-04, quantity 1, subtotal EUR 54.95, shipping EUR 4.99, tax
                               EUR 11.99, total EUR 71.93
 Record                        Payment Visa ending 4821
 Detail                        billing status paid
 Detail                        order date 08 Jul 2026
 Detail                        dispatched 10 Jul
 Detail                        delivered 14 Jul
NORTHSTAR SHOP - CUSTOMER STATEMENT
Continued - Order timeline and returns

Charges and delivery
 Delivery address               24 Fjordgata, 7010 Trondheim, Norway
 Timeline                       order placed, payment authorised, warehouse packed, carrier collected, delivered
```

| Field | Value |
| --- | --- |
| Identifiers | user_18, ingrid.dahl@outlook.com, name "Ingrid Dahl" (all user_18) |
| References | statement `NST-2026-0718-1842`, order `ORD-20261260` |
| Resource ids | **none** (no `export_N` or other system resource id) |
| Status | billing paid; delivered 14 Jul |

### evidence_58 — `delivery_correction_attachment.pdf`

Origin `support_platform`, capture **2026-09-12T07:30:00Z**.

```text
DELIVERY ADDRESS CORRECTION REQUEST
Support reference CS-4827 / support_001

Customer request
 Record                       Northstar Shop Delivery Address Correction Request
 Detail                       reference CS-4827 / support_001
 Detail                       received 18 Jun 2026
 Detail                       Priya Raman
 Detail                       priya.raman@gmail.com
 Detail                       +91 98765 73142
 Detail                       order ORD-20264827
 Detail                       preferred contact SMS
 submitted 18 Jun 2026 10     24 UTC
 Customer request             change apartment number from 14B to 18B and call before delivery
 Product                      Stainless steel water bottle, quantity 2
 Detail                       carrier SwiftShip
DELIVERY ADDRESS CORRECTION REQUEST
Continued - Attachment properties and upload history

Order and delivery details
 Record                         file delivery_address_correction.pdf
 Detail                         312 KB
 Detail                         ticket CS-4827
 Detail                         region ap-south
 Detail                         uploader customer
 captured 12 Sep 2026 07        30 UTC
 Detail                         checksum prefix c90a42
```

| Field | Value |
| --- | --- |
| Identifiers | name "Priya Raman", priya.raman@gmail.com, phone +91 98765 73142 (all user_07) |
| Resource ids | `support_001` (ticket CS-4827) |
| Status | uploaded by the customer, which makes it a **SUPPORT_ATTACHMENT** (rule_06 DELETE) |
| Times inside | received/submitted 18 Jun 2026 10:24 UTC; the internal "captured 12 Sep 2026 07:30 UTC" matches the manifest |

### evidence_27 — `legal_retention_register_20260529.pdf`

Origin `legal_retention_service`, capture **2026-05-29T08:00:00Z**.

```text
DISPUTED ORDERS AND TAX RECORDS REGISTER
Finance Operations | May 2026

Register details
 Record                         Register month May 2026
 Detail                         owner Finance Records
 Detail                         classification Internal
 generated 29 May 2026 08       00 UTC
 Detail                         For each row add invoice date, finance owner, retain-until date, and case/reference number
DISPUTED ORDERS AND TAX RECORDS REGISTER
Continued - Review and custody notes

Disputed order entries
1     ORD-20264118 | user_08 | Card dispute | 04 May 2026 | USD 184.20 | Retain until 04 May 2033 | AR
2     ORD-20264207 | user_12 | Tax correction | 09 May 2026 | EUR 72.40 | Retain until 09 May 2033 | ML
3     ORD-20264319 | user_17 | Chargeback | 14 May 2026 | GBP 219.00 | Retain until 14 May 2033 | SK
4     ORD-20264402 | user_21 | Invoice inquiry | 18 May 2026 | CAD 96.55 | Retain until 18 May 2033 | AR
5     ORD-20264511 | user_24 | Card dispute | 23 May 2026 | AUD 311.80 | Retain until 23 May 2033 | ML
6     ORD-20264600 | user_29 | Tax record | 28 May 2026 | USD 48.75 | Retain until 28 May 2033 | SK
```

| Field | Value |
| --- | --- |
| Identifiers | user_08, user_12, user_17, user_21, user_24, user_29 |
| Resource ids | **none**; there is no `legal_hold_N`, only order numbers |
| Status | each entry carries "Retain until <date> 2033", a supplied legal-hold basis for rule_13 |

### evidence_55 — `security_retention_extract.pdf`

Origin `security_service`, capture **2026-09-05T06:30:00Z**.

```text
COMPLIANCE JOURNAL - SIGNED RECORD EXTRACT
Reference CJX-20260905-0630

Journal entry
 Record                        Product Northstar Shop Compliance Journal
 Detail                        classification Internal Restricted
 Detail                        reference CJX-20260905-0630
 issued 05 Sep 2026 06         30 UTC
 Record                        Event reference audit_record_003
 Detail                        subject reference user_03
 Detail                        event Account closure recorded
 Detail                        actor automated account workflow
 recorded 25 Aug 2026 04       03 UTC
 retain until 25 Aug 2027 04   03 UTC
 Record                        Journal partition 2026-Q3
 Detail                        record version 1
 Detail                        storage class compliance-ledger
 Detail                        integrity seal valid
 Detail                        short fingerprint 8f0c…31ad
```

| Field | Value |
| --- | --- |
| Identifiers | user_03 |
| Resource ids | `audit_record_003` |
| Status | retained, "retain until 25 Aug 2027", which is the rule_12 retention period; integrity seal valid |

---

## 2. PNGs: description of each screenshot

| file_id / file | Capture | Screen | Visible identifiers | Resource ids | Statuses / notable details |
| --- | --- | --- | --- | --- | --- |
| **evidence_04** `account_admin_console_20260926.png` | 2026-09-26T11:00Z | Customer Operations → customer "Haruka Sato" (Silver) | Haruka Sato, **user_11**, haruka.s1838@zoho.com, +81 90 7610 2507; address 2-18-4 Kichijoji, Musashino, Tokyo | **account_5762**, **support_9538** (CS-8538); orders ORD-20265762, ORD-20265518 | The profile is **live**. "Last contact 24 Sep 2026 09:14 JST"; activity shows 24 Sep "Customer replied to CS-8538", 28 Aug "support_9538 created" |
| **evidence_09** `search_index_inspector_20260901.png` | 2026-09-01T06:00Z | Search Console, query `email:g.silva76@gmail.com`, 2 hits, index customer_directory_v3 / prod-eu | Row 1: Gabriel Silva, g.silva76@gmail.com, **user_13**. Row 2: **g.silva76.jr@gmail.com** (look-alike decoy), no name or ref | **search_428** (score 9.84, indexed 2026-09-01T05:58:21Z); search_1874 (decoy, score 4.12) | Executed 01 Sep 2026 06:00:14 UTC. The activity pane also shows queries `customer_reference:user_9842` (not a real user) and `display_name:"Aditi Jain"` |
| **evidence_14** `connector_management_console_20260807.png` | 2026-08-07T08:00Z | BridgeOps → Connections (PRODUCTION · eu-west · 07 Aug 2026 08:00 UTC) | Selector **jain.aditi@gmail.com** (user_14); selector **lucia-torres@gmail.com** (user_15) | **data_flow_1121** (→ customer_analytics_warehouse, Continuous, status Healthy, last response 200 OK); **data_flow_9846** (→ customer_analytics_warehouse, Continuous); also "Order notifications" and "Delivery tracking" | Both data flows are **active** (continuous sync). This is the ACTIVE_DATA_FLOW signal |
| **evidence_19** `analytics_profile_view_20260713.png` | 2026-07-13T10:00Z | Pulse Analytics → Users → "Omar Darwish" (last 90 days) | Omar Darwish, **user_20**, darwish.omar@icloud.com | **analytics_7438** | The profile is **identifiable**: name, user_id and email are shown. Last activity 13 Jul 2026 14:22 UTC; first seen 21 Apr 2026 |
| **evidence_23** `customer_export_console_20260618.png` | 2026-06-18T12:00Z | Customer Download Center → Data exports (4 jobs) | Owner **ingrid.dahl@outlook.com** (user_18); staff owners marcus.lee@, sara.kim@, daniel.park@northstar.shop | **export_1260** (customer_export_1260.zip, status **Ready**, created 18 Jun 2026 06:42 UTC, **expires 25 Jun 2026 06:42 UTC**, download count 0); export_1261 / 1259 / 1258 (staff) | export_1260 is a ready-to-download customer export, a USER_EXPORT, but it expires 25 Jun |
| **evidence_28** `support_ticket_console_20260524.png` | 2026-05-24T07:00Z | Helpline Console → ticket CS-5034 "Where is my delivery?" | **Kofi Agyeman**, **kagyeman8947@fastmail.com** (user_22); agent **Maya Chen**; order ORD-20265034 | **support_1034** | A conversation with an agent and an order, i.e. shared context, so a **SUPPORT_MESSAGE** (rule_05 REDACT). Expected delivery 26 May 2026 |
| **evidence_32** `backup_restore_console_20260429.png` | 2026-04-29T09:00Z | Vault Recovery Manager → Customer-platform archives | Account **areed1433@gmail.com** (user_16) on backup_9287; other rows bluepeakco@outlook.com, miller.logistics@company.com, summit-retail@company.com (not users) | **backup_9287** (eu-west-1, 84.7 GB, created 26 Apr 2026 02:00 UTC, path s3://northstar-backups/customer-platform/weekly/segment-42-20260426.tar.zst, **retention end 26 Jul 2026**); backup_9291 / 9288 / 9286 | No restore_allowed flag is shown. The activity pane shows "backup_9286 restored · Completed" (25 Apr) and "backup_9281 restored" (24 Apr) |
| **evidence_37** `security_audit_explorer_20260905.png` | 2026-09-05T07:00Z | Sentinel → Account events, subject filter **user_03**, 18–26 Aug 2026 | **user_03** | **audit_record_001 … 006**; detail for **audit_record_003**: event_type account_closure_recorded, actor automated account workflow, recorded_at 2026-08-25T04:03:00Z, signature Valid, journal 2026-Q3 | All 6 events have integrity **Valid**. Matches `evidence_55` (PDF) |
| **evidence_42** `deleted_account_reference_20260310.png` | 2026-03-10T06:00Z | Customer Reference Registry → **user_17**, "Retained reference" | **user_17** only; **no** name, email or phone shown | **No tombstone_N id shown**; linked records ORD-20263245, CS-3245, CS-3378, FIN-7742 (all Active) | The reference was created 11 Jan 2024 08:42 UTC; most recent update 10 Mar 2026 07:18 UTC. This is a **compliant** tombstone view: only the stable reference is shown |
| **evidence_46** `object_storage_browser_20260213.png` | 2026-02-13T08:00Z | Nimbus Object Storage → northstar-customer-data, eu-west-1 / support-attachments / 2026 / 02 (8 objects) | **None**; no person identifier on screen | Files only: **delivery_confirmation_19.pdf** (684 KB, v3, uploader support-service, modified 12 Feb 2026 18:42 UTC), delivery_confirmation_20.pdf, return_label_4821/4876.pdf, invoice_NS-10493.pdf, parcel_damage_7713.jpg, customer_export_2026-02-10.zip, customer_export_2026-02-12.zip | The object is present (a support attachment). The resource id `object_19` is **not** printed on screen |
| **evidence_60** `marketing_profile_console.png` | 2026-09-16T07:20Z | Audience Operations → "Soo-jin Park" (Live) | **Soo-jin Park, sj.park@naver.com, +82 10-5837-9451**, which matches **no** current or historical user | **marketing_001** | The profile is **live**; email opt-in Yes; last refreshed 15 Sep 2026 23:40 UTC |

---

## 3. Which `system_activity` rows link each screenshot or PDF to a person

All 12 `LINK_RESOURCE_IDENTITY` rows come from `data_catalog`, and **each lands exactly 7 minutes after a screenshot or PDF capture**. These rows are claims; the right-hand column checks them against what the image or document actually shows.

| Artifact (capture) | Link row (time) | Claimed link | Does the artifact agree? |
| --- | --- | --- | --- |
| evidence_04 (09-26 11:00) | **activity_4000** (09-26 11:07) | account_5762 → haruka.s1838@zoho.com, user_11 | **Consistent**: the screen shows user_11, account_5762 and haruka.s1838@zoho.com |
| evidence_09 (09-01 06:00) | **activity_4001** (09-01 06:07) | search_428 → g.silva76@gmail.com, user_13 | **Consistent**: row 1 shows search_428, g.silva76@gmail.com, user_13. The .jr decoy (search_1874) is not linked |
| evidence_14 (08-07 08:00) | **activity_4002** (08-07 08:07) | data_flow_1121 → jain.aditi@gmail.com, user_14 | **Consistent** for data_flow_1121. data_flow_9846 (lucia-torres, user_15) is visible but has **no** link row |
| evidence_19 (07-13 10:00) | **activity_4003** (07-13 10:07) | analytics_7438 → darwish.omar@icloud.com, user_20 | **Consistent** |
| evidence_23 (06-18 12:00) | **activity_4004** (06-18 12:07) | export_1260 → ingrid.dahl@outlook.com, user_18 | **Consistent** |
| evidence_28 (05-24 07:00) | **activity_4005** (05-24 07:07) | support_1034 → kagyeman8947@fastmail.com, user_22 | **Consistent** |
| evidence_32 (04-29 09:00) | **activity_4006** (04-29 09:07) | backup_9287 → areed1433@gmail.com, user_16 | **Consistent** |
| evidence_46 (02-13 08:00) | **activity_4007** (02-13 08:07) | object_19 (delivery_confirmation_19.pdf) "belongs only to priya.raman@gmail.com and user_07" | **Unverifiable, not contradicted.** The file name is on screen, but there is no person and no `object_19` id. The person link rests on the claim alone (eval case_61) |
| evidence_60 (09-16 07:20) | **activity_4008** (09-16 07:27) | marketing_001 → kwame-mensah@proton.me, user_09 (Kwame Mensah) | **CONTRADICTED.** The screen shows marketing_001 belonging to "Soo-jin Park, sj.park@naver.com, +82 10-5837-9451", who is not user_09 or any known user. Eval case_63 |
| evidence_18 PDF (07-18 11:00) | **activity_4009** (07-18 11:07) | export_1842 (NST-2026-0718-1842) → ingrid.dahl@outlook.com, user_18 | **Person consistent; resource weakly supported.** The PDF is a *customer statement* NST-2026-0718-1842 for user_18. It never prints `export_1842` and is not an export package; the link maps statement → export through the shared "1842" |
| evidence_37 (09-05 07:00) | **activity_4010** (09-05 07:07) | audit_record_003 → oliver-bennett@gmail.com, user_03 | **Consistent**: the screen shows subject user_03 and audit_record_003. The email is not on screen, but user_03 = Oliver Bennett (`user_identities.csv`). Also backed by evidence_55 (PDF, 06:30) |
| evidence_42 (03-10 06:00) | **activity_4011** (03-10 06:07) | tombstone_17 (user_17) → leonie.g9352@outlook.com, user_17 | **Consistent on user_17.** The screen shows only user_17 and no tombstone id; the `tombstone_17` id comes from the claim |

The PDFs evidence_58 (support_001, Priya Raman) and evidence_27 (legal register: user_08, 12, 17, 21, 24, 29) have **no** link row.

**Summary of contradictions**

- **Contradicted:** 1 (activity_4008 / evidence_60 / case_63).
- **Unverifiable:** 1 (activity_4007 / evidence_46 / case_61).
- **Weakly supported:** 1 (activity_4009 / evidence_18 / case_33: the resource id only).
- **Consistent:** 9.

Under the "never attribute without a grounded link" principle:

- **case_63's marketing_001 must not be attributed to user_09.** The only artifact contradicts the claim.
- **case_61's object_19** rests on an uncorroborated claim and needs a ruling.
