---
doc_id: "config-producer"
title: "Kafka Producer Configuration Reference and Performance Tuning"
doc_type: "config_reference"
source_url: "https://kafka.apache.org/documentation/#producerconfigs"
kafka_version: "4.0"
source_updated_at: "2024-09-01"
fetched_at: "2026-10-04T05:45:56.495764Z"
content_sha256: "e0d36e1b6928035318bea3042938fd28342c6f65874cf3209896bd04643cf5d7"
token_count: "825"
---

# Kafka Producer Configuration Reference and Performance Tuning

## 1. Producer Core Configurations

### `acks`
- **Type:** string | **Default:** `all` (since Kafka 3.0) | **Valid Values:** `[0, 1, all, -1]`
- **`acks=0`:** The producer does not wait for any acknowledgment from the broker. The record is immediately considered sent once written to the network socket buffer. Offers the highest throughput but risks silent data loss if brokers crash.
- **`acks=1`:** The producer waits for acknowledgment from the partition leader broker only. Data is durable against leader failure only after followers replicate it.
- **`acks=all` (or `-1`):** The producer waits for acknowledgment from the partition leader and all currently in-sync replicas (`min.insync.replicas`). Guarantees zero message loss as long as at least `min.insync.replicas` brokers remain online.

### `enable.idempotence`
- **Type:** boolean | **Default:** `true` (since Kafka 3.0)
- When enabled, the producer appends a unique Producer ID (`PID`) and sequence number to each record batch, enabling brokers to deduplicate retried requests.
- **Prerequisites:** Requires `acks=all`, `retries > 0`, and `max.in.flight.requests.per.connection <= 5`.

### `batch.size` & `linger.ms`
- **`batch.size` (Type: int, Default: 16384 bytes / 16 KB):** Maximum byte buffer size allocated for batching records destined for the same partition. Larger batches improve network throughput and compression ratios at the expense of memory.
- **`linger.ms` (Type: long, Default: 0 ms):** Artificial delay introduced on the producer thread to allow additional records to accumulate into a batch before dispatching. Setting `linger.ms=5` to `linger.ms=20` significantly improves batching and throughput with negligible latency impact.

### `compression.type`
- **Type:** string | **Default:** `none` | **Valid Values:** `[none, gzip, snappy, lz4, zstd]`
- Compresses entire record batches. `snappy` and `lz4` offer excellent throughput with low CPU overhead; `zstd` provides the highest compression ratio for text and JSON payloads.

### `buffer.memory` & `max.block.ms`
- **`buffer.memory` (Type: long, Default: 33554432 bytes / 32 MB):** Total memory allocated to the producer `BufferPool` for buffering unsent records.
- **`max.block.ms` (Type: long, Default: 60000 ms / 60s):** Maximum time `KafkaProducer.send()` or `partitionsFor()` will block when the `buffer.memory` is exhausted or metadata is unavailable before throwing `TimeoutException`.

### `max.in.flight.requests.per.connection`
- **Type:** int | **Default:** `5`
- Maximum number of unacknowledged requests sent over a single TCP connection. When idempotence is enabled, values up to `5` maintain strict ordering guarantees.

### `retries` & `retry.backoff.ms` & `delivery.timeout.ms`
- **`retries` (Type: int, Default: 2147483647 / MAX_INT):** Number of automatic retries on transient errors (`NotLeaderOrFollowerException`, `NetworkException`).
- **`retry.backoff.ms` (Type: long, Default: 100 ms):** Initial backoff delay between retry attempts.
- **`delivery.timeout.ms` (Type: int, Default: 120000 ms / 2 min):** Upper bound on the total time between `send()` invocation and successful broker acknowledgment, including all retries.

### `transactional.id`
- **Type:** string | **Default:** `null`
- Unique string identifier required for transactional producers. Enables multi-partition atomic transactions and Exactly-Once Semantics (EOS). Automatically enables `enable.idempotence=true`.
