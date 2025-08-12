# lumina_care/websocket_middleware.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

class WebSocketJWTAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        token = None

        # Extract token from query string
        for param in query_string.split('&'):
            if param.startswith('token='):
                token = param.split('=')[1]
                break

        if token:
            try:
                # Use async database access
                scope['user'] = await self.authenticate_token(token)
            except AuthenticationFailed:
                scope['user'] = AnonymousUser()
        else:
            scope['user'] = AnonymousUser()
        
        return await self.app(scope, receive, send)

    @database_sync_to_async
    def authenticate_token(self, token):
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        return jwt_auth.get_user(validated_token)