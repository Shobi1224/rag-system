import { Injectable, Logger } from '@nestjs/common';
import { ChatGoogleGenerativeAI } from '@langchain/google-genai';
import { JiraToolService } from '../tools/jira.service';
import { MailingListToolService } from '../tools/mailing-list.service';
import { QdrantVectorService } from '../vector/qdrant.service';
import { ChatRequestDto, ChatResponseDto, CitationDto, ToolCallDto } from '../chat/chat.dto';

@Injectable()
export class LangGraphAgentService {
  private readonly logger = new Logger(LangGraphAgentService.name);
  private llm: ChatGoogleGenerativeAI;

  constructor(
    private readonly jiraService: JiraToolService,
    private readonly mailingListService: MailingListToolService,
    private readonly vectorService: QdrantVectorService,
  ) {
    const apiKey = process.env.GOOGLE_API_KEY || '';
    if (apiKey) {
      this.llm = new ChatGoogleGenerativeAI({
        model: process.env.GEMINI_MODEL || 'gemini-2.5-flash',
        apiKey,
        temperature: 0.0,
      });
    }
  }

  async routeQuery(message: string, override?: string): Promise<'docs' | 'jira' | 'mailing_list' | 'combined' | 'refuse'> {
    if (override) return override as any;
    
    const lower = message.toLowerCase();
    if (lower.includes('weather') || lower.includes('recipe') || lower.includes('football')) {
      return 'refuse';
    }
    if (lower.includes('kafka-') || lower.includes('bug') || lower.includes('jira') || lower.includes('issue')) {
      return 'jira';
    }
    if (lower.includes('mailing list') || lower.includes('thread') || lower.includes('dev@') || lower.includes('discussion')) {
      return 'mailing_list';
    }
    if (lower.includes('kip-') || (lower.includes('version') && lower.includes('behavior'))) {
      return 'combined';
    }
    return 'docs';
  }

  async runAgent(request: ChatRequestDto, traceId: string): Promise<ChatResponseDto> {
    const startTime = Date.now();
    const route = await this.routeQuery(request.message, request.overrideRouter);
    const citations: CitationDto[] = [];
    const toolCalls: ToolCallDto[] = [];
    let answer = '';

    if (route === 'refuse') {
      answer = "I'm a dedicated Apache Kafka assistant. I can only assist with Kafka documentation, KIPs, Jira issues, and mailing list discussions.";
    } else if (route === 'jira') {
      const toolStart = Date.now();
      const issueMatch = request.message.match(/KAFKA-\d+/i);
      if (issueMatch) {
        const key = issueMatch[0].toUpperCase();
        const res = await this.jiraService.getIssue(key, request.mode);
        toolCalls.push({
          toolName: 'get_issue',
          arguments: { key },
          status: res.ok ? 'success' : 'failed',
          executionTimeMs: Date.now() - toolStart,
        });
        if (res.ok && res.data && !Array.isArray(res.data)) {
          answer = `**Jira Issue ${res.data.key}: ${res.data.title}**\n- **Status:** ${res.data.status}\n- **Component:** ${res.data.component || 'N/A'}\n- **Summary:** ${res.data.snippet}\n- **Link:** ${res.data.url}`;
          citations.push({
            sourceType: 'jira',
            titleOrKey: res.data.key,
            url: res.data.url,
            snippet: res.data.snippet,
          });
        } else {
          answer = `Jira lookup for ${key} returned no active records (${res.message || 'Not Found'}).`;
        }
      } else {
        const res = await this.jiraService.searchIssues(request.message, undefined, undefined, 3, request.mode);
        toolCalls.push({
          toolName: 'search_issues',
          arguments: { query: request.message },
          status: res.ok ? 'success' : 'failed',
          executionTimeMs: Date.now() - toolStart,
        });
        if (res.ok && Array.isArray(res.data)) {
          answer = `Found relevant Kafka Jira issues:\n` + res.data.map(i => `- [${i.key}](${i.url}): ${i.title} (${i.status})`).join('\n');
          res.data.forEach(i => citations.push({ sourceType: 'jira', titleOrKey: i.key, url: i.url, snippet: i.snippet }));
        } else {
          answer = `No matching Jira tickets found for query.`;
        }
      }
    } else if (route === 'mailing_list') {
      const toolStart = Date.now();
      const res = await this.mailingListService.searchThreads(request.message, 'dev', 3, request.mode);
      toolCalls.push({
        toolName: 'search_threads',
        arguments: { query: request.message },
        status: res.ok ? 'success' : 'failed',
        executionTimeMs: Date.now() - toolStart,
      });
      if (res.ok && res.data) {
        answer = `Found relevant discussions in the Kafka dev mailing list:\n` + res.data.map(t => `- [${t.subject}](${t.url}) (${t.date})`).join('\n');
        res.data.forEach(t => citations.push({ sourceType: 'mailing_list', titleOrKey: t.subject, url: t.url, snippet: t.snippet }));
      } else {
        answer = `No relevant mailing list discussions found.`;
      }
    } else {
      // Docs / Combined route
      answer = `Response grounded on Kafka documentation for: "${request.message}".\n(Live retrieval will connect in Phase 3 after vector store loading).`;
      citations.push({
        sourceType: 'doc',
        titleOrKey: 'Apache Kafka Architecture & Design',
        url: 'https://kafka.apache.org/documentation/#design',
        snippet: 'Kafka is a distributed event store and stream-processing platform.',
      });
    }

    const latencyMs = Date.now() - startTime;
    const tokensUsed = Math.round(request.message.length / 4) + Math.round(answer.length / 4);
    const estimatedCostUsd = (tokensUsed / 1000000) * 0.15;

    return {
      sessionId: request.sessionId,
      answer,
      citations,
      toolCalls,
      traceId,
      routeTaken: route,
      latencyMs,
      tokensUsed,
      estimatedCostUsd: Number(estimatedCostUsd.toFixed(6)),
    };
  }
}
