import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { ChatController } from './modules/chat/chat.controller';
import { ChatService } from './modules/chat/chat.service';
import { LangGraphAgentService } from './modules/agent/langgraph.service';
import { JiraToolService } from './modules/tools/jira.service';
import { MailingListToolService } from './modules/tools/mailing-list.service';
import { QdrantVectorService } from './modules/vector/qdrant.service';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: ['.env'],
    }),
  ],
  controllers: [ChatController],
  providers: [
    ChatService,
    LangGraphAgentService,
    JiraToolService,
    MailingListToolService,
    QdrantVectorService,
  ],
})
export class AppModule {}
