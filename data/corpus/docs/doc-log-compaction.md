---
doc_id: "doc-log-compaction"
title: "Log Compaction Internals, Cleaner Threads, and Deduplication"
doc_type: "core_docs"
source_url: "https://kafka.apache.org/documentation/#compaction"
kafka_version: "4.0"
source_updated_at: "2024-09-01"
fetched_at: "2026-10-04T05:45:56.485120Z"
content_sha256: "a1bdd70b871902509f24aa35fa06b71def629ac7b1c58bec80cfcb0bcd2b56c1"
token_count: "814"
---

# Log Compaction Internals, Cleaner Threads, and Deduplication

## 1. Log Compaction Overview
Log compaction is a record retention mechanism where Kafka retains at least the latest known value for each message key within a topic partition log. Instead of discarding records strictly by time or size, compaction preserves the most recent state for each key, providing fine-grained record retention rather than coarse time-based deletion.

Compaction is essential for:
- Reconstructing stateful caches on restart (e.g., Kafka Streams RocksDB changelogs).
- Managing cluster metadata (`__consumer_offsets` and `@metadata` topics).
- Key-value event-sourcing architectures.

## 2. Clean Head vs. Dirty Tail Mechanics
A compacted partition log is divided into two distinct regions:
1. **Clean Head:** The portion of the log that has already been compacted. All keys in the clean head are guaranteed to be unique.
2. **Dirty Tail:** The newly appended segments containing uncompacted records, potentially containing multiple duplicate updates for the same key.
3. **Active Segment:** The currently open segment receiving new writes. The active segment is never compacted until rolled over.

## 3. The Cleaner Thread Algorithm
Background log cleaner threads (`log.cleaner.threads`) execute the compaction process:
1. **Selection:** The cleaner identifies partition logs where the dirty ratio exceeds `min.cleanable.dirty.ratio` (default `0.5` or 50% dirty data).
2. **Phase 1 (Offset Map Build):** The cleaner reads through the dirty tail and builds an in-memory hash table (the *SkimpyOffsetMap*). It maps each 8-byte MD5 key hash to its latest 8-byte logical offset in the dirty tail.
3. **Phase 2 (Log Rewrite):** The cleaner reads both the clean head and dirty tail from beginning to end. For each record:
   - It checks if the record's offset is greater than or equal to the offset in the `SkimpyOffsetMap`.
   - If yes, the record is the latest version and is copied to a new replacement clean segment.
   - If no, a newer version of this key exists later in the log, so the old record is discarded.
4. **Swap:** The replacement cleaned segment is swapped atomically into place, and the old uncompacted segments are deleted.

## 4. Deletes and Tombstones
To delete a key in a compacted topic, a producer writes a record with the target key and a `null` payload, known as a **Tombstone**:
- The tombstone acts as a deletion marker.
- Consumers reading the tombstone recognize that the key has been deleted and remove it from their local state stores.
- The cleaner preserves the tombstone across compactions until `delete.retention.ms` (default: 86,400,000 ms / 24 hours) elapses. This ensures all consumer groups have sufficient time to observe the deletion before the tombstone is permanently garbage-collected from disk.

## 5. Key Configuration Properties
- `log.cleanup.policy`: Set to `compact` or `compact,delete` (combined compaction and time-based retention).
- `min.cleanable.dirty.ratio`: Default `0.5`. Lower values compact more aggressively at the cost of higher I/O; higher values reduce I/O but increase disk space usage.
- `log.cleaner.threads`: Number of background threads dedicated to log cleaning (default: 1).
- `log.cleaner.dedupe.buffer.size`: Total memory allocated across all cleaner threads for offset maps (default: 134,217,728 bytes / 128 MB).
- `delete.retention.ms`: Time to retain deletion tombstones (default: 24 hours).
- `min.compaction.lag.ms`: Minimum time a message remains uncompacted in the dirty tail (default: 0).
- `max.compaction.lag.ms`: Maximum time a message can remain uncompacted in the dirty tail (default: Long.MAX_VALUE).
