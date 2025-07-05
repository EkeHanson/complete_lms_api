# utils/tenant_utils.py
from core.models import Tenant
from talent_engine.models import JobRequisition
from django.db import connection
import logging

logger = logging.getLogger('tenant_utils')

def resolve_tenant_from_unique_link(unique_link: str):
    """
    Resolves and returns the tenant and JobRequisition based on the unique link.
    """
    if not unique_link or '-' not in unique_link:
        logger.warning("Missing or invalid unique_link format")
        return None, None

    tenant_schema = unique_link.split('-')[0]

    try:
        tenant = Tenant.objects.get(schema_name=tenant_schema)
        connection.set_schema(tenant.schema_name)

        #logger.debug(f"Schema set to: {tenant.schema_name}")

        # Now properly fetch the job requisition by unique_link
        # print("About to get JOb")
        job_requisition = JobRequisition.objects.filter(
            unique_link=unique_link, 
            tenant=tenant, 
            publish_status=True
        ).first()
        # print("just gotten the JOb")

        if not job_requisition:
            logger.warning(f"No published JobRequisition found for link: {unique_link}")
            return tenant, None

        return tenant, job_requisition

    except Tenant.DoesNotExist:
        logger.warning(f"Tenant '{tenant_schema}' not found.")
        return None, None

    except Exception as e:
        logger.error(f"Unexpected error in resolving tenant/job: {str(e)}")
        return None, None
