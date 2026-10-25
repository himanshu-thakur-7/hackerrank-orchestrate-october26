"""Committed transcriptions of the 11 dataset screenshots: facts only, keyed by the sha256 of the PNG bytes.

PROVENANCE
  Source catalogue: docs/02b_DOCS_AND_SCREENS.md §2, written from a first read-by-eye of every PNG
  (no OCR tool installed). Re-verified 2026-10-25 by the coding agent (Claude Code) viewing each of the
  11 PNG files again; every value below was checked against the image (see log.txt, T12 entry).
  No vision API was used: this is a hand transcription, not a model-extraction run. Live, cached
  vision extraction is the second path (T11); this module is what the no-key run uses, so output.csv
  is reproducible without credentials.

Only what the screen shows is recorded. Resource ids that are not printed on screen (object_19,
tombstone_17) are NOT invented; such screens are `units` (record units without a resource id).
State: PRESENT for a record shown; ACTIVE for a connector in continuous sync (status Healthy).
"""

SCREENS = {
    # evidence/images/account_admin_console_20260926.png  Customer Operations -> Haruka Sato
    "d5c32ca5b6e1a2b4bbe9f5d41835ef1fd5d4f7061dab9067a4f9f88cea3c1861": {
        "records": [
            {"region": "header", "resource_id": "account_5762", "system_id": "account_service", "state": "PRESENT",
             "identifiers": ["user_11", "haruka.s1838@zoho.com", "+81 90 7610 2507"], "pii": ["name", "email", "phone"],
             "attrs": {"tier": "Silver", "last_contact": "24 Sep 2026 09:14 JST"}},
            {"region": "customer details", "resource_id": "support_9538", "system_id": "support_platform", "state": "PRESENT",
             "identifiers": ["user_11", "haruka.s1838@zoho.com", "+81 90 7610 2507"], "pii": [],
             "attrs": {"ticket": "CS-8538", "created": "28 Aug"}},
        ],
        "units": [],
    },
    # evidence/images/search_index_inspector_20260901.png  Search Console, query email:g.silva76@gmail.com
    "75afdb0ae53a4510c83399a70d88073cb4fb2747454095756e4ddad1a8c70605": {
        "records": [
            {"region": "results row 1", "resource_id": "search_428", "system_id": "search_service", "state": "PRESENT",
             "identifiers": ["g.silva76@gmail.com", "user_13"], "pii": ["name", "email"],
             "attrs": {"index": "customer_directory_v3", "indexed_at": "2026-09-01T05:58:21Z", "score": "9.84"}},
            {"region": "results row 2", "resource_id": "search_1874", "system_id": "search_service", "state": "PRESENT",
             "identifiers": ["g.silva76.jr@gmail.com"], "pii": ["email"],
             "attrs": {"index": "customer_directory_v3", "score": "4.12"}},
        ],
        "units": [],
    },
    # evidence/images/connector_management_console_20260807.png  BridgeOps -> Connections
    "e81fabc93ea1b5f4c918d934cdb2bea05d61737adfcc29f281494f5d8ec46355": {
        "records": [
            {"region": "topology row 1", "resource_id": "data_flow_1121", "system_id": "integration_service", "state": "ACTIVE",
             "identifiers": ["jain.aditi@gmail.com"], "pii": ["email"],
             "attrs": {"destination": "customer_analytics_warehouse", "mode": "Continuous", "status": "Healthy"}},
            {"region": "topology row 2", "resource_id": "data_flow_9846", "system_id": "integration_service", "state": "ACTIVE",
             "identifiers": ["lucia-torres@gmail.com"], "pii": ["email"],
             "attrs": {"destination": "customer_analytics_warehouse", "mode": "Continuous"}},
        ],
        "units": [],
    },
    # evidence/images/analytics_profile_view_20260713.png  Pulse Analytics -> Omar Darwish
    "4e4cb259bc2010b622b0c53fe5872258f994fefc23452a83bb27473758693484": {
        "records": [
            {"region": "header", "resource_id": "analytics_7438", "system_id": "analytics_platform", "state": "PRESENT",
             "identifiers": ["user_20", "darwish.omar@icloud.com"], "pii": ["name", "email"],
             "attrs": {"last_activity": "13 Jul 2026 14:22 UTC"}},
        ],
        "units": [],
    },
    # evidence/images/customer_export_console_20260618.png  Customer Download Center -> Data exports
    "18b95c1bd8b8956e40216df935498a9f3c181ea2a69b5cd6d3c0841a816d5557": {
        "records": [
            {"region": "exports row 2", "resource_id": "export_1260", "system_id": "export_service", "state": "PRESENT",
             "identifiers": ["ingrid.dahl@outlook.com"], "pii": ["email"],
             "attrs": {"status": "Ready", "created": "2026-06-18T06:42:00Z", "expires": "2026-06-25T06:42:00Z", "download_count": "0"}},
            {"region": "exports row 1", "resource_id": "export_1261", "system_id": "export_service", "state": "PRESENT",
             "identifiers": ["marcus.lee@northstar.shop"], "pii": ["email"], "attrs": {"status": "Collecting"}},
            {"region": "exports row 3", "resource_id": "export_1259", "system_id": "export_service", "state": "PRESENT",
             "identifiers": ["sara.kim@northstar.shop"], "pii": ["email"], "attrs": {"status": "Packaging"}},
            {"region": "exports row 4", "resource_id": "export_1258", "system_id": "export_service", "state": "PRESENT",
             "identifiers": ["daniel.park@northstar.shop"], "pii": ["email"], "attrs": {"status": "Ready"}},
        ],
        "units": [],
    },
    # evidence/images/support_ticket_console_20260524.png  Helpline Console -> CS-5034
    "542b7aec17e6b2f38827896e7eb52c70e4bfaaca22433621be1f80f54884e944": {
        "records": [
            {"region": "header", "resource_id": "support_1034", "system_id": "support_platform", "state": "PRESENT",
             "identifiers": ["kagyeman8947@fastmail.com"], "pii": ["name", "email"],
             "attrs": {"ticket": "CS-5034", "message_excerpt": "Could you let me know where my order is and when it is expected to arrive?",
                       "agent": "Maya Chen", "order": "ORD-20265034"}},
        ],
        "units": [],
    },
    # evidence/images/backup_restore_console_20260429.png  Vault Recovery Manager -> archives (no restore flag shown)
    "2c246aa5843bec609b9ddfdf1154cd81e0fd61996f83954735e9856e48c18bf3": {
        "records": [
            {"region": "archives row 3", "resource_id": "backup_9287", "system_id": "backup_service", "state": "PRESENT",
             "identifiers": ["areed1433@gmail.com"], "pii": ["email"],
             "attrs": {"region": "eu-west-1", "created": "2026-04-26T02:00:00Z", "retention_end": "2026-07-26"}},
            {"region": "archives row 1", "resource_id": "backup_9291", "system_id": "backup_service", "state": "PRESENT",
             "identifiers": ["bluepeakco@outlook.com"], "pii": ["email"], "attrs": {}},
            {"region": "archives row 2", "resource_id": "backup_9288", "system_id": "backup_service", "state": "PRESENT",
             "identifiers": ["miller.logistics@company.com"], "pii": ["email"], "attrs": {}},
            {"region": "archives row 4", "resource_id": "backup_9286", "system_id": "backup_service", "state": "PRESENT",
             "identifiers": ["summit-retail@company.com"], "pii": ["email"], "attrs": {}},
        ],
        "units": [],
    },
    # evidence/images/security_audit_explorer_20260905.png  Sentinel -> Account events, subject filter user_03
    "ca59f693f4e7002466b3fdeaf1bb6763618770963dd811b60003772d07b4b03b": {
        "records": [
            {"region": f"events row {n}", "resource_id": rid, "system_id": "security_service", "state": "PRESENT",
             "identifiers": ["user_03"], "pii": [], "attrs": {"event": ev, "integrity": "Valid"}}
            for n, (rid, ev) in enumerate((("audit_record_003", "Account closure recorded"), ("audit_record_002", "Session revoked"),
                                           ("audit_record_001", "Recovery challenge completed"), ("audit_record_006", "Email change confirmed"),
                                           ("audit_record_005", "Login from new device"), ("audit_record_004", "Password changed")), 1)
        ],
        "units": [],
    },
    # evidence/images/deleted_account_reference_20260310.png  Customer Reference Registry -> user_17 (no tombstone id shown)
    "68c28a72afd6ed184d5990d15c543f8a516face204f0360f732755a8a63c28be": {
        "records": [],
        "units": [{"region": "header", "text": "user_17 Retained reference (Customer key); linked ORD-20263245, CS-3245, CS-3378, "
                                                "FIN-7742; no name, email or phone shown"}],
    },
    # evidence/images/object_storage_browser_20260213.png  Nimbus Object Storage -> support-attachments/2026/02 (no person shown)
    "96e9a191380c29b9e0ab997007268c4cd6353cb6721ebd1ed4a32599d8d37e04": {
        "records": [],
        "units": [{"region": "objects", "text": "delivery_confirmation_19.pdf (684 KB, v3, uploader support-service, modified "
                                                 "2026-02-12T18:42Z), delivery_confirmation_20.pdf, return_label_4821.pdf, return_label_4876.pdf, "
                                                 "invoice_NS-10493.pdf, parcel_damage_7713.jpg, customer_export_2026-02-10.zip, "
                                                 "customer_export_2026-02-12.zip; no person identifier, no object id"}],
    },
    # evidence/images/marketing_profile_console.png  Audience Operations -> Soo-jin Park (no known user)
    "51fa0e6a38f8fa3629ba1b0d0b90b4ed139715956b97bfd09a6f1a6232c15df5": {
        "records": [
            {"region": "header", "resource_id": "marketing_001", "system_id": "marketing_platform", "state": "PRESENT",
             "identifiers": ["sj.park@naver.com", "+82 10-5837-9451"], "pii": ["name", "email", "phone"],
             "attrs": {"status": "Live", "email_opt_in": "yes"}},
        ],
        "units": [],
    },
}
