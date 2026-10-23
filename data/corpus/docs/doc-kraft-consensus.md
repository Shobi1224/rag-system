---
doc_id: "doc-kraft-consensus"
title: "KRaft Consensus, Metadata Quorum, and Controller Architecture"
doc_type: "core_docs"
source_url: "https://kafka.apache.org/documentation/#kraft"
kafka_version: "4.0"
source_updated_at: "2024-09-01"
fetched_at: "2026-10-04T05:45:56.488459Z"
content_sha256: "e3161d761e514cb7fdc6e91ff6b6a6bf87bca8b92d5d82ca2757eb7c29a3362a"
token_count: "862"
---

# KRaft Consensus, Metadata Quorum, and Controller Architecture

## 1. The KRaft Architecture (Kafka Raft Metadata Mode)
In Apache Kafka 4.0, KRaft is the sole supported metadata mode; Apache ZooKeeper has been completely removed from the codebase. KRaft integrates a specialized event-driven Raft consensus algorithm directly into Kafka controller nodes.

### Core Motivation and Advantages over ZooKeeper
- **Scale:** Supports clusters with tens of millions of partitions by eliminating external ZooKeeper synchronization bottlenecks.
- **Fast Failovers:** In ZooKeeper mode, electing a new controller required loading the entire cluster metadata tree from ZooKeeper into JVM memory, taking minutes on large clusters. In KRaft, all standby controllers and brokers maintain a continuously updated, in-memory metadata cache by tailing the metadata log, enabling sub-second controller failovers.
- **Unified Security & Networking:** Eliminates separate ZooKeeper client ports, ACLs, and firewall rules; all controller communication uses standard Kafka SASL/TLS RPCs.

## 2. Quorum Controller Roles & Nodes
KRaft clusters divide nodes into specific process roles configured by `process.roles`:
- `process.roles=controller`: Dedicated quorum controller node.
- `process.roles=broker`: Dedicated data broker node handling topic partitions and client traffic.
- `process.roles=broker,controller`: Combined mode where a single JVM runs both broker and controller roles (ideal for development or small clusters).

### Active Leader Controller vs. Standby Controllers
- **Active Controller (Leader):** Elected by the Raft quorum. Only the active controller handles write requests for cluster metadata (e.g., `CreateTopics`, `AlterPartition`, `AlterConfigs`, `CreateAcls`). Every metadata change is committed as an event record to the `@metadata` topic log.
- **Standby Controllers (Followers):** Replicate the `@metadata` partition 0 log from the active controller using Raft `Fetch` and `FetchSnapshot` RPCs. They participate in quorum voting and are ready for immediate failover.
- **Brokers:** Regular broker nodes tail the `@metadata` partition 0 log asynchronously via standard `Fetch` requests and update their local in-memory metadata image.

## 3. The `@metadata` Replicated Topic
All cluster state is represented as an append-only event stream stored on partition 0 of the internal `@metadata` topic:
- Metadata records represent state transitions: `RegisterBrokerRecord`, `TopicRecord`, `PartitionRecord`, `ConfigRecord`, `AclRecord`.
- Periodically, the active controller creates a metadata snapshot file (`<offset>.checkpoint`) summarizing current cluster state, allowing new or lagging nodes to catch up quickly without replaying historical logs from offset zero.

## 4. Leader Election and Pre-Vote (KIP-996)
KRaft implements standard Raft leader election with randomized election timeouts (`controller.quorum.election.timeout.ms`, default: 1,000 ms) and heartbeats (`controller.quorum.fetch.timeout.ms`, default: 2,000 ms).
- **Pre-Vote Protocol (KIP-996):** Before a candidate controller increments its term and solicits votes, it broadcasts a Pre-Vote request. Peers only grant pre-votes if they have not heard from the active leader for longer than the election timeout. This prevents network-partitioned or isolated nodes with stale terms from disrupting an active quorum upon reconnection.

## 5. Key KRaft Configuration Parameters
- `process.roles`: Node role (`broker`, `controller`, or `broker,controller`).
- `node.id`: Unique non-negative integer ID identifying the node in the quorum.
- `controller.quorum.voters`: Comma-separated list of controller voters in the format `<node_id>@<host>:<port>`. Example: `1@controller1:9093,2@controller2:9093,3@controller3:9093`.
- `controller.listener.names`: Listener name used by controllers for Raft quorum RPCs (e.g., `CONTROLLER`).
- `metadata.log.dir`: Local directory where the `@metadata` partition log and snapshot checkpoints are stored.
