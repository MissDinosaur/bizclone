"""Home page UI - Main landing page for BizClone"""

import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

# Setup Jinja2 templates
templates = Jinja2Templates(directory="ui/templates")

router = APIRouter(tags=["home"])


@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """
    Get home page
    Display main landing page with company info and navigation buttons
    """
    try:
        context = {
            "request": request,
        }
        return templates.TemplateResponse("index.html", context)
    except Exception as e:
        logger.error(f"Error rendering home page: {e}", exc_info=True)
        return HTMLResponse(
            content=f"<h1>Error</h1><p>{str(e)}</p>",
            status_code=500
        )
