"""
Workflow Service — re-exports background job API (legacy module path).
"""
from services.prospect_jobs import get_prospect_job_status, start_prospect_job

__all__ = ["start_prospect_job", "get_prospect_job_status"]
