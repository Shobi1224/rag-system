import { Injectable, Logger } from '@nestjs/common';
import { LangGraphAgentService } from '../agent/langgraph.service';
import { ChatRequestDto, ChatResponseDto } from './chat.dto';
import { Observable } from 'rxjs';

@Injectable()
export class ChatService {
  private readonly logger = new Logger(ChatService.name);
  private sessionHistory: Map<string, Array<{ role: string; content: string }>> = new Map();

  constructor(private readonly agentService: LangGraphAgentService) {}

  async processChat(request: ChatRequestDto, traceId: string): Promise<ChatResponseDto> {
    // Record user message in session memory
    const history = this.sessionHistory.get(request.sessionId) || [];
    history.push({ role: 'user', content: request.message });

    const response = await this.agentService.runAgent(request, traceId);

    history.push({ role: 'assistant', content: response.answer });
    this.sessionHistory.set(request.sessionId, history);

    return response;
  }

  streamChat(request: ChatRequestDto, traceId: string): Observable<{ data: string }> {
    return new Observable((subscriber) => {
      (async () => {
        const response = await this.processChat(request, traceId);
        const words = response.answer.split(' ');
        for (const word of words) {
          subscriber.next({ data: JSON.stringify({ token: word + ' ' }) });
          await new Promise((r) => setTimeout(r, 25));
        }
        subscriber.next({ data: JSON.stringify({ citations: response.citations, traceId: response.traceId }) });
        subscriber.next({ data: '[DONE]' });
        subscriber.complete();
      })();
    });
  }
}
