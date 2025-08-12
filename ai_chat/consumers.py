import json
import urllib.parse
from channels.generic.websocket import AsyncWebsocketConsumer
from django_tenants.utils import schema_context
from courses.utils import retrieve_documents, generate_ai_response
from core.models import Tenant
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from channels.db import database_sync_to_async
import logging
from .models import ChatSession, ChatMessage

logger = logging.getLogger(__name__)

class AIChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        query_string = self.scope["query_string"].decode()
        params = urllib.parse.parse_qs(query_string)
        tenant_id = params.get('tenant_id', [''])[0]
        access_token = params.get('token', [''])[0]
        self.session_id = params.get('session_id', [''])[0]

        logger.debug(f"Connecting with tenant_id: {tenant_id}, access_token: {access_token[:10]}..., session_id: {self.session_id}")

        if not tenant_id or not access_token:
            logger.warning("Missing tenant_id or access_token, closing connection")
            await self.close()
            return

        try:
            self.tenant = await self.get_tenant(tenant_id)
            self.tenant_schema = self.tenant.schema_name
            logger.debug(f"Tenant found: {self.tenant_schema}")
            
            self.user = await self.authenticate_user(access_token)
            logger.debug(f"User authenticated: {self.user}")
            
            await self.accept()
            logger.info("WebSocket connection accepted")
        except (Tenant.DoesNotExist, AuthenticationFailed) as e:
            logger.error(f"Authentication failed: {str(e)}")
            await self.close()
        except Exception as e:
            logger.error(f"Unexpected error during connection: {str(e)}", exc_info=True)
            await self.close()

    @database_sync_to_async
    def get_tenant(self, tenant_id):
        logger.debug(f"Fetching tenant with id: {tenant_id}")
        return Tenant.objects.get(id=tenant_id)

    @database_sync_to_async
    def authenticate_user(self, access_token):
        logger.debug("Authenticating user with JWT")
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(access_token)
        return jwt_auth.get_user(validated_token)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            query = data.get('message')
            logger.debug(f"Received query: {query}")

            if query:
                with schema_context(self.tenant_schema):
                    documents = await retrieve_documents(query, self.tenant_schema)
                    response = await generate_ai_response(query, documents, self.tenant_schema)

                    # Save user message
                    await self.save_message(self.session_id, 'user', query)
                    # Save AI response
                    await self.save_message(self.session_id, 'ai', response)

                await self.send(text_data=json.dumps({'message': response}))
        except Exception as e:
            logger.error(f"Failed to process query: {str(e)}", exc_info=True)
            await self.send(text_data=json.dumps({'error': f"Failed to process query: {str(e)}"}))

    @database_sync_to_async
    def save_message(self, session_id, sender, text):
        try:
            with schema_context(self.tenant_schema):
                logger.debug(f"Saving message in schema: {self.tenant_schema}, session_id: {session_id}, type: {type(session_id)}")
                if not session_id:
                    logger.error("No session_id provided")
                    raise ValueError("session_id is empty")
                if not isinstance(session_id, int):
                    session_id = int(session_id)
                session = ChatSession.objects.get(id=session_id)
                ChatMessage.objects.create(session=session, sender=sender, text=text)
                if sender == 'user' and session.title == 'Untitled':
                    session.title = text[:40]
                    session.save()
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid session_id: {session_id}, error: {str(e)}")
            raise
        except ChatSession.DoesNotExist:
            logger.error(f"ChatSession with id {session_id} does not exist in schema {self.tenant_schema}")
            raise


