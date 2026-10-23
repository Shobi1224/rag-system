import { Injectable, Logger } from '@nestjs/common';
import axios from 'axios';
import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';

export interface JiraIssueResult {
  key: string;
  title: string;
  status: string;
  component?: string;
  updated: string;
  snippet: string;
  url: string;
}

export interface JiraToolResponse {
  ok: boolean;
  errorType?: 'timeout' | 'rate_limit' | 'not_found' | 'empty' | 'replay_miss';
  message?: string;
  data?: JiraIssueResult | JiraIssueResult[];
}

@Injectable()
export class JiraToolService {
  private readonly logger = new Logger(JiraToolService.name);
  private readonly baseUrl = 'https://issues.apache.org/jira/rest/api/2';
  private readonly snapshotDir = path.resolve(process.cwd(), 'data', 'snapshots', 'jira');

  constructor() {
    if (!fs.existsSync(this.snapshotDir)) {
      fs.mkdirSync(this.snapshotDir, { recursive: true });
    }
  }

  private getHash(args: Record<string, any>): string {
    return crypto.createHash('sha256').update(JSON.stringify(args)).digest('hex').substring(0, 16);
  }

  private loadSnapshot(hash: string): JiraToolResponse | null {
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

  private saveSnapshot(hash: string, data: JiraToolResponse) {
    const file = path.join(this.snapshotDir, `${hash}.json`);
    fs.writeFileSync(file, JSON.stringify({ ...data, fetchedAt: new Date().toISOString() }, null, 2));
  }

  async searchIssues(
    query: string,
    component?: string,
    status?: string,
    limit: number = 5,
    mode: string = 'live'
  ): Promise<JiraToolResponse> {
    const args = { action: 'search', query, component, status, limit };
    const hash = this.getHash(args);

    if (mode === 'replay') {
      const cached = this.loadSnapshot(hash);
      if (cached) return cached;
      return { ok: false, errorType: 'replay_miss', message: `Missing Jira snapshot for replay: ${hash}` };
    }

    let jql = `project = KAFKA AND text ~ "${query.replace(/"/g, '\\"')}"`;
    if (component) jql += ` AND component = "${component}"`;
    if (status) jql += ` AND status = "${status}"`;
    jql += ' ORDER BY updated DESC';

    try {
      const res = await axios.get(`${this.baseUrl}/search`, {
        params: { jql, maxResults: limit, fields: 'key,summary,status,components,updated,description' },
        timeout: 10000,
      });

      const issues: JiraIssueResult[] = (res.data.issues || []).map((issue: any) => ({
        key: issue.key,
        title: issue.fields.summary,
        status: issue.fields.status?.name || 'Unknown',
        component: issue.fields.components?.[0]?.name,
        updated: issue.fields.updated,
        snippet: (issue.fields.description || '').substring(0, 300),
        url: `https://issues.apache.org/jira/browse/${issue.key}`,
      }));

      const result: JiraToolResponse = issues.length > 0
        ? { ok: true, data: issues }
        : { ok: false, errorType: 'empty', message: 'No Jira issues found for criteria.' };

      this.saveSnapshot(hash, result);
      return result;
    } catch (err: any) {
      const errorType = err.code === 'ECONNABORTED' ? 'timeout' : 'not_found';
      const result: JiraToolResponse = { ok: false, errorType, message: err.message };
      return result;
    }
  }

  async getIssue(key: string, mode: string = 'live'): Promise<JiraToolResponse> {
    const args = { action: 'get_issue', key };
    const hash = this.getHash(args);

    if (mode === 'replay') {
      const cached = this.loadSnapshot(hash);
      if (cached) return cached;
      return { ok: false, errorType: 'replay_miss', message: `Missing snapshot for Jira key: ${key}` };
    }

    try {
      const res = await axios.get(`${this.baseUrl}/issue/${key}`, { timeout: 10000 });
      const f = res.data.fields;
      const issue: JiraIssueResult = {
        key: res.data.key,
        title: f.summary,
        status: f.status?.name || 'Unknown',
        component: f.components?.[0]?.name,
        updated: f.updated,
        snippet: (f.description || '').substring(0, 500),
        url: `https://issues.apache.org/jira/browse/${key}`,
      };
      const result: JiraToolResponse = { ok: true, data: issue };
      this.saveSnapshot(hash, result);
      return result;
    } catch (err: any) {
      return { ok: false, errorType: 'not_found', message: `Issue ${key} not found: ${err.message}` };
    }
  }
}
