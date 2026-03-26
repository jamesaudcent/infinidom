"""Email service for site form submissions."""
from __future__ import annotations

import asyncio
from html import escape
from typing import Any

import resend

from backend.config import get_settings


def _format_form_html(form_data: dict[str, Any]) -> str:
    """Build a simple HTML table from submitted form data."""
    rows = []
    for key, value in form_data.items():
        safe_key = escape(str(key))
        safe_value = escape("" if value is None else str(value)).replace("\n", "<br>")
        rows.append(
            f"<tr><td style='padding:8px;border:1px solid #ddd;font-weight:600'>{safe_key}</td>"
            f"<td style='padding:8px;border:1px solid #ddd'>{safe_value}</td></tr>"
        )

    rows_html = "".join(rows) or (
        "<tr><td style='padding:8px;border:1px solid #ddd' colspan='2'>No fields submitted</td></tr>"
    )
    return (
        "<h2>New Form Submission</h2>"
        "<p>A user submitted a form on your infinidom site.</p>"
        "<table style='border-collapse:collapse;width:100%'>"
        "<thead><tr>"
        "<th style='padding:8px;border:1px solid #ddd;text-align:left'>Field</th>"
        "<th style='padding:8px;border:1px solid #ddd;text-align:left'>Value</th>"
        "</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        "</table>"
    )


async def send_form_email(*, site_name: str, to_email: str, form_data: dict[str, Any]) -> None:
    """Send a form submission email through Resend."""
    settings = get_settings()
    if not settings.resend_api_key:
        raise ValueError("RESEND_API_KEY is not configured")
    if not settings.resend_from_email:
        raise ValueError("RESEND_FROM_EMAIL is not configured")

    resend.api_key = settings.resend_api_key

    params: resend.Emails.SendParams = {
        "from": settings.resend_from_email,
        "to": [to_email],
        "subject": f"New form submission for {site_name}",
        "html": _format_form_html(form_data),
    }
    await asyncio.to_thread(resend.Emails.send, params)
