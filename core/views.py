import logging
import jwt
from django.conf import settings
from django.db import transaction, connection
from django_tenants.utils import tenant_context, get_public_schema_name
from rest_framework import viewsets, status, generics, serializers
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from .models import Tenant, Module, TenantConfig, Branch
from .serializers import TenantSerializer, ModuleSerializer, TenantConfigSerializer, BranchSerializer
from payments.models import PaymentGateway, SiteConfig, PaymentConfig
from payments.payment_configs import PAYMENT_GATEWAY_CONFIGS

logger = logging.getLogger('core')

class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]

    def get_tenant_from_token(self, request):
        """Extract tenant from JWT token or request.tenant."""
        try:
            if hasattr(request, 'tenant') and request.tenant:
                logger.debug(f"Tenant from request: {request.tenant.schema_name}")
                return request.tenant
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                logger.warning("No valid Bearer token provided")
                raise ValueError("Invalid token format")
            token = auth_header.split(' ')[1]
            decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            tenant_id = decoded_token.get('tenant_id')
            schema_name = decoded_token.get('schema_name')
            if tenant_id:
                tenant = Tenant.objects.get(id=tenant_id)
                return tenant
            elif schema_name:
                tenant = Tenant.objects.get(schema_name=schema_name)
                return tenant
            else:
                logger.warning("No tenant_id or schema_name in token")
                raise ValueError("Tenant not specified in token")
        except Tenant.DoesNotExist:
            logger.error("Tenant not found")
            raise serializers.ValidationError("Tenant not found")
        except jwt.InvalidTokenError:
            logger.error("Invalid JWT token")
            raise serializers.ValidationError("Invalid token")
        except Exception as e:
            logger.error(f"Error extracting tenant: {str(e)}")
            raise serializers.ValidationError(f"Error extracting tenant: {str(e)}")

    def get_queryset(self):
        """Filter queryset to the authenticated user's tenant for standard operations."""
        tenant = self.get_tenant_from_token(self.request)
        connection.set_schema(tenant.schema_name)
        with connection.cursor() as cursor:
            cursor.execute("SHOW search_path;")
            search_path = cursor.fetchone()[0]
            logger.debug(f"Database search_path: {search_path}")
        return Tenant.objects.filter(id=tenant.id).prefetch_related('domain_set')

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def all(self, request):
        """List all tenants in the system (superuser only)."""
        try:
            connection.set_schema(get_public_schema_name())
            queryset = Tenant.objects.all().prefetch_related('domain_set')
            serializer = self.get_serializer(queryset, many=True)
            logger.info(f"Superuser {request.user.email} retrieved all tenants: {[t['id'] for t in serializer.data]}")
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Failed to list all tenants: {str(e)}")
            return Response({"detail": f"Failed to list tenants: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def create_with_domains(self, request):
        """Create a tenant with primary and secondary domains."""
        serializer = TenantSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    tenant = serializer.save()
                    logger.info(f"Tenant created with domains: {tenant.name} (schema: {tenant.schema_name})")
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Failed to create tenant with domains: {str(e)}")
                return Response({"detail": f"Failed to create tenant: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        logger.error(f"Validation error: {serializer.errors}")
        return Response({"detail": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer):
        """Create a new tenant and prepopulate payment gateways, site config, and payment config."""
        try:
            with transaction.atomic():
                tenant = serializer.save()
                logger.info(f"Tenant created: {tenant.name} (schema: {tenant.schema_name})")
                # Ensure schema is created before prepopulating
                tenant.create_schema(check_if_exists=True)
                with tenant_context(tenant):
                    # Create default payment gateways
                    payment_configs = []
                    for gateway_data in PAYMENT_GATEWAY_CONFIGS:
                        PaymentGateway.objects.create(
                            name=gateway_data['name'],
                            description=gateway_data['description'],
                            is_active=gateway_data['is_active'],
                            is_test_mode=gateway_data['is_test_mode'],
                            is_default=gateway_data['is_default']
                        )
                        logger.info(f"Created payment gateway {gateway_data['name']} for tenant {tenant.schema_name}")
                        # Prepare config for PaymentConfig
                        payment_configs.append({
                            'method': gateway_data['name'],
                            'config': gateway_data['config'],
                            'isActive': gateway_data['is_active']
                        })

                    # Create default site configuration
                    SiteConfig.objects.create(
                        currency='USD',
                        title='US Dollar'
                    )
                    logger.info(f"Created default site configuration for tenant {tenant.schema_name}")

                    # Create default payment configuration
                    PaymentConfig.objects.create(
                        configs=payment_configs
                    )
                    logger.info(f"Created default payment configuration for tenant {tenant.schema_name}")

                return tenant
        except Exception as e:
            logger.error(f"Failed to create tenant or prepopulate configurations: {str(e)}")
            raise serializers.ValidationError(f"Failed to create tenant or prepopulate configurations: {str(e)}")

    def list(self, request, *args, **kwargs):
        """List tenants (only the authenticated tenant)."""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        logger.info(f"Listing tenants: {[t['id'] for t in serializer.data]} for tenant {request.tenant.schema_name}")
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """Retrieve a specific tenant (only if it matches the authenticated tenant)."""
        tenant = self.get_tenant_from_token(request)
        instance = self.get_object()
        if instance.id != tenant.id:
            logger.warning(f"Unauthorized access attempt to tenant {instance.id} by tenant {tenant.id}")
            return Response({"detail": "Not authorized to access this tenant"}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(instance)
        logger.info(f"Retrieving tenant: {instance.id} for tenant {tenant.schema_name}")
        return Response(serializer.data)

    def perform_update(self, serializer):
        """Update a tenant within the authenticated tenant's context."""
        tenant = self.get_tenant_from_token(self.request)
        instance = self.get_object()
        if instance.id != tenant.id:
            logger.error(f"Unauthorized update attempt on tenant {instance.id} by tenant {tenant.id}")
            raise serializers.ValidationError("Not authorized to update this tenant")
        with tenant_context(tenant):
            serializer.save()
        logger.info(f"Tenant updated: {instance.name} for tenant {tenant.schema_name}")

    def perform_destroy(self, instance):
        """Delete a tenant within the authenticated tenant's context."""
        tenant = self.get_tenant_from_token(self.request)
        if instance.id != tenant.id:
            logger.error(f"Unauthorized delete attempt on tenant {instance.id} by tenant {tenant.id}")
            raise serializers.ValidationError("Not authorized to delete this tenant")
        with tenant_context(tenant):
            instance.delete()
        logger.info(f"Tenant deleted: {instance.name} for tenant {tenant.schema_name}")

class BranchListCreateView(generics.ListCreateAPIView):
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated]

    def get_tenant(self, request):
        try:
            if hasattr(request.user, 'tenant') and request.user.tenant:
                logger.debug(f"Tenant from user: {request.user.tenant.schema_name}")
                return request.user.tenant
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                logger.warning("No valid Bearer token provided")
                raise ValueError("Invalid token format")
            token = auth_header.split(' ')[1]
            decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            tenant_id = decoded_token.get('tenant_id')
            schema_name = decoded_token.get('tenant_schema')
            if tenant_id:
                tenant = Tenant.objects.get(id=tenant_id)
                logger.debug(f"Tenant extracted from token by ID: {tenant.schema_name}")
                return tenant
            elif schema_name:
                tenant = Tenant.objects.get(schema_name=schema_name)
                logger.debug(f"Tenant extracted from token by schema: {tenant.schema_name}")
                return tenant
            else:
                logger.warning("No tenant_id or schema_name in token")
                raise ValueError("Tenant not specified in token")
        except Tenant.DoesNotExist:
            logger.error("Tenant not found")
            raise serializers.ValidationError("Tenant not found")
        except jwt.InvalidTokenError:
            logger.error("Invalid JWT token")
            raise serializers.ValidationError("Invalid token")
        except Exception as e:
            logger.error(f"Error extracting tenant: {str(e)}")
            raise serializers.ValidationError(f"Error extracting tenant: {str(e)}")

    def get_queryset(self):
        tenant = self.get_tenant(self.request)
        connection.set_schema(tenant.schema_name)
        with connection.cursor() as cursor:
            cursor.execute("SHOW search_path;")
            search_path = cursor.fetchone()[0]
            logger.debug(f"Database search_path: {search_path}")
        with tenant_context(tenant):
            return Branch.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        tenant = self.get_tenant(self.request)
        try:
            with tenant_context(tenant):
                with transaction.atomic():
                    branch = serializer.save()
                    logger.info(f"Branch created: {branch.name} for tenant {tenant.schema_name}")
        except Exception as e:
            logger.error(f"Error creating branch for tenant {tenant.schema_name}: {str(e)}")
            raise serializers.ValidationError(f"Error creating branch: {str(e)}")

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            logger.info(f"Retrieved {queryset.count()} branches for tenant {request.user.tenant.schema_name}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error listing branches for tenant {request.user.tenant.schema_name}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BranchDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_tenant(self, request):
        try:
            if hasattr(request.user, 'tenant') and request.user.tenant:
                logger.debug(f"Tenant from user: {request.user.tenant.schema_name}")
                return request.user.tenant
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                logger.warning("No valid Bearer token provided")
                raise ValueError("Invalid token format")
            token = auth_header.split(' ')[1]
            decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            tenant_id = decoded_token.get('tenant_id')
            schema_name = decoded_token.get('tenant_schema')
            if tenant_id:
                tenant = Tenant.objects.get(id=tenant_id)
                logger.debug(f"Tenant extracted from token by ID: {tenant.schema_name}")
                return tenant
            elif schema_name:
                tenant = Tenant.objects.get(schema_name=schema_name)
                logger.debug(f"Tenant extracted from token by schema: {tenant.schema_name}")
                return tenant
            else:
                logger.warning("No tenant_id or schema_name in token")
                raise ValueError("Tenant not specified in token")
        except Tenant.DoesNotExist:
            logger.error("Tenant not found")
            raise serializers.ValidationError("Tenant not found")
        except jwt.InvalidTokenError:
            logger.error("Invalid JWT token")
            raise serializers.ValidationError("Invalid token")
        except Exception as e:
            logger.error(f"Error extracting tenant: {str(e)}")
            raise serializers.ValidationError(f"Error extracting tenant: {str(e)}")

    def get_queryset(self):
        tenant = self.get_tenant(self.request)
        connection.set_schema(tenant.schema_name)
        with connection.cursor() as cursor:
            cursor.execute("SHOW search_path;")
            search_path = cursor.fetchone()[0]
            logger.debug(f"Database search_path: {search_path}")
        with tenant_context(tenant):
            return Branch.objects.filter(tenant=tenant)

    def perform_update(self, serializer):
        tenant = self.get_tenant(self.request)
        try:
            with tenant_context(tenant):
                with transaction.atomic():
                    branch = serializer.save()
                    logger.info(f"Branch updated: {branch.name} for tenant {tenant.schema_name}")
        except Exception as e:
            logger.error(f"Error updating branch for tenant {tenant.schema_name}: {str(e)}")
            raise serializers.ValidationError(f"Error updating branch: {str(e)}")

    def perform_destroy(self, instance):
        tenant = self.get_tenant(self.request)
        try:
            with tenant_context(tenant):
                with transaction.atomic():
                    instance.delete()
                    logger.info(f"Branch deleted: {instance.name} for tenant {tenant.schema_name}")
        except Exception as e:
            logger.error(f"Error deleting branch for tenant {tenant.schema_name}: {str(e)}")
            raise serializers.ValidationError(f"Error deleting branch: {str(e)}")

class ModuleListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        tenant = request.user.tenant
        with tenant_context(tenant):
            modules = Module.objects.filter(is_active=True)
            serializer = ModuleSerializer(modules, many=True, context={'request': request})
            logger.info(f"Retrieved {modules.count()} modules for tenant {tenant.schema_name}")
            return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        tenant = request.user.tenant
        serializer = ModuleSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            try:
                with tenant_context(tenant):
                    with transaction.atomic():
                        module = serializer.save()
                        logger.info(f"Module created: {module.name} for tenant {tenant.schema_name}")
                        return Response(serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Error creating module for tenant {tenant.schema_name}: {str(e)}")
                return Response({
                    'status': 'error',
                    'message': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        logger.error(f"Validation error for tenant {tenant.schema_name}: {serializer.errors}")
        return Response({
            'status': 'error',
            'message': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class TenantConfigView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = request.user.tenant
        with tenant_context(tenant):
            try:
                config = TenantConfig.objects.get(tenant=tenant)
                serializer = TenantConfigSerializer(config)
                logger.info(f"Fetched TenantConfig for tenant {tenant.schema_name}")
                return Response(serializer.data, status=status.HTTP_200_OK)
            except TenantConfig.DoesNotExist:
                default_templates = {
                    'interviewScheduling': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'We’re pleased to invite you to an interview for the [Position] role at [Company].\n'
                            'Please let us know your availability so we can confirm a convenient time.\n\n'
                            'Best regards,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'interviewRescheduling': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'Due to unforeseen circumstances, we need to reschedule your interview originally set for [Old Date/Time]. '
                            'Kindly share a few alternative slots that work for you.\n\n'
                            'Thanks for your understanding,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'interviewRejection': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'Thank you for taking the time to interview. After careful consideration, '
                            'we have decided not to move forward.\n\n'
                            'Best wishes,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'interviewAcceptance': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'Congratulations! We are moving you to the next stage. We’ll follow up with next steps.\n\n'
                            'Looking forward,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'jobRejection': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'Thank you for applying. Unfortunately, we’ve chosen another candidate at this time.\n\n'
                            'Kind regards,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'jobAcceptance': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'We’re excited to offer you the [Position] role at [Company]! '
                            'Please find the offer letter attached.\n\n'
                            'Welcome aboard!\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    }
                }
                try:
                    with transaction.atomic():
                        config = TenantConfig.objects.create(
                            tenant=tenant,
                            email_templates=default_templates
                        )
                        logger.info(f"Created TenantConfig for tenant {tenant.schema_name} with default email templates")
                        serializer = TenantConfigSerializer(config)
                        return Response(serializer.data, status=status.HTTP_201_CREATED)
                except Exception as e:
                    logger.error(f"Error creating TenantConfig for tenant {tenant.schema_name}: {str(e)}")
                    return Response(
                        {'status': 'error', 'message': 'Failed to create tenant configuration'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

    def patch(self, request):
        tenant = request.user.tenant
        with tenant_context(tenant):
            try:
                config = TenantConfig.objects.get(tenant=tenant)
                current_templates = config.email_templates or {}
                incoming_templates = request.data.get('email_templates', {})
                updated_templates = { **current_templates, **incoming_templates }
                updated_data = { **request.data, 'email_templates': updated_templates }
                serializer = TenantConfigSerializer(config, data=updated_data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    logger.info(f"Tenant config updated for tenant {tenant.schema_name}")
                    return Response(serializer.data, status=status.HTTP_200_OK)
                logger.error(f"Validation error for tenant {tenant.schema_name}: {serializer.errors}")
                return Response({'status': 'error', 'message': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            except TenantConfig.DoesNotExist:
                logger.error(f"Tenant config not found for tenant {tenant.schema_name}")
                return Response({'status': 'error', 'message': 'Tenant config not found'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        tenant = request.user.tenant
        with tenant_context(tenant):
            try:
                if TenantConfig.objects.filter(tenant=tenant).exists():
                    logger.warning(f"Tenant config already exists for tenant {tenant.schema_name}")
                    return Response({'status': 'error', 'message': 'Tenant config already exists'}, status=status.HTTP_400_BAD_REQUEST)
                serializer = TenantConfigSerializer(data=request.data)
                if serializer.is_valid():
                    serializer.save(tenant=tenant)
                    logger.info(f"Tenant config created for tenant {tenant.schema_name}")
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                logger.error(f"Validation error for tenant {tenant.schema_name}: {serializer.errors}")
                return Response({'status': 'error', 'message': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                logger.error(f"Error creating tenant config for tenant {tenant.schema_name}: {str(e)}")
                return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)