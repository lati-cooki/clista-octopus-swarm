import os
import requests
import logging

logger = logging.getLogger(__name__)

def trigger_deployment_webhook(prompt: str, decision: str, coherence: float):
    """
    Connects the Swarm's output to an Enterprise CI/CD pipeline (e.g. GitHub Actions, Jira).
    If a NO-GO is detected, it flags the deployment as rejected.
    """
    webhook_url = os.getenv("ENTERPRISE_WEBHOOK_URL")
    if not webhook_url:
        logger.info("CI/CD Webhook skipped: ENTERPRISE_WEBHOOK_URL not configured in environment.")
        return False
        
    payload = {
        "event": "mrm_consensus_reached",
        "prompt": prompt,
        "decision": decision,
        "coherence_score": coherence,
        "approved": "NO-GO" not in decision.upper()
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=5.0)
        response.raise_for_status()
        logger.info(f"CI/CD Webhook triggered successfully: {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"Failed to trigger CI/CD Webhook: {e}")
        return False
