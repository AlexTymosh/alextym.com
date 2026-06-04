from fastapi import APIRouter, status

from app.core.domain_metrics import record_page_view, record_resume_download
from app.schemas.analytics import AnalyticsEventRequest, AnalyticsEventResponse

router = APIRouter(tags=["analytics"])


@router.post(
    "/analytics/events",
    response_model=AnalyticsEventResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def record_analytics_event(
    event_request: AnalyticsEventRequest,
) -> AnalyticsEventResponse:
    if event_request.event == "page_view" and event_request.page is not None:
        record_page_view(event_request.page)
    if event_request.event == "resume_download" and event_request.source is not None:
        record_resume_download(event_request.source)

    return AnalyticsEventResponse()
