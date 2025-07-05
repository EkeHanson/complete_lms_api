import logging
from core.models import Tenant
from django.db import connection, transaction
from django_filters.rest_framework import DjangoFilterBackend
from django_tenants.utils import tenant_context
from rest_framework import generics, status
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import JobRequisition
from .serializers import JobRequisitionSerializer
from .permissions import IsSubscribedAndAuthorized

logger = logging.getLogger('talent_engine')

class JobRequisitionBulkDeleteView(generics.GenericAPIView):
    # permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]  # Added permission
    permission_classes = [IsAuthenticated]  # Added permission

    def post(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            logger.warning("No IDs provided for bulk soft delete")
            return Response({"detail": "No IDs provided."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            tenant = request.tenant
            with tenant_context(tenant):
                if not all(isinstance(id, str) and id.startswith('PRO-') for id in ids):
                    logger.warning(f"Invalid ID format in: {ids}")
                    return Response({"detail": "All IDs must be in PRO-XXXX format."}, status=status.HTTP_400_BAD_REQUEST)
                requisitions = JobRequisition.active_objects.filter(tenant=tenant, id__in=ids)
                count = requisitions.count()
                if count == 0:
                    logger.warning("No active requisitions found for provided IDs")
                    return Response({"detail": "No requisitions found."}, status=status.HTTP_404_NOT_FOUND)
                with transaction.atomic():
                    for requisition in requisitions:
                        requisition.soft_delete()
            #logger.info(f"Soft-deleted {count} job requisitions for tenant {tenant.schema_name}")
            return Response({"detail": f"Soft-deleted {count} requisition(s)."}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Bulk soft delete failed: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class JobRequisitionListCreateView(generics.ListCreateAPIView):
    serializer_class = JobRequisitionSerializer
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'role']
    search_fields = ['title', 'status', 'requested_by__email', 'role']

    def get_queryset(self):
        tenant = self.request.tenant
        #logger.debug(f"User: {self.request.user}, Tenant: {tenant.schema_name}")
        connection.set_schema(tenant.schema_name)
        #logger.debug(f"Schema set to: {connection.schema_name}")
        with connection.cursor() as cursor:
            cursor.execute("SHOW search_path;")
            search_path = cursor.fetchone()[0]
            #logger.debug(f"Database search_path: {search_path}")
        queryset = JobRequisition.active_objects.filter(tenant=tenant)
        #logger.debug(f"Query: {queryset.query}")
        return queryset

    def perform_create(self, serializer):
        tenant = self.request.tenant
        connection.set_schema(tenant.schema_name)
        serializer.save(tenant=tenant)
        #logger.info(f"Job requisition created: {serializer.validated_data['title']} for tenant {tenant.schema_name}")

class JobRequisitionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = JobRequisitionSerializer
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]
    lookup_field = 'id'

    def get_queryset(self):
        tenant = self.request.tenant
        connection.set_schema(tenant.schema_name)
        #logger.debug(f"Schema set to: {connection.schema_name}")
        with connection.cursor() as cursor:
            cursor.execute("SHOW search_path;")
            search_path = cursor.fetchone()[0]
            #logger.debug(f"Database search_path: {search_path}")
        queryset = JobRequisition.active_objects.filter(tenant=tenant)
        #logger.debug(f"Query: {queryset.query}")
        return queryset

    def perform_update(self, serializer):
        tenant = self.request.tenant
        with tenant_context(tenant):
            serializer.save()
        #logger.info(f"Job requisition updated: {serializer.instance.title} for tenant {tenant.schema_name}")

    def perform_destroy(self, instance):
        tenant = self.request.tenant
        with tenant_context(tenant):
            instance.soft_delete()
        #.info(f"Job requisition soft-deleted: {instance.title} for tenant {tenant.schema_name}")

class JobRequisitionByLinkView(generics.RetrieveAPIView):
    serializer_class = JobRequisitionSerializer
    lookup_field = 'unique_link'
    permission_classes = []

    def get_queryset(self):
        unique_link = self.kwargs.get('unique_link', '')
        if not unique_link or '-' not in unique_link:
            #logger.warning(f"Invalid unique_link format: {unique_link}")
            return JobRequisition.objects.none()

        try:
            tenant_schema = unique_link.split('-')[0]
            tenant = Tenant.objects.get(schema_name=tenant_schema)
            #logger.debug(f"Tenant extracted: {tenant.schema_name}")
            connection.set_schema(tenant.schema_name)
            #logger.debug(f"Schema set to: {connection.schema_name}")
            with connection.cursor() as cursor:
                cursor.execute("SHOW search_path;")
                search_path = cursor.fetchone()[0]
                #logger.debug(f"Database search_path: {search_path}")
            queryset = JobRequisition.active_objects.filter(tenant=tenant, publish_status=True)
            #logger.debug(f"Query: {queryset.query}")
            return queryset
        except Tenant.DoesNotExist:
            logger.warning(f"Tenant {tenant_schema} not found")
            return JobRequisition.objects.none()
        except Exception as e:
            logger.error(f"Error setting tenant context: {str(e)}")
            return JobRequisition.objects.none()

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            tenant_schema = instance.tenant.schema_name
            #logger.info(f"Job requisition accessed via link: {instance.title} for tenant {tenant_schema}")
            return Response(serializer.data)
        except JobRequisition.DoesNotExist:
            logger.warning(f"Job with unique_link {kwargs.get('unique_link')} not found or not published")
            return Response({"detail": "Job not found or not published"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error retrieving job requisition: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SoftDeletedJobRequisitionsView(generics.ListAPIView):
    serializer_class = JobRequisitionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.tenant
        # print("tenant")
        # print(tenant)
        # print("tenant")
        if not tenant:
            logger.error("No tenant associated with the request")
            raise generics.ValidationError("Tenant not found.")

        #logger.debug(f"User: {self.request.user}, Tenant: {tenant.schema_name}")
        connection.set_schema(tenant.schema_name)
        with tenant_context(tenant):
            queryset = JobRequisition.objects.filter(tenant=tenant, is_deleted=True)
            #logger.debug(f"Query: {queryset.query}")
            return queryset

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            #logger.info(f"Retrieved {queryset.count()} soft-deleted job requisitions for tenant {request.tenant.schema_name}")
            return Response({
                "detail": f"Retrieved {queryset.count()} soft-deleted requisition(s).",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error listing soft-deleted job requisitions for tenant {request.tenant.schema_name}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RecoverSoftDeletedJobRequisitionsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]

    def post(self, request, *args, **kwargs):
        #logger.debug(f"Received POST request to recover job requisitions: {request.data}")
        try:
            tenant = request.tenant
            if not tenant:
                logger.error("No tenant associated with the request")
                return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)

            ids = request.data.get('ids', [])
            if not ids:
                logger.warning("No requisition IDs provided for recovery")
                return Response({"detail": "No requisition IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

            connection.set_schema(tenant.schema_name)
            with tenant_context(tenant):
                requisitions = JobRequisition.objects.filter(id__in=ids, tenant=tenant, is_deleted=True)
                if not requisitions.exists():
                    logger.warning(f"No soft-deleted requisitions found for IDs {ids} in tenant {tenant.schema_name}")
                    return Response({"detail": "No soft-deleted requisitions found."}, status=status.HTTP_404_NOT_FOUND)

                recovered_count = 0
                with transaction.atomic():
                    for requisition in requisitions:
                        requisition.restore()
                        recovered_count += 1

                #logger.info(f"Successfully recovered {recovered_count} requisitions for tenant {tenant.schema_name}")
                return Response({
                    "detail": f"Successfully recovered {recovered_count} requisition(s)."
                }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error during recovery of requisitions for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PermanentDeleteJobRequisitionsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]

    def post(self, request, *args, **kwargs):
        #logger.debug(f"Received POST request to permanently delete job requisitions: {request.data}")
        try:
            tenant = request.tenant
            if not tenant:
                logger.error("No tenant associated with the request")
                return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)

            ids = request.data.get('ids', [])
            if not ids:
                logger.warning("No requisition IDs provided for permanent deletion")
                return Response({"detail": "No requisition IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

            connection.set_schema(tenant.schema_name)
            with tenant_context(tenant):
                requisitions = JobRequisition.objects.filter(id__in=ids, tenant=tenant, is_deleted=True)
                if not requisitions.exists():
                    logger.warning(f"No soft-deleted requisitions found for IDs {ids} in tenant {tenant.schema_name}")
                    return Response({"detail": "No soft-deleted requisitions found."}, status=status.HTTP_404_NOT_FOUND)

                deleted_count = requisitions.delete()[0]
                #logger.info(f"Successfully permanently deleted {deleted_count} requisitions for tenant {tenant.schema_name}")
                return Response({
                    "detail": f"Successfully permanently deleted {deleted_count} requisition(s)."
                }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error during permanent deletion of requisitions for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)