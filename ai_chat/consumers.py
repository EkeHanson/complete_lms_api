# ai_chat/consumers.py
import json
import urllib.parse
from channels.generic.websocket import AsyncWebsocketConsumer
from django_tenants.utils import schema_context
from courses.utils import retrieve_documents, generate_ai_response
from core.models import Tenant
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from channels.db import database_sync_to_async

class AIChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Parse query parameters
        query_string = self.scope["query_string"].decode()
        params = urllib.parse.parse_qs(query_string)
        tenant_id = params.get('tenant_id', [''])[0]
        access_token = params.get('token', [''])[0]

        if not tenant_id or not access_token:
            await self.close()
            return

        try:
            # Get tenant asynchronously
            self.tenant = await self.get_tenant(tenant_id)
            self.tenant_schema = self.tenant.schema_name
            
            # Authenticate user asynchronously
            self.user = await self.authenticate_user(access_token)
            
            await self.accept()
        except (Tenant.DoesNotExist, AuthenticationFailed) as e:
            print(f"Authentication failed: {str(e)}")
            await self.close()
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            await self.close()

    @database_sync_to_async
    def get_tenant(self, tenant_id):
        return Tenant.objects.get(id=tenant_id)

    @database_sync_to_async
    def authenticate_user(self, access_token):
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(access_token)
        return jwt_auth.get_user(validated_token)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            query = data.get('message')
            
            if query:
                # Use schema context for processing
                with schema_context(self.tenant_schema):
                    # Make these utils async or use sync_to_async if they do DB operations
                    documents = retrieve_documents(query, self.tenant_schema)
                    response = generate_ai_response(query, documents)
                    
                await self.send(text_data=json.dumps({'message': response}))
                
        except Exception as e:
            await self.send(text_data=json.dumps({'error': str(e)}))