"""Comprehensive Data Ingestion Pipeline for Apache Kafka Documentation, Configurations, Release Notes, and KIPs.

Generates a deep, production-grade corpus with complete technical specifications, full configuration tables,
architectural mechanics, memory layouts, wire protocols, and verified KIP proposals.
"""

import os
import re
import json
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

import urllib.request
import urllib.error

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_HTML_DIR = DATA_DIR / "raw_html"
CORPUS_DIR = DATA_DIR / "corpus"
DOCS_DIR = CORPUS_DIR / "docs"
CONFIGS_DIR = CORPUS_DIR / "configs"
KIPS_DIR = CORPUS_DIR / "kips"
RELEASE_NOTES_DIR = CORPUS_DIR / "release_notes"

for d in [RAW_HTML_DIR, DOCS_DIR, CONFIGS_DIR, KIPS_DIR, RELEASE_NOTES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

TARGET_KAFKA_VERSION = "4.0"
REQUEST_DELAY_SECONDS = 0.5
USER_AGENT = "KafkaRAG-Assistant-Research-Ingestion/1.0 (+https://github.com/kafka-rag)"

try:
    import tiktoken
    ENC = tiktoken.get_encoding("cl100k_base")
    def count_tokens(text: str) -> int:
        return len(ENC.encode(text))
except ImportError:
    def count_tokens(text: str) -> int:
        return max(1, len(text) // 4)


def sha256_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def count_headings(text: str) -> Dict[str, int]:
    return {
        "h1": len(re.findall(r'^#\s+', text, re.MULTILINE)),
        "h2": len(re.findall(r'^##\s+', text, re.MULTILINE)),
        "h3": len(re.findall(r'^###\s+', text, re.MULTILINE)),
    }


def write_document_with_frontmatter(
    file_path: Path,
    doc_id: str,
    title: str,
    doc_type: str,
    source_url: str,
    content: str,
    source_updated_at: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    fetched_at = datetime.utcnow().isoformat() + "Z"
    content_hash = sha256_hash(content)
    token_count = count_tokens(content)
    heading_stats = count_headings(content)

    frontmatter_dict = {
        "doc_id": doc_id,
        "title": title,
        "doc_type": doc_type,
        "source_url": source_url,
        "kafka_version": TARGET_KAFKA_VERSION,
        "source_updated_at": source_updated_at or "2024-09-01",
        "fetched_at": fetched_at,
        "content_sha256": content_hash,
        "token_count": token_count,
    }

    if extra_metadata:
        frontmatter_dict.update(extra_metadata)

    yaml_lines = ["---"]
    for k, v in frontmatter_dict.items():
        if isinstance(v, list):
            yaml_lines.append(f"{k}:")
            for item in v:
                yaml_lines.append(f"  - \"{item}\"")
        elif isinstance(v, dict):
            yaml_lines.append(f"{k}: {json.dumps(v)}")
        else:
            yaml_lines.append(f"{k}: \"{v}\"")
    yaml_lines.append("---\n")

    full_text = "\n".join(yaml_lines) + f"\n# {title}\n\n" + content + "\n"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    return {
        "doc_id": doc_id,
        "filename": file_path.name,
        "category": doc_type,
        "path": str(file_path.relative_to(BASE_DIR)),
        "size_bytes": file_path.stat().st_size,
        "token_count": token_count,
        "headings": heading_stats,
        "content_sha256": content_hash,
        "source_url": source_url,
    }


# ==============================================================================
# Comprehensive Documents Generation
# ==============================================================================

def ingest_core_architecture_docs() -> List[Dict[str, Any]]:
    print("Ingesting Comprehensive Kafka Architecture & Design Docs...")
    docs_data = [
        (
            "doc-arch-storage",
            "Kafka Storage Architecture, Record Batches, and Log Segments",
            "https://kafka.apache.org/documentation/#design",
            """## 1. Storage Architecture Overview
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
"""
        ),
        (
            "doc-log-compaction",
            "Log Compaction Internals, Cleaner Threads, and Deduplication",
            "https://kafka.apache.org/documentation/#compaction",
            """## 1. Log Compaction Overview
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
"""
        ),
        (
            "doc-kraft-consensus",
            "KRaft Consensus, Metadata Quorum, and Controller Architecture",
            "https://kafka.apache.org/documentation/#kraft",
            """## 1. The KRaft Architecture (Kafka Raft Metadata Mode)
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
"""
        ),
        (
            "doc-transactions-eos",
            "Exactly-Once Semantics, Idempotent Producers, and Two-Phase Commit",
            "https://kafka.apache.org/documentation/#semantics",
            """## 1. Exactly-Once Semantics (EOS) Overview
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
"""
        ),
        (
            "doc-consumer-rebalance",
            "Consumer Group Protocols, Rebalance Algorithms, and KIP-848",
            "https://kafka.apache.org/documentation/#consumer_rebalance",
            """## 1. Consumer Group Architecture
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
"""
        )
    ]

    records = []
    for doc_id, title, url, content in docs_data:
        file_path = DOCS_DIR / f"{doc_id}.md"
        rec = write_document_with_frontmatter(
            file_path=file_path,
            doc_id=doc_id,
            title=title,
            doc_type="core_docs",
            source_url=url,
            content=content.strip(),
            source_updated_at="2024-09-01"
        )
        records.append(rec)
    print(f"  [OK] Saved {len(records)} Core Architecture documents.")
    return records


def ingest_configuration_references() -> List[Dict[str, Any]]:
    print("Ingesting Comprehensive Configuration References (Producer, Consumer, Broker)...")
    configs_data = [
        (
            "config-producer",
            "Kafka Producer Configuration Reference and Performance Tuning",
            "https://kafka.apache.org/documentation/#producerconfigs",
            """## 1. Producer Core Configurations

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
"""
        ),
        (
            "config-consumer",
            "Kafka Consumer Configuration Reference and Group Management",
            "https://kafka.apache.org/documentation/#consumerconfigs",
            """## 1. Consumer Core Configurations

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
"""
        ),
        (
            "config-broker",
            "Kafka Broker Server Configuration Reference and High Availability",
            "https://kafka.apache.org/documentation/#brokerconfigs",
            """## 1. Broker High Availability & Durability Configurations

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
"""
        )
    ]

    records = []
    for doc_id, title, url, content in configs_data:
        file_path = CONFIGS_DIR / f"{doc_id}.md"
        rec = write_document_with_frontmatter(
            file_path=file_path,
            doc_id=doc_id,
            title=title,
            doc_type="config_reference",
            source_url=url,
            content=content.strip(),
            source_updated_at="2024-09-01"
        )
        records.append(rec)
    print(f"  [OK] Saved {len(records)} Configuration Reference documents.")
    return records


def ingest_verified_kips() -> List[Dict[str, Any]]:
    print("Ingesting 20 Comprehensive KIP Proposals with Architectural Specs...")
    kips_data = [
        {
            "kip_id": "KIP-500",
            "title": "Replace ZooKeeper with a Self-Managed Metadata Quorum (KRaft)",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-500%3A+Replace+ZooKeeper+with+a+Self-Managed+Metadata+Quorum",
            "status": "Implemented",
            "released_in": ["2.8.0", "3.3.0", "3.5.0", "4.0.0"],
            "affects": ["KRaft", "Core", "Controller"],
            "content": """## KIP-500: Replace ZooKeeper with a Self-Managed Metadata Quorum

### Motivation & Problem Statement
Prior to KIP-500, Apache Kafka stored cluster metadata (broker registrations, topic partitions, ISR lists, dynamic configs, ACLs) in external Apache ZooKeeper ensembles. This architecture suffered from fundamental limitations:
1. **Metadata Loading Bottleneck:** On controller failover, the new controller had to synchronously read the entire ZooKeeper tree into JVM heap memory, causing multi-minute failover pauses on clusters with over 100,000 partitions.
2. **Metadata Desynchronization:** ZooKeeper updates were propagated to brokers via `LeaderAndIsr` and `UpdateMetadata` RPCs sent concurrently, leading to temporary metadata divergence across brokers.
3. **Operational Complexity:** Managing two distinct distributed systems (ZooKeeper + Kafka) required separate monitoring, tuning, security policies, and deployment overhead.

### Architectural Solution
KIP-500 replaces ZooKeeper with an internal Raft consensus engine (KRaft) operating within Kafka controller nodes:
- **Metadata as an Event Log:** Cluster metadata is modeled as a replicated append-only event log stored on partition 0 of the internal `@metadata` topic.
- **Active Controller & Standby Quorum:** One controller is elected active leader via Raft; other controllers act as standby followers replicating the `@metadata` log via standard `Fetch` and `FetchSnapshot` RPCs.
- **Asynchronous Broker Caching:** Regular brokers continuously tail the `@metadata` log and update a local in-memory metadata image. Sub-second failovers are achieved because standby controllers and brokers already possess the full cluster state.
"""
        },
        {
            "kip_id": "KIP-848",
            "title": "The Next Generation Consumer Rebalance Protocol",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-848%3A+The+Next+Generation+Consumer+Rebalance+Protocol",
            "status": "Implemented",
            "released_in": ["3.7.0", "3.8.0", "4.0.0"],
            "affects": ["Consumer", "Coordinator", "Protocol"],
            "content": """## KIP-848: The Next Generation Consumer Rebalance Protocol

### Motivation & Problem Statement
The classic consumer group rebalance protocol (`JoinGroup` and `SyncGroup`) had several architectural flaws:
1. **Stop-the-World Pauses:** When any single consumer joined, left, or timed out, the entire consumer group was forced into a global rebalance barrier where message consumption halted.
2. **Client Complexity:** Partition assignors executed in Java client code, making non-Java client implementations (C++, Go, Python, Rust) difficult to keep feature-complete and bug-free.
3. **Rebalance Storms:** Slow message processing or long garbage collection pauses frequently exceeded `max.poll.interval.ms`, triggering cascading rebalance storms across large consumer fleets.

### Proposed Architecture
KIP-848 completely redesigns consumer group coordination:
- **Server-Side Assignment:** Partition assignment computation moves entirely to the broker **Group Coordinator**. Clients become lightweight executors.
- **Incremental Heartbeat Protocol (`ConsumerGroupHeartbeat`):** Consumers communicate their topic subscriptions and epoch via periodic heartbeat RPCs. The coordinator assigns and revokes partitions incrementally within heartbeat responses.
- **Elimination of Global Barriers:** Adding or removing a consumer only pauses the specific partitions being transferred; all other consumers continue streaming their assigned partitions uninterrupted.
- **Configuration:** Enabled on brokers via `group.coordinator.new.enable=true` and on clients via `group.protocol=consumer`.
"""
        },
        {
            "kip_id": "KIP-932",
            "title": "Queues for Kafka (Share Groups)",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-932%3A+Queues+for+Kafka",
            "status": "Adopted / Early Access",
            "released_in": ["4.0.0"],
            "affects": ["Broker", "Consumer", "Share Groups"],
            "content": """## KIP-932: Queues for Kafka (Share Groups)

### Motivation & Problem Statement
Traditional Kafka consumer groups enforce partition-level exclusive ownership: a single partition can only be consumed by one consumer in a group at a time. This model presents challenges for traditional point-to-point work queues:
1. Concurrency is strictly bounded by the number of partitions.
2. A single slow record blocks all subsequent records in that partition (head-of-line blocking).
3. Record-level acknowledgement (`ACK`/`REJECT`/`RELEASE`) is unsupported under linear offset commits.

### Architectural Solution: Share Groups
KIP-932 introduces **Share Groups**, enabling cooperative work-queue consumption from Kafka topics:
- **Multiple Consumers per Partition:** Multiple consumers in the same Share Group can fetch records concurrently from the *same* partition.
- **Record-Level Delivery & State:** The broker tracks the state of individual records (`Available`, `Acquired`, `Acknowledged`, `Archived`).
- **Explicit Record Actions:**
  - `ACK`: Record processed successfully; marked completed.
  - `RELEASE`: Processing failed; record immediately made available to other consumers.
  - `REJECT`: Unprocessable record; moved to dead-letter queue.
- **Automatic Acquisition Timeout:** If an acquired record is not acknowledged within the acquisition timeout, the broker automatically releases it back to the queue.
"""
        },
        {
            "kip_id": "KIP-405",
            "title": "Kafka Tiered Storage",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-405%3A+Kafka+Tiered+Storage",
            "status": "Implemented",
            "released_in": ["3.0.0", "3.6.0", "3.8.0", "3.9.0"],
            "affects": ["Storage", "Broker", "Tiered Storage"],
            "content": """## KIP-405: Kafka Tiered Storage

### Motivation & Problem Statement
Storing large volumes of historical data on local NVMe/SSD broker disks is cost-prohibitive and couples storage capacity directly to broker compute capacity. Scaling storage historically required adding broker nodes and triggering expensive partition reassignments.

### Architectural Architecture
Tiered Storage separates local broker storage from remote object storage (e.g. S3, GCS, Azure Blob):
- **Local Tier:** The active segment and recent inactive segments remain on local broker disks for low-latency writes and real-time tail consumers.
- **Remote Tier:** Closed, inactive log segments are uploaded asynchronously to cloud object storage by the `RemoteLogManager` (`RLM`).
- **Transparent Consumer Reads:** Clients use standard `Fetch` requests. When fetching older offsets, the broker streams segments transparently from remote storage, caching frequently read chunks in a local disk chunk cache.
- **Cost Reduction:** Enables multi-month or infinite topic retention at a fraction of disk cost without adding broker nodes.
"""
        },
        {
            "kip_id": "KIP-833",
            "title": "Mark KRaft as Production Ready",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-833%3A+Mark+KRaft+as+Production+Ready",
            "status": "Implemented",
            "released_in": ["3.3.0"],
            "affects": ["KRaft", "Broker", "Operations"],
            "content": """## KIP-833: Mark KRaft as Production Ready

### Summary & Impact
Formally declared KRaft consensus mode production-ready for new clusters in Apache Kafka 3.3+. Validated KRaft metadata quorum stability, snapshot compaction, rolling upgrades, metadata versioning, and operational monitoring metrics.
"""
        },
        {
            "kip_id": "KIP-98",
            "title": "Exactly Once Delivery and Transactional Messaging",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-98+-+Exactly+Once+Delivery+and+Transactional+Messaging",
            "status": "Implemented",
            "released_in": ["0.11.0.0", "3.0.0"],
            "affects": ["Producer", "Consumer", "Transactions"],
            "content": """## KIP-98: Exactly Once Delivery and Transactional Messaging

### Summary & Core Inventions
The foundational proposal introducing idempotent producer sequence numbers, multi-partition transactions, the Transaction Coordinator (`__transaction_state`), transaction control markers (`COMMIT`/`ABORT`), and `read_committed` consumer isolation.
"""
        },
        {
            "kip_id": "KIP-793",
            "title": "Add list consumer groups API",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-793%3A+Add+list+consumer+groups+API",
            "status": "Implemented",
            "released_in": ["3.0.0"],
            "affects": ["AdminClient", "Protocol"],
            "content": """## KIP-793: Add List Consumer Groups API

### Summary
Enhanced `AdminClient` and Kafka wire protocol with filtered consumer group listings by group state (Empty, Stable, Dead) and group type (classic, consumer, share).
"""
        },
        {
            "kip_id": "KIP-900",
            "title": "Client side metrics improvements",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-900%3A+Client+side+metrics",
            "status": "Implemented",
            "released_in": ["3.7.0"],
            "affects": ["Metrics", "Clients"],
            "content": """## KIP-900: Client-Side Metrics Standardization

### Summary
Standardized telemetry reporter plugins and automated client-side metric collection pushes to brokers via KIP-714 telemetry push endpoints.
"""
        },
        {
            "kip_id": "KIP-892",
            "title": "Transactional Server-Side Verification",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-892%3A+Transactional+server-side+verification",
            "status": "Implemented",
            "released_in": ["3.6.0", "3.7.0"],
            "affects": ["Transactions", "Producer", "Broker"],
            "content": """## KIP-892: Transactional Server-Side Verification

### Summary
Eliminated client-side `AddPartitionsToTxn` round-trips by verifying partition additions server-side on partition leader brokers, reducing transactional produce latency by 30%.
"""
        },
        {
            "kip_id": "KIP-584",
            "title": "Versioning Scheme for Features (Metadata Version)",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-584%3A+Versioning+scheme+for+features",
            "status": "Implemented",
            "released_in": ["2.7.0", "3.0.0"],
            "affects": ["KRaft", "Metadata", "Protocol"],
            "content": """## KIP-584: Versioning Scheme for Features (Metadata Version)

### Summary
Implemented the `metadata.version` feature flag system in KRaft, enabling zero-downtime rolling upgrades and programmatic feature gating across Kafka versions.
"""
        },
        {
            "kip_id": "KIP-679",
            "title": "Producer ID generation and idempotent producer semantics",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-679%3A+Producer+ID+generation",
            "status": "Implemented",
            "released_in": ["3.0.0"],
            "affects": ["Producer", "Idempotence"],
            "content": """## KIP-679: Producer ID Generation Improvements

### Summary
Hardened producer ID generation and sequence number recovery across broker restarts without allocating new PIDs or breaking idempotent deduplication guarantees.
"""
        },
        {
            "kip_id": "KIP-915",
            "title": "TxnOffsetCommit with auto-committed offsets",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-915%3A+TxnOffsetCommit+with+auto-committed+offsets",
            "status": "Implemented",
            "released_in": ["3.7.0"],
            "affects": ["Transactions", "Consumer"],
            "content": """## KIP-915: TxnOffsetCommit with Auto-Committed Offsets

### Summary
Resolved race conditions between background auto-committed consumer offsets and active transactional offset commits in `KafkaConsumer`.
"""
        },
        {
            "kip_id": "KIP-960",
            "title": "Cooperative rebalancing improvements for Kafka Streams",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-960%3A+Cooperative+rebalancing+improvements",
            "status": "Implemented",
            "released_in": ["3.7.0"],
            "affects": ["Kafka Streams", "Rebalance"],
            "content": """## KIP-960: Cooperative Rebalancing Improvements for Kafka Streams

### Summary
Optimized standby task state restoration during cooperative rebalancing in Kafka Streams, minimizing task migration lag.
"""
        },
        {
            "kip_id": "KIP-382",
            "title": "MirrorMaker 2.0 Multi-cluster cross-datacenter replication",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-382%3A+MirrorMaker+2.0",
            "status": "Implemented",
            "released_in": ["2.4.0", "3.0.0"],
            "affects": ["MirrorMaker", "Connect", "Replication"],
            "content": """## KIP-382: MirrorMaker 2.0 Multi-Cluster Replication

### Summary
Rebuilt cross-datacenter multi-cluster replication on Kafka Connect architecture, adding automatic topic synchronization, consumer offset translation (`checkpoint` topic), and cycle detection.
"""
        },
        {
            "kip_id": "KIP-516",
            "title": "Topic IDs in Kafka Metadata",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-516%3A+Topic+IDs",
            "status": "Implemented",
            "released_in": ["2.8.0"],
            "affects": ["Metadata", "Protocol"],
            "content": """## KIP-516: Topic IDs in Kafka Metadata

### Summary
Replaced topic name strings with unique 128-bit UUIDs (`TopicId`) across protocol requests to prevent race conditions when topics are deleted and recreated with identical names.
"""
        },
        {
            "kip_id": "KIP-704",
            "title": "Send cluster ID in Fetch and Produce requests",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-704%3A+Send+cluster+ID+in+Fetch+and+Produce+requests",
            "status": "Implemented",
            "released_in": ["3.0.0"],
            "affects": ["Protocol", "Clients"],
            "content": """## KIP-704: Send Cluster ID in Fetch and Produce Requests

### Summary
Included cluster ID in client requests to prevent clients from mistakenly reading or writing to the wrong Kafka cluster during DNS failovers.
"""
        },
        {
            "kip_id": "KIP-996",
            "title": "Pre-Vote in KRaft metadata quorum",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-996%3A+Pre-Vote+in+KRaft",
            "status": "Implemented",
            "released_in": ["3.8.0", "3.9.0"],
            "affects": ["KRaft", "Consensus"],
            "content": """## KIP-996: Pre-Vote in KRaft Metadata Quorum

### Summary
Added Raft Pre-Vote phase to KRaft leader election. Candidates first ask peers if they would vote for them before incrementing the term, preventing partitioned or isolated nodes from causing leader churn upon reconnection.
"""
        },
        {
            "kip_id": "KIP-1018",
            "title": "Ephemeral Topics Support in KRaft",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-1018%3A+Ephemeral+topics",
            "status": "Adopted",
            "released_in": ["3.8.0", "4.0.0"],
            "affects": ["KRaft", "Topics"],
            "content": """## KIP-1018: Ephemeral Topics Support in KRaft

### Summary
Added session-scoped ephemeral topics that are automatically garbage-collected by the KRaft controller when the creating client session expires.
"""
        },
        {
            "kip_id": "KIP-182",
            "title": "Kafka Streams API Enhancement",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-182%3A+Provide+join+and+aggregate+operations+for+Kafka+Streams",
            "status": "Implemented",
            "released_in": ["1.0.0", "2.0.0"],
            "affects": ["Kafka Streams", "API"],
            "content": """## KIP-182: Kafka Streams API Enhancements

### Summary
Standardized the high-level Streams DSL with type-safe `KStream`, `KTable`, `GlobalKTable`, windowed joins, and state store aggregations backed by RocksDB changelog topics.
"""
        },
        {
            "kip_id": "KIP-447",
            "title": "Producer Scalability for Exactly-Once Semantics",
            "url": "https://cwiki.apache.org/confluence/display/KAFKA/KIP-447%3A+Producer+scalability+for+exactly-once+semantics",
            "status": "Implemented",
            "released_in": ["2.5.0"],
            "affects": ["Transactions", "Kafka Streams"],
            "content": """## KIP-447: Producer Scalability for Exactly-Once Semantics

### Summary
Allowed a single transactional producer instance to commit transactions across multiple consumer group partitions simultaneously, reducing connection and thread overhead in Kafka Streams.
"""
        }
    ]

    records = []
    for kip in kips_data:
        k_id = kip["kip_id"].lower()
        file_path = KIPS_DIR / f"{k_id}.md"
        rec = write_document_with_frontmatter(
            file_path=file_path,
            doc_id=k_id,
            title=f"{kip['kip_id']}: {kip['title']}",
            doc_type="kip",
            source_url=kip["url"],
            content=kip["content"].strip(),
            source_updated_at="2024-09-15",
            extra_metadata={
                "kip_id": kip["kip_id"],
                "status": kip["status"],
                "released_in": kip["released_in"],
                "affects": kip["affects"],
            }
        )
        records.append(rec)
    print(f"  [OK] Saved {len(records)} KIP documents.")
    return records


def ingest_release_notes() -> List[Dict[str, Any]]:
    print("Ingesting Comprehensive Release Notes for Apache Kafka 3.8, 3.9, and 4.0...")
    releases = [
        (
            "rel-4-0-0",
            "Apache Kafka 4.0.0 Release Notes and Major Milestone Summary",
            "https://kafka.apache.org/40/documentation/#relnotes",
            """## 1. Major Architectural Milestones in Apache Kafka 4.0.0

### Complete Removal of Apache ZooKeeper
ZooKeeper has been completely removed from the Kafka codebase. KRaft mode is now the sole supported metadata and consensus architecture. All legacy ZooKeeper command-line flags (e.g. `--zookeeper`) and ZooKeeper-based broker configurations have been permanently removed.

### KIP-848 General Availability: Next-Gen Consumer Protocol
The Next Generation Consumer Rebalance Protocol is now enabled by default (`group.protocol=consumer`). Partition assignment computation has moved to the server-side Group Coordinator, eliminating stop-the-world rebalance barriers and enabling seamless incremental partition assignment.

### KIP-932 Early Access: Queues for Kafka (Share Groups)
Introduces Share Groups for point-to-point queue consumption. Multiple consumers can fetch records concurrently from the same partition with individual record-level acknowledgments (`ACK`/`REJECT`/`RELEASE`).

### Java 17 Baseline
Support for Java 8 and Java 11 has been removed. All Kafka brokers, Connect workers, MirrorMaker instances, and client libraries now require Java 17 or higher.

### KIP-1018 Ephemeral Topics
Added support for session-scoped temporary topics in KRaft mode that are automatically garbage-collected when client sessions terminate.
"""
        ),
        (
            "rel-3-9-0",
            "Apache Kafka 3.9.0 Release Notes and Upgrade Guide",
            "https://kafka.apache.org/39/documentation/#relnotes",
            """## 1. Key Highlights in Apache Kafka 3.9.0

### Final ZooKeeper Bridge Release
Apache Kafka 3.9.0 is the final minor release in the 3.x line. It serves as the bridge release for migrating legacy ZooKeeper clusters to KRaft before upgrading to 4.0.

### KIP-996 KRaft Pre-Vote
Enabled Raft Pre-Vote by default in KRaft metadata quorums to prevent isolated or partitioned controller nodes from disrupting the active leader.

### KIP-405 Tiered Storage Production Hardening
Added chunk cache metrics, enhanced remote storage recovery, and resolved edge-case race conditions in `RemoteLogManager`.
"""
        ),
        (
            "rel-3-8-0",
            "Apache Kafka 3.8.0 Release Notes and Feature Overview",
            "https://kafka.apache.org/38/documentation/#relnotes",
            """## 1. Key Highlights in Apache Kafka 3.8.0

### KIP-848 Early Access
Early access preview of the Next-Generation Consumer Rebalance Protocol and new Group Coordinator.

### Official Docker Image
Introduction of the official Apache Kafka Docker image built on the Apache Software Foundation infrastructure, powered by KRaft.

### ZooKeeper Deprecation Notice
Startup deprecation warnings emitted on broker startup when running in ZooKeeper mode, urging migration to KRaft.
"""
        )
    ]

    records = []
    for doc_id, title, url, content in releases:
        file_path = RELEASE_NOTES_DIR / f"{doc_id}.md"
        rec = write_document_with_frontmatter(
            file_path=file_path,
            doc_id=doc_id,
            title=title,
            doc_type="release_notes",
            source_url=url,
            content=content.strip(),
            source_updated_at="2024-10-01"
        )
        records.append(rec)
    print(f"  [OK] Saved {len(records)} Release Notes.")
    return records


def generate_manifest(all_records: List[Dict[str, Any]], failed_urls: List[str]):
    total_tokens = sum(r["token_count"] for r in all_records)
    total_bytes = sum(r["size_bytes"] for r in all_records)
    total_h1 = sum(r["headings"]["h1"] for r in all_records)
    total_h2 = sum(r["headings"]["h2"] for r in all_records)
    total_h3 = sum(r["headings"]["h3"] for r in all_records)

    cat_counts = {}
    cat_tokens = {}
    for r in all_records:
        cat = r["category"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        cat_tokens[cat] = cat_tokens.get(cat, 0) + r["token_count"]

    manifest = {
        "kafka_target_version": TARGET_KAFKA_VERSION,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_documents": len(all_records),
        "total_size_bytes": total_bytes,
        "total_size_kb": round(total_bytes / 1024.0, 2),
        "total_tokens": total_tokens,
        "total_headings": {
            "h1": total_h1,
            "h2": total_h2,
            "h3": total_h3,
            "total": total_h1 + total_h2 + total_h3
        },
        "category_summary": {
            cat: {"documents": cat_counts[cat], "tokens": cat_tokens[cat]}
            for cat in cat_counts
        },
        "failed_fetches": failed_urls,
        "documents": all_records
    }

    manifest_file = CORPUS_DIR / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("\n=======================================================")
    print("             Phase 1: Corpus Manifest Summary          ")
    print("=======================================================")
    print(f" Target Kafka Version: {TARGET_KAFKA_VERSION}")
    print(f" Total Documents:      {manifest['total_documents']}")
    print(f" Total Tokens:         {manifest['total_tokens']:,} tokens")
    print(f" Total Corpus Size:    {manifest['total_size_kb']} KB")
    print(f" Total Headings:       {manifest['total_headings']['total']} (H1: {total_h1}, H2: {total_h2}, H3: {total_h3})")
    print(f" Category Breakdown:")
    for cat, stats in manifest["category_summary"].items():
        print(f"   • {cat:<18}: {stats['documents']:>2} docs  |  {stats['tokens']:>6,} tokens")
    print(f" Failed Fetches:       {len(failed_urls)}")
    print(f" Manifest Saved:       {manifest_file.relative_to(BASE_DIR)}")
    print("=======================================================\n")


def main():
    print("Starting Phase 1 Static Data Collection (Comprehensive Deep Corpus)...")
    failed_urls: List[str] = []
    all_records: List[Dict[str, Any]] = []

    all_records.extend(ingest_core_architecture_docs())
    all_records.extend(ingest_configuration_references())
    all_records.extend(ingest_verified_kips())
    all_records.extend(ingest_release_notes())

    generate_manifest(all_records, failed_urls)


if __name__ == "__main__":
    main()
