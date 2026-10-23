import { Injectable, Logger } from '@nestjs/common';
import axios from 'axios';
import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';

export interface MailingListThread {
  subject: string;
  date: string;
  author: string;
  snippet: string;
  url: string;
}

export interface MailingListToolResponse {
  ok: boolean;
  errorType?: 'timeout' | 'rate_limit' | 'not_found' | 'empty' | 'replay_miss';
  message?: string;
  data?: MailingListThread[];
}

@Injectable()
export class MailingListToolService {
  private readonly logger = new Logger(MailingListToolService.name);
  private readonly snapshotDir = path.resolve(process.cwd(), 'data', 'snapshots', 'mailing_list');

  constructor() {
    if (!fs.existsSync(this.snapshotDir)) {
      fs.mkdirSync(this.snapshotDir, { recursive: true });
    }
  }

  private getHash(args: Record<string, any>): string {
    return crypto.createHash('sha256').update(JSON.stringify(args)).digest('hex').substring(0, 16);
  }

  private loadSnapshot(hash: string): MailingListToolResponse | null {
    const file = path.join(this.snapshotDir, `${hash}.json`);
    if (fs.existsSync(file)) {
      try {
        const raw = fs.readFileSync(file, 'utf-8');
        return JSON.parse(raw);
      } catch (e) {
        this.logger.warn(`Failed reading snapshot: ${file}`);
      }
    }
    return null;
  }

  private saveSnapshot(hash: string, data: MailingListToolResponse) {
    const file = path.join(this.snapshotDir, `${hash}.json`);
    fs.writeFileSync(file, JSON.stringify({ ...data, fetchedAt: new Date().toISOString() }, null, 2));
  }

  async searchThreads(
    query: string,
    list: 'dev' | 'users' = 'dev',
    limit: number = 5,
    mode: string = 'live'
  ): Promise<MailingListToolResponse> {
    const args = { query, list, limit };
    const hash = this.getHash(args);

    if (mode === 'replay') {
      const cached = this.loadSnapshot(hash);
      if (cached) return cached;
      return { ok: false, errorType: 'replay_miss', message: `Missing mailing list snapshot: ${hash}` };
    }

    try {
      // Apache Pony Mail archive search endpoint for Kafka
      const targetList = list === 'dev' ? 'dev@kafka.apache.org' : 'users@kafka.apache.org';
      const searchUrl = `https://lists.apache.org/api/stats.lua?list=${targetList}&q=${encodeURIComponent(query)}`;
      
      const res = await axios.get(searchUrl, { timeout: 10000 });
      const emails = res.data?.emails || [];

      const threads: MailingListThread[] = emails.slice(0, limit).map((em: any) => ({
        subject: em.subject || 'No Subject',
        date: em.date || '',
        author: em.from || '',
        snippet: (em.body || '').substring(0, 300),
        url: `https://lists.apache.org/thread/${em.id}`,
      }));

      const result: MailingListToolResponse = threads.length > 0
        ? { ok: true, data: threads }
        : { ok: false, errorType: 'empty', message: `No mailing list threads found for: ${query}` };

      this.saveSnapshot(hash, result);
      return result;
    } catch (err: any) {
      const errorType = err.code === 'ECONNABORTED' ? 'timeout' : 'not_found';
      const result: MailingListToolResponse = { ok: false, errorType, message: err.message };
      return result;
    }
  }
}
