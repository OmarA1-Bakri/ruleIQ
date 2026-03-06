"""

Compliance check nodes - migrated from Celery compliance_tasks.
Implements compliance checking against regulations and requirements.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List
from uuid import uuid4

from langgraph_agent.graph.unified_state import UnifiedComplianceState
from langgraph_agent.utils.cost_tracking import track_node_cost
from services.neo4j_service import get_neo4j_service

logger = logging.getLogger(__name__)


@track_node_cost(node_name="compliance_check", model_name="gpt-4")
async def compliance_check_node(
    state: UnifiedComplianceState,
) -> UnifiedComplianceState:
    """
    Complete compliance check implementation.

    Migrated from workers/compliance_tasks.py

    This node:
    - Extracts requirements from RAG documents
    - Checks compliance status against regulations
    - Identifies violations and obligations
    - Determines if notifications are needed

    Args:
        state: Current workflow state with RAG context

    Returns:
        Updated state with compliance results
    """
    logger.info(f"Starting compliance check for workflow {state['workflow_id']}")

    # Extract parameters
    company_id = state.get("company_id") or state.get("metadata", {}).get("company_id")
    regulation = state.get("metadata", {}).get("regulation", "GDPR")

    if not company_id:
        logger.error("No company_id provided for compliance check")
        state["errors"].append(
            {
                "type": "ValidationError",
                "message": "company_id required for compliance check",
                "timestamp": datetime.now().isoformat(),
            }
        )
        state["error_count"] += 1
        return state

    try:
        # Extract requirements from RAG documents
        requirements = extract_requirements_from_rag(state.get("relevant_documents", []))

        # Check compliance status
        compliance_status = await check_compliance_status(
            company_id=company_id, regulation=regulation, requirements=requirements
        )

        # Store results in state
        state["compliance_data"]["check_results"] = compliance_status
        state["compliance_data"]["regulation"] = regulation
        state["compliance_data"]["timestamp"] = datetime.now().isoformat()

        state["obligations"] = compliance_status.get("obligations", [])

        # Calculate compliance score
        if compliance_status.get("obligations"):
            satisfied = len([o for o in compliance_status["obligations"] if o["satisfied"]])
            total = len(compliance_status["obligations"])
            compliance_score = (satisfied / total * 100) if total > 0 else 0
            state["compliance_data"]["compliance_score"] = compliance_score

        # Determine if notification is needed
        violations = compliance_status.get("violations", [])
        if violations:
            state["metadata"]["notify_required"] = True
            state["metadata"]["notify_type"] = "violation"
            state["metadata"]["violation_count"] = len(violations)

            logger.warning(f"Found {len(violations)} compliance violations for {company_id}")
        else:
            logger.info(f"No compliance violations found for {company_id}")

        # Add to history
        state["history"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": "compliance_check_completed",
                "regulation": regulation,
                "obligations_found": len(state["obligations"]),
                "violations_found": len(violations),
            }
        )

        logger.info(f"Compliance check completed for {company_id}")

    except Exception as e:
        logger.error(f"Error in compliance check: {e}")
        state["errors"].append(
            {
                "type": "ComplianceCheckError",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        )
        state["error_count"] += 1
        raise

    return state


@track_node_cost(node_name="extract_requirements", track_tokens=False)
def extract_requirements_from_rag(
    documents: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Extract compliance requirements from RAG documents.

    Args:
        documents: List of relevant documents from RAG

    Returns:
        List of extracted requirements
    """
    requirements = []

    for doc in documents:
        content = doc.get("content", "")
        metadata = doc.get("metadata", {})

        # Parse requirements from document content
        # This is a simplified version - in production, use NLP or structured extraction
        if "requirement" in content.lower() or "must" in content.lower():
            requirements.append(
                {
                    "id": str(uuid4()),
                    "content": content,
                    "source": metadata.get("source", "unknown"),
                    "category": metadata.get("category", "general"),
                }
            )

    logger.info(f"Extracted {len(requirements)} requirements from {len(documents)} documents")

    return requirements


@track_node_cost(node_name="check_compliance_status", model_name="gpt-4")
async def check_compliance_status(
    company_id: str, regulation: str, requirements: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Check compliance status against requirements.

    Queries Neo4j to determine which obligations are satisfied.

    Args:
        company_id: Company identifier
        regulation: Regulation to check (e.g., "GDPR")
        requirements: List of requirements to check

    Returns:
        Dictionary with compliance status including obligations and violations
    """
    logger.info(f"Checking compliance for {company_id} against {regulation}")

    obligations = []
    violations = []

    try:
        neo4j_service = await get_neo4j_service()
        if not neo4j_service or not neo4j_service.driver:
            logger.error("Neo4j service not available")
            return {
                "obligations": [],
                "violations": [],
                "total_obligations": 0,
                "satisfied_obligations": 0,
                "compliance_score": 0,
                "error": "Database service not available",
                "timestamp": datetime.now().isoformat(),
            }

        # Query for company's obligations and evidence
        query = """
        MATCH (c:Company {id: $company_id})
        OPTIONAL MATCH (c)-[:SUBJECT_TO]->(r:Regulation {name: $regulation})
        OPTIONAL MATCH (r)-[:CONTAINS]->(o:Obligation)
        OPTIONAL MATCH (c)-[:HAS_EVIDENCE]->(e:Evidence)-[:SATISFIES]->(o)
        RETURN o, collect(DISTINCT e) as evidence
        """

        result = await neo4j_service.execute_query(
            query,
            parameters={"company_id": company_id, "regulation": regulation},
            read_only=True,
        )

        for record in result:
            if record.get("o"):
                obligation = record["o"]
                evidence = record.get("evidence", [])

                ob_data = {
                    "id": obligation.get("id", str(uuid4())),
                    "title": obligation.get("title", "Unknown Obligation"),
                    "description": obligation.get("description", ""),
                    "satisfied": len(evidence) > 0,
                    "evidence": [e.get("id") for e in evidence if e],
                    "evidence_count": len(evidence),
                    "regulation": regulation,
                }

                obligations.append(ob_data)

                if not ob_data["satisfied"]:
                    violations.append(ob_data)

        # Calculate compliance metrics
        total_obligations = len(obligations)
        satisfied_obligations = len([o for o in obligations if o["satisfied"]])
        compliance_score = (
            (satisfied_obligations / total_obligations * 100) if total_obligations > 0 else 100
        )

        logger.info(
            f"Compliance check complete: {satisfied_obligations}/{total_obligations} "
            f"obligations satisfied ({compliance_score:.1f}%)"
        )

        return {
            "obligations": obligations,
            "violations": violations,
            "total_obligations": total_obligations,
            "satisfied_obligations": satisfied_obligations,
            "compliance_score": compliance_score,
            "regulation": regulation,
            "company_id": company_id,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error querying Neo4j for compliance status: {e}")

        # Return minimal status on error
        return {
            "obligations": [],
            "violations": [],
            "total_obligations": 0,
            "satisfied_obligations": 0,
            "compliance_score": 0,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


async def assess_compliance_risk(
    state: UnifiedComplianceState,
) -> UnifiedComplianceState:
    """
    Assess compliance risk based on violations.

    Additional node for risk assessment workflow.

    Args:
        state: Current workflow state

    Returns:
        Updated state with risk assessment
    """
    violations = state.get("compliance_data", {}).get("check_results", {}).get("violations", [])

    # Simple risk scoring
    risk_score = 0
    risk_level = "LOW"

    if violations:
        risk_score = min(len(violations) * 20, 100)  # Cap at 100

        if risk_score >= 80:
            risk_level = "CRITICAL"
        elif risk_score >= 60:
            risk_level = "HIGH"
        elif risk_score >= 40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

    state["compliance_data"]["risk_assessment"] = {
        "score": risk_score,
        "level": risk_level,
        "violation_count": len(violations),
        "timestamp": datetime.now().isoformat(),
    }

    logger.info(f"Risk assessment: {risk_level} ({risk_score}/100)")

    return state
