---
doc_id: "config-broker"
title: "Kafka Broker Server Configuration Reference and High Availability"
doc_type: "config_reference"
source_url: "https://kafka.apache.org/documentation/#brokerconfigs"
kafka_version: "4.0"
source_updated_at: "2024-09-01"
fetched_at: "2026-10-04T05:45:56.498784Z"
content_sha256: "3eaff0bd162c704bdd35db7386ace28d586e551d1cf8efcb975a43535d73dd32"
token_count: "716"
---

# Kafka Broker Server Configuration Reference and High Availability

## 1. Broker High Availability & Durability Configurations

### `min.insync.replicas`
- **Type:** int | **Default:** `1` | **Production Recommendation:** `2` (when `replication.factor=3`)
- When a producer sends records with `acks=all`, `min.insync.replicas` specifies the minimum number of in-sync replicas (`ISR`) that must acknowledge the write. If the active ISR count drops below this value, the broker rejects producer writes with `NotEnoughReplicasException`, protecting against data loss during broker outages.

### `default.replication.factor` & `num.partitions`
- **`default.replication.factor` (Type: int, Default: 1, Production Recommendation: 3):** Default replication factor for automatically created topics.
- **`num.partitions` (Type: int, Default: 1):** Default number of partitions per auto-created topic.

### `unclean.leader.election.enable`
- **Type:** boolean | **Default:** `false`
- If set to `true`, out-of-sync replicas (replicas outside the ISR) can be elected as partition leader if all ISR members fail. While this prevents topic downtime, it causes silent data loss and log divergence. Keep `false` in production systems.

### `auto.create.topics.enable`
- **Type:** boolean | **Default:** `true` | **Production Recommendation:** `false`
- When `false`, brokers reject metadata requests for non-existent topics, preventing accidental topic creation due to client typos.

## 2. Storage & Retention Configurations
- **`log.retention.hours` (Type: int, Default: 168 hours / 7 days):** Number of hours to retain log segments before deletion.
- **`log.retention.bytes` (Type: long, Default: -1 / unlimited):** Maximum total size of a partition log on disk before older segments are deleted.
- **`log.segment.bytes` (Type: int, Default: 1073741824 bytes / 1 GB):** Maximum size of a single `.log` segment file before rolling over.
- **`log.cleanup.policy` (Type: string, Default: `delete`):** `delete` (time/size retention), `compact` (key-based deduplication), or `compact,delete`.
- **`log.cleaner.threads` (Type: int, Default: 1):** Number of background cleaner threads for log compaction.
- **`min.cleanable.dirty.ratio` (Type: double, Default: 0.5):** Minimum ratio of dirty tail records to total log records required before compaction triggers.

## 3. KRaft Quorum Configurations
- **`process.roles` (Type: list, Default: `[]`):** Roles executed by this JVM: `broker`, `controller`, or `broker,controller`.
- **`node.id` (Type: int, Default: `-1`):** Unique non-negative integer ID identifying the node in the cluster.
- **`controller.quorum.voters` (Type: list):** Voter list in format `<node_id>@<host>:<port>`. Example: `1@ctrl1:9093,2@ctrl2:9093,3@ctrl3:9093`.
- **`controller.listener.names` (Type: string):** Listener name used for Raft controller RPCs (e.g. `CONTROLLER`).
