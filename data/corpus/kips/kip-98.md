---
doc_id: "kip-98"
title: "KIP-98: Exactly Once Delivery and Transactional Messaging"
doc_type: "kip"
source_url: "https://cwiki.apache.org/confluence/display/KAFKA/KIP-98+-+Exactly+Once+Delivery+and+Transactional+Messaging"
kafka_version: "4.0"
source_updated_at: "2024-09-15"
fetched_at: "2026-10-04T05:45:56.507394Z"
content_sha256: "f4eb98b8118a53c43f9fc60319673f8a9376483101926ed846c0b7c5b0adf05f"
token_count: "68"
kip_id: "KIP-98"
status: "Implemented"
released_in:
  - "0.11.0.0"
  - "3.0.0"
affects:
  - "Producer"
  - "Consumer"
  - "Transactions"
---

# KIP-98: Exactly Once Delivery and Transactional Messaging

## KIP-98: Exactly Once Delivery and Transactional Messaging

### Summary & Core Inventions
The foundational proposal introducing idempotent producer sequence numbers, multi-partition transactions, the Transaction Coordinator (`__transaction_state`), transaction control markers (`COMMIT`/`ABORT`), and `read_committed` consumer isolation.
