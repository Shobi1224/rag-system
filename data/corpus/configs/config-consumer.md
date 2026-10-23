---
doc_id: "config-consumer"
title: "Kafka Consumer Configuration Reference and Group Management"
doc_type: "config_reference"
source_url: "https://kafka.apache.org/documentation/#consumerconfigs"
kafka_version: "4.0"
source_updated_at: "2024-09-01"
fetched_at: "2026-10-04T05:45:56.497363Z"
content_sha256: "c244330ec7a407097572f91af592b7215cd0a2d2e1c47ca58901e4749af9e392"
token_count: "879"
---

# Kafka Consumer Configuration Reference and Group Management

## 1. Consumer Core Configurations

### `group.id`
- **Type:** string | **Default:** `null`
- Unique identifier of the consumer group this consumer joins. All consumers with the same `group.id` share topic partition assignments.

### `auto.offset.reset`
- **Type:** string | **Default:** `latest` | **Valid Values:** `[latest, earliest, none]`
- **`latest`:** Automatically reset consumer offset to the latest log end offset (`LEO`) if no initial offset exists or if stored offset is out of range.
- **`earliest`:** Reset consumer offset to the earliest available offset (log start offset) in the partition.
- **`none`:** Throw `OffsetOutOfRangeException` if no previous offset is found for the group.

### `enable.auto.commit` & `auto.commit.interval.ms`
- **`enable.auto.commit` (Type: boolean, Default: `true`):** When `true`, consumer offsets are periodically committed in the background during `poll()`. For at-least-once or transactional processing, set to `false` and commit offsets manually via `commitSync()` or `commitAsync()`.
- **`auto.commit.interval.ms` (Type: int, Default: 5000 ms / 5s):** Frequency of background automatic offset commits.

### `session.timeout.ms` & `heartbeat.interval.ms`
- **`session.timeout.ms` (Type: int, Default: 45000 ms / 45s):** Timeout used by the broker Group Coordinator to detect consumer failure. If no heartbeat is received within this duration, the consumer is evicted from the group and a rebalance is triggered.
- **`heartbeat.interval.ms` (Type: int, Default: 3000 ms / 3s):** Frequency of heartbeat signals sent by the consumer background thread. Must not exceed 1/3 of `session.timeout.ms`.

### `max.poll.interval.ms` & `max.poll.records`
- **`max.poll.interval.ms` (Type: int, Default: 300000 ms / 5 min):** Maximum allowable time between successive `poll()` calls on the application thread. If processing a batch takes longer than this interval, the consumer is assumed hung and leaves the group.
- **`max.poll.records` (Type: int, Default: 500):** Maximum number of records returned in a single `poll()` call. Tuning this prevents exceeding `max.poll.interval.ms`.

### `fetch.min.bytes`, `fetch.max.wait.ms`, `fetch.max.bytes`
- **`fetch.min.bytes` (Type: int, Default: 1 byte):** Minimum data bytes the broker must accumulate before responding to a fetch request. Increasing this (e.g., to 100KB) improves throughput at the expense of latency.
- **`fetch.max.wait.ms` (Type: int, Default: 500 ms):** Maximum time the broker will block waiting for `fetch.min.bytes` to accumulate before returning.
- **`fetch.max.bytes` (Type: int, Default: 52428800 bytes / 50 MB):** Maximum total data returned across all partitions in a single fetch response.

### `isolation.level`
- **Type:** string | **Default:** `read_uncommitted` | **Valid Values:** `[read_uncommitted, read_committed]`
- **`read_uncommitted`:** Returns all records including uncommitted and aborted transactional messages.
- **`read_committed`:** Filters out aborted transactional batches and blocks consumption past ongoing transactional Last Stable Offsets (LSO).

### `partition.assignment.strategy`
- **Type:** list | **Default:** `[org.apache.kafka.clients.consumer.RangeAssignor, org.apache.kafka.clients.consumer.CooperativeStickyAssignor]`
- Supported strategies: `CooperativeStickyAssignor` (recommended for classic rebalancing), `RangeAssignor`, `RoundRobinAssignor`, `StickyAssignor`.

### `group.protocol` (KIP-848)
- **Type:** string | **Default:** `classic` (in 3.x), `consumer` (in 4.0) | **Valid Values:** `[classic, consumer]`
- Enables the KIP-848 Next-Generation server-side consumer rebalancing protocol.
