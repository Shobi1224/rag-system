import { IsString, IsNotEmpty, IsOptional, IsIn } from 'class-validator';

export class ChatRequestDto {
  @IsString()
  @IsNotEmpty()
  sessionId: string;

  @IsString()
  @IsNotEmpty()
  message: string;

  @IsOptional()
  @IsIn(['live', 'replay'])
  mode?: string = 'live';

  @IsOptional()
  @IsIn(['docs', 'jira', 'mailing_list', 'combined', 'refuse'])
  overrideRouter?: string;
}

export interface CitationDto {
  sourceType: 'doc' | 'jira' | 'mailing_list';
  titleOrKey: string;
  url?: string;
  snippet?: string;
}

export interface ToolCallDto {
  toolName: string;
  arguments: Record<string, any>;
  status: string;
  executionTimeMs: number;
}

export class ChatResponseDto {
  sessionId: string;
  answer: string;
  citations: CitationDto[];
  toolCalls: ToolCallDto[];
  traceId?: string;
  routeTaken?: string;
  latencyMs: number;
  tokensUsed: number;
  estimatedCostUsd: number;
}
