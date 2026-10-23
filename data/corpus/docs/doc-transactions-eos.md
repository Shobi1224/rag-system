---
doc_id: "doc-transactions-eos"
title: "Exactly-Once Semantics, Idempotent Producers, and Two-Phase Commit"
doc_type: "core_docs"
source_url: "https://kafka.apache.org/documentation/#semantics"
kafka_version: "4.0"
source_updated_at: "2024-09-01"
fetched_at: "2026-10-04T05:45:56.490850Z"
content_sha256: "ad6cedf455de9e64f48456658a8baa31fffbeba3d6a21866499b3a8501e70ed2"
token_count: "964"
---

# Exactly-Once Semantics, Idempotent Producers, and Two-Phase Commit

## 1. Exactly-Once Semantics (EOS) Overview
Apache Kafka delivers end-to-end Exactly-Once Semantics (EOS) across consume-process-produce streaming applications. EOS guarantees that each incoming record is processed exactly once, and output records along with consumer offsets are committed atomically across multiple topic partitions.

EOS is built on two core mechanisms:
1. **Idempotent Producers:** Guarantees zero duplicate writes and strict per-partition message ordering, even across network retries.
2. **Transactional Messaging:** Guarantees atomic multi-partition writes using a two-phase commit protocol coordinated by the Transaction Coordinator.

## 2. Idempotent Producer Mechanics
Enabled by default via `enable.idempotence=true` (since Kafka 3.0):
1. **Producer ID (`PID`):** On startup, the producer sends an `InitProducerId` request to the broker. The broker assigns a globally unique 64-bit Producer ID (`PID`) and initializes `producer_epoch = 0`.
2. **Sequence Numbers:** For each topic partition, the producer assigns monotonically increasing 32-bit sequence numbers (`0, 1, 2...`) to every record batch.
3. **Broker Deduplication:** The partition leader maintains an in-memory cache of the latest 5 sequence numbers received from each `PID`. If a producer retries a produce request due to a transient network error, the broker inspects the sequence number:
   - If `sequence_number == expected_sequence`: The broker accepts and appends the batch.
   - If `sequence_number <= last_seen_sequence`: The broker recognizes a duplicate retry, acknowledges it with `SUCCESS`, but skips writing it to disk.
   - If `sequence_number > expected_sequence + 1`: The broker detects an out-of-order gap and throws an `OutOfOrderSequenceException`.

## 3. Transaction Coordinator & The `__transaction_state` Topic
Multi-partition transactions are managed by the **Transaction Coordinator**, an internal broker component:
- The coordinator broker is determined by hashing the producer's configured `transactional.id` to a partition of the internal compacted topic `__transaction_state` (`Math.abs(transactional_id.hashCode()) % num_partitions`).
- The `__transaction_state` topic persists the lifecycle state machine of each transaction: `Empty` -> `Ongoing` -> `PrepareCommit` / `PrepareAbort` -> `CompleteCommit` / `CompleteAbort`.

## 4. Two-Phase Commit Workflow
When a producer executes a transactional loop:
1. **`initTransactions()`:** Producer registers `transactional.id` with the coordinator. The coordinator increments `producer_epoch`, fencing any older zombie producer instances sharing the same `transactional.id`.
2. **`beginTransaction()`:** Producer transitions local state to `Ongoing`.
3. **`send()` & `AddPartitionsToTxn`:** Before writing to a new partition, the producer registers the topic-partition with the coordinator via `AddPartitionsToTxnRequest`. The coordinator records the partition list in `__transaction_state`. (Optimized server-side in KIP-892).
4. **Produce Records:** Producer sends data record batches with `isTransactional=true`, `PID`, and `producer_epoch` to partition leader brokers.
5. **`sendOffsetsToTransaction()`:** Producer sends committed consumer offsets to the coordinator via `AddOffsetsToTxnRequest` and `TxnOffsetCommitRequest`, linking consumer offsets directly to the active transaction.
6. **`commitTransaction()` (Two-Phase Commit):**
   - **Phase 1 (Prepare):** Coordinator writes a `PREPARE_COMMIT` record to `__transaction_state`. Once replicated, the commit is legally binding.
   - **Phase 2 (Control Markers):** Coordinator broadcasts `WriteTxnMarkersRequest` to all partition leader brokers touched by the transaction. Each leader appends a special control batch (`COMMIT` or `ABORT` marker) to its partition log.
   - **Finalization:** Coordinator writes a `COMPLETE_COMMIT` record to `__transaction_state` and returns `SUCCESS` to the producer.

## 5. Consumer Isolation Levels
Consumers control how they view transactional records via `isolation.level`:
- **`read_uncommitted` (Default):** Returns all messages in offset order, including uncommitted messages and records from aborted transactions.
- **`read_committed`:** Filters out all aborted transaction records. The consumer reads only up to the **Last Stable Offset (LSO)**—the offset of the first unresolved ongoing transaction. If a transaction is ongoing, `read_committed` consumers pause at the LSO until the transaction commits or aborts.
