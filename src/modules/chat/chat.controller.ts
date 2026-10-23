import { Controller, Post, Get, Body, Headers, Sse, MessageEvent } from '@nestjs/common';
import { ChatService } from './chat.service';
import { ChatRequestDto, ChatResponseDto } from './chat.dto';
import { QdrantVectorService } from '../vector/qdrant.service';
import { Observable } from 'rxjs';
import { v4 as uuidv4 } from 'uuid';

@Controller()
export class ChatController {
  constructor(
    private readonly chatService: ChatService,
    private readonly vectorService: QdrantVectorService,
  ) {}

  @Get('health')
  async getHealth() {
    const qdrantOk = await this.vectorService.isHealthy();
    return {
      status: 'ok',
      service: 'NestJS Kafka Agent Core',
      qdrantConnected: qdrantOk,
      geminiConfigured: !!process.env.GOOGLE_API_KEY,
      langsmithConfigured: !!process.env.LANGSMITH_API_KEY,
    };
  }

  @Post('chat')
  async chat(
    @Body() body: ChatRequestDto,
    @Headers('x-request-id') requestId?: string,
  ): Promise<ChatResponseDto> {
    const traceId = requestId || `trace-${uuidv4()}`;
    return this.chatService.processChat(body, traceId);
  }

  @Sse('chat/stream')
  streamChat(
    @Body() body: ChatRequestDto,
    @Headers('x-request-id') requestId?: string,
  ): Observable<MessageEvent> {
    const traceId = requestId || `trace-${uuidv4()}`;
    return this.chatService.streamChat(body, traceId) as any;
  }
}
