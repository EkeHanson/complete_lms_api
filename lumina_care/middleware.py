# # lumina_care/middleware.py
# from django_tenants.middleware import TenantMainMiddleware
# from django_tenants.utils import get_public_schema_name
# from core.models import Domain, Tenant
# from django.http import Http404
# from django.db import connection
# import logging
# from rest_framework_simplejwt.authentication import JWTAuthentication

# logger = logging.getLogger(__name__)
# # lumina_care/middleware.py
# from django_tenants.middleware import TenantMainMiddleware
# from django_tenants.utils import get_public_schema_name
# from core.models import Domain, Tenant
# from django.http import Http404, JsonResponse
# from django.db import connection
# import logging
# from rest_framework_simplejwt.authentication import JWTAuthentication

# logger = logging.getLogger(__name__)

# class CustomTenantMiddleware(TenantMainMiddleware):
#     def process_request(self, request):
#         # Skip tenant processing for requests with skip header
#         if request.headers.get('X-Skip-Interceptor') == 'true':
#             return
#         logger.debug(f"Processing request: {request.path}, Host: {request.get_host()}")
#         public_paths = [
#             '/api/tenants/', '/api/docs/', '/api/schema/',
#             '/api/token/', '/accounts/', '/api/social/callback/', '/api/admin/create/'
#         ]
#         if any(request.path.startswith(path) for path in public_paths):
#             try:
#                 public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
#                 request.tenant = public_tenant
#                 logger.info(f"Using public tenant for public endpoint: {public_tenant.schema_name}")
#                 with connection.cursor() as cursor:
#                     cursor.execute("SHOW search_path;")
#                     logger.debug(f"Search_path: {cursor.fetchone()[0]}")
#                 return
#             except Tenant.DoesNotExist:
#                 logger.error("Public tenant does not exist")
#                 if request.path.startswith('/api/'):
#                     return JsonResponse({'error': 'Public tenant not configured'}, status=404)
#                 raise Http404("Public tenant not configured")

#         # Try JWT authentication
#         try:
#             auth = JWTAuthentication().authenticate(request)
#             if auth:
#                 user, token = auth
#                 tenant_id = token.get('tenant_id')
#                 if tenant_id:
#                     tenant = Tenant.objects.get(id=tenant_id)
#                     request.tenant = tenant
#                     logger.info(f"Tenant set from JWT: {tenant.schema_name}")
#                     with connection.cursor() as cursor:
#                         cursor.execute("SHOW search_path;")
#                         logger.debug(f"Search_path: {cursor.fetchone()[0]}")
#                     return
#                 else:
#                     logger.warning("No tenant_id in JWT token")
#         except Exception as e:
#             logger.debug(f"JWT tenant resolution failed: {str(e)}")

#         # Fallback to hostname
#         hostname = request.get_host().split(':')[0]
#         domain = Domain.objects.filter(domain=hostname).first()
#         if domain:
#             request.tenant = domain.tenant
#             logger.info(f"Tenant set from domain: {domain.tenant.schema_name}")
#             with connection.cursor() as cursor:
#                 cursor.execute("SHOW search_path;")
#                 logger.debug(f"Search_path: {cursor.fetchone()[0]}")
#             return

#         # Development fallback
#         if hostname in ['127.0.0.1', 'localhost']:
#             try:
#                 tenant = Tenant.objects.get(schema_name='abraham_ekene_onwon')
#                 request.tenant = tenant
#                 logger.info(f"Using tenant {tenant.schema_name} for local development")
#                 with connection.cursor() as cursor:
#                     cursor.execute("SHOW search_path;")
#                     logger.debug(f"Search_path: {cursor.fetchone()[0]}")
#                 return
#             except Tenant.DoesNotExist:
#                 logger.error("Development tenant abraham_ekene_onwon does not exist")
#                 if request.path.startswith('/api/'):
#                     return JsonResponse({'error': 'Development tenant not configured'}, status=404)
#                 raise Http404("Development tenant not configured")

#         logger.error(f"No tenant found for hostname: {hostname}")
#         if request.path.startswith('/api/'):
#             return JsonResponse({'error': f'No tenant found for hostname: {hostname}'}, status=404)
#         raise Http404(f"No tenant found for hostname: {hostname}")

# # class CustomTenantMiddleware(TenantMainMiddleware):
#     def process_request(self, request):
#         logger.debug(f"Processing request: {request.path}, Host: {request.get_host()}")
#         public_paths = [
#             '/api/tenants/', '/api/docs/', '/api/schema/',
#             '/api/token/', '/accounts/', '/api/social/callback/', '/api/admin/create/'
#         ]
#         if any(request.path.startswith(path) for path in public_paths):
#             try:
#                 public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
#                 request.tenant = public_tenant
#                 logger.info(f"Using public tenant for public endpoint: {public_tenant.schema_name}")
#                 with connection.cursor() as cursor:
#                     cursor.execute("SHOW search_path;")
#                     logger.debug(f"Search_path: {cursor.fetchone()[0]}")
#                 return
#             except Tenant.DoesNotExist:
#                 logger.error("Public tenant does not exist")
#                 raise Http404("Public tenant not configured")

#         # Try JWT authentication
#         try:
#             auth = JWTAuthentication().authenticate(request)
#             if auth:
#                 user, token = auth
#                 tenant_id = token.get('tenant_id')
#                 if tenant_id:
#                     tenant = Tenant.objects.get(id=tenant_id)
#                     request.tenant = tenant
#                     logger.info(f"Tenant set from JWT: {tenant.schema_name}")
#                     with connection.cursor() as cursor:
#                         cursor.execute("SHOW search_path;")
#                         logger.debug(f"Search_path: {cursor.fetchone()[0]}")
#                     return
#                 else:
#                     logger.warning("No tenant_id in JWT token")
#         except Exception as e:
#             logger.debug(f"JWT tenant resolution failed: {str(e)}")

#         # Fallback to hostname
#         hostname = request.get_host().split(':')[0]
#         domain = Domain.objects.filter(domain=hostname).first()
#         if domain:
#             request.tenant = domain.tenant
#             logger.info(f"Tenant set from domain: {domain.tenant.schema_name}")
#             with connection.cursor() as cursor:
#                 cursor.execute("SHOW search_path;")
#                 logger.debug(f"Search_path: {cursor.fetchone()[0]}")
#             return

#         # Development fallback
#         if hostname in ['127.0.0.1', 'localhost']:
#             try:
#                 tenant = Tenant.objects.get(schema_name='abraham_ekene_onwon')
#                 request.tenant = tenant
#                 logger.info(f"Using tenant {tenant.schema_name} for local development")
#                 with connection.cursor() as cursor:
#                     cursor.execute("SHOW search_path;")
#                     logger.debug(f"Search_path: {cursor.fetchone()[0]}")
#                 return
#             except Tenant.DoesNotExist:
#                 logger.error("Development tenant abraham_ekene_onwon does not exist")
#                 raise Http404("Development tenant not configured")

#         logger.error(f"No tenant found for hostname: {hostname}")
#         raise Http404(f"No tenant found for hostname: {hostname}")

from django_tenants.middleware import TenantMainMiddleware
from django_tenants.utils import get_public_schema_name
from core.models import Domain, Tenant
from django.http import Http404, JsonResponse
from django.db import connection
import logging
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import UntypedToken
from django.conf import settings

logger = logging.getLogger(__name__)
class CustomTenantMiddleware(TenantMainMiddleware):
    def process_request(self, request):
        if request.headers.get('X-Skip-Interceptor') == 'true':
            logger.debug("Skipping tenant processing for X-Skip-Interceptor request")
            return

        logger.debug(f"Processing request: {request.path}, Host: {request.get_host()}")
        public_paths = [
            '/api/tenants/', '/api/docs/', '/api/schema/',
            '/api/token/', '/accounts/', '/api/social/callback/', '/api/admin/create/'
        ]

        if request.path == '/api/token/refresh/':
            logger.debug("Handling token refresh request")
            refresh_token = request.COOKIES.get('refresh_token')
            if refresh_token:
                try:
                    untyped_token = UntypedToken(refresh_token)
                    tenant_id = untyped_token.payload.get('tenant_id')
                    if tenant_id:
                        tenant = Tenant.objects.get(id=tenant_id)
                        request.tenant = tenant
                        connection.set_schema(tenant.schema_name)
                        logger.info(f"[{tenant.schema_name}] Tenant set from refresh token for token refresh")
                        return
                except Exception as e:
                    logger.warning(f"Failed to get tenant from refresh token: {str(e)}")

        if any(request.path.startswith(path) for path in public_paths):
            try:
                public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
                request.tenant = public_tenant
                logger.info(f"Using public tenant for public endpoint: {public_tenant.schema_name}")
                with connection.cursor() as cursor:
                    cursor.execute("SHOW search_path;")
                    logger.debug(f"Search_path: {cursor.fetchone()[0]}")
                return
            except Tenant.DoesNotExist:
                logger.error("Public tenant does not exist")
                if request.path.startswith('/api/'):
                    return JsonResponse({'error': 'Public tenant not configured'}, status=404)
                raise Http404("Public tenant not configured")

        try:
            auth = JWTAuthentication().authenticate(request)
            if auth:
                user, token = auth
                tenant_id = token.get('tenant_id')
                if tenant_id:
                    tenant = Tenant.objects.get(id=tenant_id)
                    request.tenant = tenant
                    logger.info(f"Tenant set from JWT: {tenant.schema_name}")
                    with connection.cursor() as cursor:
                        cursor.execute("SHOW search_path;")
                        logger.debug(f"Search_path: {cursor.fetchone()[0]}")
                    return
                else:
                    logger.warning("No tenant_id in JWT token")
        except Exception as e:
            logger.debug(f"JWT tenant resolution failed: {str(e)}")

        hostname = request.get_host().split(':')[0]
        domain = Domain.objects.filter(domain=hostname).first()
        if domain:
            request.tenant = domain.tenant
            logger.info(f"Tenant set from domain: {domain.tenant.schema_name}")
            with connection.cursor() as cursor:
                cursor.execute("SHOW search_path;")
                logger.debug(f"Search_path: {cursor.fetchone()[0]}")
            return

        if hostname in ['127.0.0.1', 'localhost']:
            try:
                tenant = Tenant.objects.get(schema_name='proliance')  # Use correct tenant
                request.tenant = tenant
                logger.info(f"Using tenant {tenant.schema_name} for local development")
                with connection.cursor() as cursor:
                    cursor.execute("SHOW search_path;")
                    logger.debug(f"Search_path: {cursor.fetchone()[0]}")
                return
            except Tenant.DoesNotExist:
                logger.error("Development tenant proliance does not exist")
                if request.path.startswith('/api/'):
                    return JsonResponse({'error': 'Development tenant not configured'}, status=404)
                raise Http404("Development tenant not configured")

        logger.error(f"No tenant found for hostname: {hostname}")
        if request.path.startswith('/api/'):
            return JsonResponse({'error': f'No tenant found for hostname: {hostname}'}, status=404)
        raise Http404(f"No tenant found for hostname: {hostname}")

    def process_response(self, request, response):
        # Ensure CORS headers are preserved
        if hasattr(request, 'tenant') and request.tenant:
            response['Access-Control-Allow-Origin'] = settings.FRONTEND_URL
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Access-Control-Expose-Headers'] = 'Set-Cookie'
            logger.debug(f"[{request.tenant.schema_name}] Response headers: {dict(response.headers)}")
        return response