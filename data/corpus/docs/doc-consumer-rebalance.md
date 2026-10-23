---
doc_id: "doc-consumer-rebalance"
title: "Consumer Group Protocols, Rebalance Algorithms, and KIP-848"
doc_type: "core_docs"
source_url: "https://kafka.apache.org/documentation/#consumer_rebalance"
kafka_version: "4.0"
source_updated_at: "2024-09-01"
fetched_at: "2026-10-04T05:45:56.492989Z"
content_sha256: "4055aaa4fa05e38fef9897bb15d84722e7a1b73d572b4b9cd3250be4d0a08203"
token_count: "725"
---

# Consumer Group Protocols, Rebalance Algorithms, and KIP-848

## 1. Consumer Group Architecture
A Consumer Group is a cooperative pool of consumer instances that collaboratively read from a set of subscribed topics. Partitions are divided among active group members so that each partition is assigned to exactly one consumer within the group at any given time.

The group is managed by the **Group Coordinator**, a broker elected by hashing `group.id` to a partition of the internal `__consumer_offsets` topic.

## 2. Classic Consumer Rebalance Protocol
In the classic protocol (prior to KIP-848), partition assignment is calculated client-side by a designated *Group Leader* consumer:
1. **JoinGroup Phase:** When a consumer starts or group membership changes, all consumers send `JoinGroup` RPCs to the Group Coordinator. The coordinator selects one member as the Group Leader and sends it the metadata of all active consumers.
2. **SyncGroup Phase:** The Group Leader runs the partition assignment strategy algorithm (e.g., `RangeAssignor`, `CooperativeStickyAssignor`) and sends the calculated assignment map to the coordinator in a `SyncGroup` request. Non-leader consumers send empty `SyncGroup` requests. The coordinator responds to each consumer with its assigned partition list.

### Rebalance Assignor Strategies
- **Eager Rebalance (Stop-the-World):** Used by `RangeAssignor` and `RoundRobinAssignor`. When a rebalance occurs, all consumers revoke all assigned partitions simultaneously before receiving new assignments. Data consumption pauses completely across the entire group during the rebalance barrier.
- **Cooperative Sticky Rebalance (`CooperativeStickyAssignor`):** Partitions are migrated incrementally over two consecutive rebalance rounds. Consumers only revoke partitions that are actively moving to another member; consumers holding unaffected partitions continue processing data without downtime.

## 3. Next-Generation Consumer Protocol (KIP-848)
KIP-848 fundamentally re-architects the consumer group protocol in Apache Kafka 4.0 (`group.protocol=consumer`):
- **Server-Side Assignment:** Partition assignment algorithms move from client-side Java code to the broker **Group Coordinator**, eliminating client version discrepancies and simplifying client implementations across C++, Python, Go, and Rust.
- **Incremental Heartbeat Protocol (`ConsumerGroupHeartbeat`):** Consumers no longer undergo heavy `JoinGroup`/`SyncGroup` rebalance barriers. Instead, each consumer sends lightweight periodic heartbeats. The coordinator assigns and revokes partitions incrementally in heartbeat responses.
- **Zero Stop-the-World Downtime:** Adding or removing a consumer only affects the migrating partitions; all other consumers continue uninterrupted streaming.

## 4. Liveness, Timeouts, and Static Membership
- `session.timeout.ms` (default 45s): Maximum duration without heartbeats before the coordinator marks a consumer dead and reassigns its partitions.
- `heartbeat.interval.ms` (default 3s): Frequency of heartbeats sent by the consumer background thread (must be <= 1/3 of `session.timeout.ms`).
- `max.poll.interval.ms` (default 300,000 ms / 5 min): Maximum allowable time between successive `poll()` invocations on the application thread. If data processing takes longer than `max.poll.interval.ms`, the consumer leaves the group to prevent partition starvation.
- **Static Membership (`group.instance.id`):** By assigning a unique static instance ID to a consumer, the coordinator preserves its partition assignment during rolling restarts for up to `session.timeout.ms`, preventing unnecessary rebalances during application deployments.
