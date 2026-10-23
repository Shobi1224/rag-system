---
doc_id: "doc-arch-storage"
title: "Kafka Storage Architecture, Record Batches, and Log Segments"
doc_type: "core_docs"
source_url: "https://kafka.apache.org/documentation/#design"
kafka_version: "4.0"
source_updated_at: "2024-09-01"
fetched_at: "2026-10-04T05:45:56.461767Z"
content_sha256: "907be6ce803689c9b45eeb52c17f2e6738771c7bb9c5d2410f2dce03af842645"
token_count: "947"
---

# Kafka Storage Architecture, Record Batches, and Log Segments

## 1. Storage Architecture Overview
Apache Kafka organizes data into topics, where each topic is subdivided into one or more partitions. A partition is the fundamental unit of parallelism, persistence, and ordering in Kafka. Each partition represents an append-only, ordered, immutable sequence of message record batches written sequentially to local disk.

### Zero-Copy Data Transfer
Kafka achieves high network throughput through Linux pagecache and zero-copy data transfer. Instead of maintaining message caches in JVM heap memory, Kafka relies on the operating system OS pagecache. When consumers fetch data:
1. Data is transferred from the OS pagecache directly to the network socket descriptor using the `sendfile()` system call (Java `FileChannel.transferTo()`).
2. This avoids copying data through user-space JVM memory and eliminates JVM garbage collection pauses.

## 2. Physical Log Segment Files
Partitions are divided into multiple log segments on disk. Each segment consists of four primary files located in the broker's data directory (`<topic>-<partition_id>/`):
1. **`.log` (Log Segment File):** Contains raw binary data formatted as Kafka RecordBatches.
2. **`.index` (Offset Index):** A memory-mapped sparse index mapping logical record offsets to physical byte positions within the `.log` file. Entries are written every 4KB (controlled by `index.interval.bytes`).
3. **`.timeindex` (Time Index):** Maps message timestamps to logical record offsets for time-based lookups (`offsetsForTimes()`) and timestamp-based log retention.
4. **`leader-epoch-checkpoint`:** Records the leader epoch and corresponding start offset for each epoch to prevent log truncation divergence during partition leader failovers.

## 3. RecordBatch Memory Layout (Record Format v2)
Since Kafka 0.11.0, records are grouped into `RecordBatch` envelopes with the following binary layout:
- `baseOffset` (8 bytes / Int64): First logical offset in the batch.
- `batchLength` (4 bytes / Int32): Total byte length of the record batch.
- `partitionLeaderEpoch` (4 bytes / Int32): Epoch of the broker leader that wrote the batch.
- `magic` (1 byte / Int8): Record format version (`2` for Kafka 0.11+).
- `crc` (4 bytes / Int32): CRC32-C checksum covering attributes through records.
- `attributes` (2 bytes / Int16): Bit flags:
  - Bits 0-2: Compression codec (`0`: None, `1`: GZIP, `2`: Snappy, `3`: LZ4, `4`: ZSTD).
  - Bit 3: Timestamp type (`0`: CreateTime, `1`: LogAppendTime).
  - Bit 4: Is Transactional (`1` if part of a transaction).
  - Bit 5: Is Control Batch (`1` for `COMMIT` or `ABORT` transaction markers).
- `lastOffsetDelta` (4 bytes / Int32): Offset difference between last record and base offset.
- `baseTimestamp` (8 bytes / Int64): Base timestamp for delta calculations.
- `maxTimestamp` (8 bytes / Int64): Maximum timestamp among all records in the batch.
- `producerId` (8 bytes / Int64): Producer ID (`PID`) assigned for idempotence/transactions.
- `producerEpoch` (2 bytes / Int16): Producer epoch to fence zombie producers.
- `baseSequence` (4 bytes / Int32): First sequence number in the batch.
- `records` (Array): Array of individual variable-length records with key, value, and headers.

## 4. Log Rolling & Retention Policies
Log segments roll over and start a new active segment under the following conditions:
- **Size Roll:** The active segment reaches `segment.bytes` (default: 1,073,741,824 bytes / 1 GB).
- **Time Roll:** The active segment reaches `segment.ms` (default: 604,800,000 ms / 7 days).
- **Index Full:** The `.index` or `.timeindex` reaches `segment.index.bytes` (default: 10,485,760 bytes / 10 MB).

Retention rules discard older inactive segments based on:
- `log.cleanup.policy=delete`: Segments older than `log.retention.hours` (default 168 hours / 7 days) or when partition size exceeds `log.retention.bytes` are marked for deletion and removed after `log.segment.delete.delay.ms` (default 60,000 ms).
