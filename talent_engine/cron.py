# talent_engine/cron.py
from django_tenants.utils import tenant_context
from django.utils import timezone
from core.models import Tenant
from talent_engine.models import JobRequisition
import logging

logger = logging.getLogger('talent_engine')

def close_expired_requisitions():
    try:
        tenants = Tenant.objects.all()
        logger.info(f"Starting job to close expired job requisitions for {tenants.count()} tenants.")
        for tenant in tenants:
            try:
                with tenant_context(tenant):
                    expired_requisitions = JobRequisition.active_objects.filter(
                        status__in=['open', 'pending'],
                        deadline_date__lt=timezone.now().date()
                    )
                    updated_count = 0
                    for requisition in expired_requisitions:
                        requisition.status = 'closed'
                        requisition.save()
                        updated_count += 1
                        logger.info(
                            f"Closed job requisition {requisition.id} "
                            f"(Title: {requisition.title}) for tenant {tenant.schema_name}"
                        )
                    if updated_count > 0:
                        logger.info(
                            f"Updated {updated_count} expired job requisitions "
                            f"to 'closed' for tenant {tenant.schema_name}"
                        )
                    else:
                        logger.debug(f"No expired requisitions found for tenant {tenant.schema_name}")
            except Exception as e:
                logger.error(f"Error processing tenant {tenant.schema_name}: {str(e)}", exc_info=True)
                continue
        logger.info("Completed job for closing expired job requisitions.")
    except Exception as e:
        logger.error(f"Unexpected error in job: {str(e)}", exc_info=True)
        raise