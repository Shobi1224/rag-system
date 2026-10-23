import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { QdrantClient } from '@qdrant/js-client-rest';

export interface RetrievedDocChunk {
  id: string | number;
  score: number;
  text: string;
  sourceUrl?: string;
  sectionTitle?: string;
  kafkaVersion?: string;
}

@Injectable()
export class QdrantVectorService implements OnModuleInit {
  private readonly logger = new Logger(QdrantVectorService.name);
  private client: QdrantClient;
  private readonly collectionName = process.env.QDRANT_COLLECTION_NAME || 'kafka_docs';

  onModuleInit() {
    const url = process.env.QDRANT_URL || 'http://localhost:6333';
    this.client = new QdrantClient({
      url,
      apiKey: process.env.QDRANT_API_KEY || undefined,
      timeout: 3000,
    });
    this.logger.log(`Initialized Qdrant client pointing to: ${url}`);
  }

  async isHealthy(): Promise<boolean> {
    try {
      await this.client.getCollections();
      return true;
    } catch {
      return false;
    }
  }

  async searchVectors(
    vector: number[],
    limit: number = 5,
    filter?: Record<string, any>
  ): Promise<RetrievedDocChunk[]> {
    try {
      const response = await this.client.query(this.collectionName, {
        query: vector,
        limit,
        filter: filter ? ({ must: Object.entries(filter).map(([k, v]) => ({ key: k, match: { value: v } })) } as any) : undefined,
        with_payload: true,
      });

      const points = response?.points || [];
      return points.map((r: any) => ({
        id: r.id,
        score: r.score,
        text: (r.payload?.text as string) || '',
        sourceUrl: (r.payload?.source_url as string) || '',
        sectionTitle: (r.payload?.section_title as string) || '',
        kafkaVersion: (r.payload?.kafka_version as string) || '',
      }));
    } catch (e: any) {
      this.logger.warn(`Vector search skipped or collection not found (${e.message})`);
      return [];
    }
  }
}

