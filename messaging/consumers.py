# # messaging/consumers.py
# import json
# from channels.generic.websocket import AsyncWebsocketConsumer
# from channels.db import database_sync_to_async
# from django.contrib.auth.models import AnonymousUser
# from .models import MessageRecipient
# from django.utils import timezone

# class MessageConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         self.user = self.scope['user']
#         if isinstance(self.user, AnonymousUser):
#             await self.close()
#         else:
#             self.group_name = f'user_{self.user.id}'
#             await self.channel_layer.group_add(
#                 self.group_name,
#                 self.channel_name
#             )
#             await self.accept()

#     async def disconnect(self, close_code):
#         if hasattr(self, 'group_name'):
#             await self.channel_layer.group_discard(
#                 self.group_name,
#                 self.channel_name
#             )

#     async def receive(self, text_data):
#         text_data_json = json.loads(text_data)
#         message_type = text_data_json.get('type')
        
#         if message_type == 'mark_as_read':
#             message_id = text_data_json.get('message_id')
#             await self.mark_message_as_read(message_id)

#     async def new_message(self, event):
#         await self.send(text_data=json.dumps({
#             'type': 'new_message',
#             'message': event['message']
#         }))

#     async def message_read(self, event):
#         await self.send(text_data=json.dumps({
#             'type': 'message_read',
#             'message_id': event['message_id']
#         }))

#     @database_sync_to_async
#     def mark_message_as_read(self, message_id):
#         MessageRecipient.objects.filter(
#             message_id=message_id,
#             recipient=self.user
#         ).update(read=True, read_at=timezone.now())

# messaging/consumers.py
import json
import logging
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from django_tenants.utils import tenant_context

from .models import MessageRecipient

logger = logging.getLogger("messaging.socket")


class MessageConsumer(AsyncWebsocketConsumer):
    # ------------------------------------------------------------------ connect
    async def connect(self):
        self.user = self.scope.get("user")
        self.tenant = self.scope.get("tenant")

        # Reject if anonymous or tenant missing
        if isinstance(self.user, AnonymousUser) or self.tenant is None:
            await self.close()
            return

        # Use tenant schema in the group name to guarantee isolation
        self.group_name = f"{self.tenant.schema_name}_user_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    # ---------------------------------------------------------------- disconnect
    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # ---------------------------------------------------------------- receive
    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get("type") == "mark_as_read":
            await self.mark_message_as_read(data.get("message_id"))

    # ---------------------------------------------------------------- send events
    async def new_message(self, event):
        """Send new message to client"""
        await self.send(text_data=json.dumps({"type": "new_message", "message": event["message"]}))

    async def message_read(self, event):
        """Notify sender that message was read"""
        await self.send(text_data=json.dumps({"type": "message_read", "message_id": event["message_id"], "reader_id": event["reader_id"]}))

    # ---------------------------------------------------------------- helper
    @database_sync_to_async
    def mark_message_as_read(self, message_id: str | int | None):
        """Runs in synchronous thread‑pool; switch to tenant schema before touching DB."""
        if not message_id:
            return

        try:
            with tenant_context(self.tenant):
                updated = (
                    MessageRecipient.objects.filter(message_id=message_id, recipient=self.user)
                    .update(read=True, read_at=timezone.now())
                )
                logger.debug(
                    "Tenant %s – user %s marked message %s as read (%s rows updated)",
                    self.tenant.schema_name,
                    self.user.id,
                    message_id,
                    updated,
                )
        except Exception as exc:
            logger.exception("Failed to mark message as read: %s", exc)


