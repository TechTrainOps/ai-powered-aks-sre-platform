import json
import os
from typing import Any

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field


app = FastAPI(
    title="AKS SRE AI Analyser",
    version="1.0.0",
)


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
AZURE_OPENAI_API_VERSION = os.getenv(
    "AZURE_OPENAI_API_VERSION",
    "2025-04-01-preview",
)


# -------------------------------------------------------------------
# Request / Response models
# -------------------------------------------------------------------

class IncidentRequest(BaseModel):
    incident_id: str = Field(min_length=1)

    alert: dict[str, Any] = Field(default_factory=dict)

    evidence: dict[str, Any] = Field(default_factory=dict)


class RCAResponse(BaseModel):
    incident_id: str
    summary: str
    root_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    severity: str
    evidence: list[str]
    recommended_action: str


# -------------------------------------------------------------------
# Azure OpenAI client
# -------------------------------------------------------------------

def get_openai_client() -> OpenAI:
    """
    Create an Azure OpenAI client using Microsoft Entra ID.

    DefaultAzureCredential uses the AKS Workload Identity environment
    injected into the analyser pod.
    """

    if not AZURE_OPENAI_ENDPOINT:
        raise RuntimeError(
            "AZURE_OPENAI_ENDPOINT environment variable is not configured."
        )

    if not AZURE_OPENAI_DEPLOYMENT:
        raise RuntimeError(
            "AZURE_OPENAI_DEPLOYMENT environment variable is not configured."
        )

    credential = DefaultAzureCredential()

    token_provider = get_bearer_token_provider(
        credential,
        "https://ai.azure.com/.default",
    )

    return OpenAI(
        base_url=f"{AZURE_OPENAI_ENDPOINT}/openai/v1/",
        api_key=token_provider(),
        max_retries=5,
    )


# -------------------------------------------------------------------
# Evidence formatting
# -------------------------------------------------------------------

def build_incident_context(incident: IncidentRequest) -> str:
    """
    Convert the incident into a controlled JSON representation
    that can be provided to the model.
    """

    context = {
        "incident_id": incident.incident_id,
        "alert": incident.alert,
        "evidence": incident.evidence,
    }

    return json.dumps(
        context,
        indent=2,
        default=str,
    )


# -------------------------------------------------------------------
# Health endpoint
# -------------------------------------------------------------------

@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "healthy"}


# -------------------------------------------------------------------
# Analyzer endpoint
# -------------------------------------------------------------------

@app.post("/analyse", response_model=RCAResponse)
def analyse_incident(incident: IncidentRequest) -> RCAResponse:
    """
    Analyse an incident using Azure OpenAI and return structured RCA.
    """

    try:
        incident_context = build_incident_context(incident)

        system_prompt = """
You are an SRE incident analysis assistant for an Azure Kubernetes
Service environment.

Analyse the supplied alert and Kubernetes evidence.

Your job is to:

1. Identify the most likely root cause.
2. Explain the evidence supporting that conclusion.
3. Estimate confidence between 0 and 1.
4. Assign a severity such as Sev1, Sev2, Sev3, or Sev4.
5. Recommend a safe next action.

Do not invent evidence.

Only use facts contained in the supplied incident.

Do not claim that a remediation was executed.

Return ONLY valid JSON matching this schema:

{
  "summary": "brief incident summary",
  "root_cause": "most likely root cause",
  "confidence": 0.0,
  "severity": "Sev2",
  "evidence": [
    "evidence item 1",
    "evidence item 2"
  ],
  "recommended_action": "safe recommended action"
}
"""

        user_prompt = f"""
Analyse this AKS incident:

{incident_context}
"""

        client = get_openai_client()

        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=0.1,
            response_format={
                "type": "json_object",
            },
        )

        content = response.choices[0].message.content

        if not content:
            raise RuntimeError(
                "Azure OpenAI returned an empty response."
            )

        result = json.loads(content)

        return RCAResponse(
            incident_id=incident.incident_id,
            summary=result["summary"],
            root_cause=result["root_cause"],
            confidence=float(result["confidence"]),
            severity=result["severity"],
            evidence=result["evidence"],
            recommended_action=result["recommended_action"],
        )

    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Azure OpenAI returned invalid JSON: {exc}",
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Incident analysis failed: {exc}",
        ) from exc