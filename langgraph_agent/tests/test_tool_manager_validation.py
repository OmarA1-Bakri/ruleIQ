"""
Tests for tool manager validation and Pydantic compatibility.
Validates tool creation, execution, and error handling.
"""

import pytest
import asyncio
from uuid import uuid4

from langgraph_agent.agents.tool_manager import (
    ToolManager,
    ToolResult,
    ToolError,
    ComplianceAnalysisTool,
    DocumentRetrievalTool,
    EvidenceCollectionTool,
    ReportGenerationTool,
    ToolCategory,
    ToolPriority,
)
from langgraph_agent.core.models import SafeFallbackResponse


class TestToolCreation:
    """Test tool instantiation and Pydantic compatibility."""

    def test_compliance_analysis_tool_creation(self):
        """Test ComplianceAnalysisTool can be instantiated."""
        tool = ComplianceAnalysisTool()

        assert tool.name == "compliance_analysis"
        assert (
            tool.description == "Analyze business compliance requirements and applicable frameworks"
        )
        assert tool.category == ToolCategory.COMPLIANCE_ANALYSIS
        assert tool.priority == ToolPriority.HIGH

    def test_document_retrieval_tool_creation(self):
        """Test DocumentRetrievalTool can be instantiated."""
        tool = DocumentRetrievalTool()

        assert tool.name == "document_retrieval"
        assert (
            tool.description == "Retrieve compliance documents, templates, and guidance materials"
        )
        assert tool.category == ToolCategory.DOCUMENT_RETRIEVAL
        assert tool.priority == ToolPriority.MEDIUM  # Default

    def test_evidence_collection_tool_creation(self):
        """Test EvidenceCollectionTool can be instantiated."""
        tool = EvidenceCollectionTool()

        assert tool.name == "evidence_collection"
        assert tool.description == "Collect and organize compliance evidence and documentation"
        assert tool.category == ToolCategory.EVIDENCE_COLLECTION

    def test_report_generation_tool_creation(self):
        """Test ReportGenerationTool can be instantiated."""
        tool = ReportGenerationTool()

        assert tool.name == "report_generation"
        assert tool.description == "Generate comprehensive compliance reports and assessments"
        assert tool.category == ToolCategory.REPORT_GENERATION
        assert tool.priority == ToolPriority.MEDIUM

    def test_all_tools_have_required_langchain_methods(self):
        """Test all tools implement required LangChain BaseTool methods."""
        tools = [
            ComplianceAnalysisTool(),
            DocumentRetrievalTool(),
            EvidenceCollectionTool(),
            ReportGenerationTool(),
        ]

        for tool in tools:
            # Check required attributes
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")

            # Check required methods
            assert hasattr(tool, "_run")
            assert hasattr(tool, "_arun")
            assert callable(tool._run)
            assert callable(tool._arun)


class TestToolManager:
    """Test ToolManager functionality."""

    def test_tool_manager_initialization(self):
        """Test ToolManager initializes with default tools."""
        manager = ToolManager("test_secret")

        assert len(manager.tools) == 4
        assert "compliance_analysis" in manager.tools
        assert "document_retrieval" in manager.tools
        assert "evidence_collection" in manager.tools
        assert "report_generation" in manager.tools

    def test_tool_manager_list_tools(self):
        """Test listing available tools."""
        manager = ToolManager("test_secret")

        tools = manager.list_tools()
        assert len(tools) == 4
        assert "compliance_analysis" in tools

        # Test category filtering
        compliance_tools = manager.list_tools(ToolCategory.COMPLIANCE_ANALYSIS)
        assert "compliance_analysis" in compliance_tools

        document_tools = manager.list_tools(ToolCategory.DOCUMENT_RETRIEVAL)
        assert "document_retrieval" in document_tools

    def test_tool_manager_get_tool(self):
        """Test getting individual tools."""
        manager = ToolManager("test_secret")

        tool = manager.get_tool("compliance_analysis")
        assert tool is not None
        assert isinstance(tool, ComplianceAnalysisTool)

        # Test non-existent tool
        missing_tool = manager.get_tool("nonexistent")
        assert missing_tool is None

    def test_tool_manager_priority_filtering(self):
        """Test getting tools by priority level."""
        manager = ToolManager("test_secret")

        high_priority = manager.get_tools_by_priority(ToolPriority.HIGH)
        assert "compliance_analysis" in high_priority

        medium_priority = manager.get_tools_by_priority(ToolPriority.MEDIUM)
        assert len(medium_priority) >= 1  # At least document_retrieval and report_generation


@pytest.mark.asyncio
class TestToolExecution:
    """Test tool execution functionality."""

    async def test_compliance_analysis_tool_execution(self):
        """Test ComplianceAnalysisTool execution."""
        tool = ComplianceAnalysisTool()

        business_profile = {
            "industry": "retail",
            "employees": 50,
            "data_processing": ["customer_data", "employee_data"],
        }
        frameworks = ["GDPR", "UK_GDPR"]

        result = await tool._execute(business_profile, frameworks)

        assert isinstance(result, dict)
        assert "applicable_frameworks" in result
        assert "compliance_score" in result
        assert "priority_obligations" in result
        assert "risk_areas" in result
        assert "recommendations" in result

        assert result["applicable_frameworks"] == frameworks
        assert isinstance(result["compliance_score"], (int, float))
        assert isinstance(result["priority_obligations"], list)
        assert isinstance(result["risk_areas"], list)
        assert isinstance(result["recommendations"], list)

    async def test_document_retrieval_tool_execution(self):
        """Test DocumentRetrievalTool execution."""
        tool = DocumentRetrievalTool()

        result = await tool._execute(
            query="GDPR privacy policy", framework="GDPR", doc_type="template"
        )

        assert isinstance(result, dict)
        assert "templates" in result
        assert "guidance" in result
        assert "regulations" in result

        assert isinstance(result["templates"], list)
        assert len(result["templates"]) > 0

        # Check template structure
        template = result["templates"][0]
        assert "title" in template
        assert "type" in template
        assert "framework" in template
        assert "url" in template

    async def test_evidence_collection_tool_execution(self):
        """Test EvidenceCollectionTool execution."""
        tool = EvidenceCollectionTool()

        result = await tool._execute(company_id="test_company_123", frameworks=["GDPR", "UK_GDPR"])

        assert isinstance(result, dict)
        assert "collected" in result
        assert "missing" in result
        assert "recommendations" in result

        assert isinstance(result["collected"], list)
        assert isinstance(result["missing"], list)
        assert isinstance(result["recommendations"], list)

        # Check evidence structure
        if result["collected"]:
            evidence = result["collected"][0]
            assert "type" in evidence
            assert "title" in evidence
            assert "status" in evidence

    async def test_report_generation_tool_execution(self):
        """Test ReportGenerationTool execution."""
        tool = ReportGenerationTool()

        result = await tool._execute(
            company_id="test_company_123",
            report_type="compliance_assessment",
            frameworks=["GDPR"],
        )

        assert isinstance(result, dict)
        assert "report_id" in result
        assert "company_id" in result
        assert "report_type" in result
        assert "frameworks" in result
        assert "generated_at" in result
        assert "executive_summary" in result
        assert "sections" in result
        assert "action_plan" in result

        # Check report structure
        assert result["company_id"] == "test_company_123"
        assert result["report_type"] == "compliance_assessment"
        assert result["frameworks"] == ["GDPR"]

        # Check executive summary
        summary = result["executive_summary"]
        assert "overall_score" in summary
        assert "critical_issues" in summary
        assert "medium_issues" in summary
        assert "recommendations" in summary


@pytest.mark.asyncio
class TestToolManagerExecution:
    """Test ToolManager execution functionality."""

    async def test_execute_tool_success(self):
        """Test successful tool execution through ToolManager."""
        manager = ToolManager("test_secret")
        company_id = uuid4()
        thread_id = "test_thread"

        result = await manager.execute_tool(
            tool_name="compliance_analysis",
            company_id=company_id,
            thread_id=thread_id,
            business_profile={"industry": "tech"},
            frameworks=["GDPR"],
        )

        assert isinstance(result, ToolResult)
        assert result.success
        assert result.tool_name == "compliance_analysis"
        assert result.result is not None
        assert result.execution_time_ms >= 0

    async def test_execute_tool_not_found(self):
        """Test tool execution with non-existent tool."""
        manager = ToolManager("test_secret")
        company_id = uuid4()
        thread_id = "test_thread"

        result = await manager.execute_tool(
            tool_name="nonexistent_tool", company_id=company_id, thread_id=thread_id
        )

        assert isinstance(result, SafeFallbackResponse)
        assert "not found" in result.error_message
        assert result.company_id == company_id
        assert result.thread_id == thread_id

    async def test_execute_tool_chain(self):
        """Test executing a sequence of tools."""
        manager = ToolManager("test_secret")
        company_id = uuid4()
        thread_id = "test_thread"

        tool_sequence = [
            {
                "tool": "compliance_analysis",
                "args": [],
                "kwargs": {
                    "business_profile": {"industry": "retail"},
                    "frameworks": ["GDPR"],
                },
            },
            {
                "tool": "document_retrieval",
                "args": [],
                "kwargs": {
                    "query": "GDPR template",
                    "framework": "GDPR",
                    "doc_type": "template",
                },
                "use_context": [],  # No context dependency for this test
            },
        ]

        results = await manager.execute_tool_chain(
            tool_sequence=tool_sequence, company_id=company_id, thread_id=thread_id
        )

        assert len(results) == 2
        assert all(isinstance(r, ToolResult) for r in results)
        assert all(r.success for r in results)

    async def test_execute_parallel_tools(self):
        """Test executing multiple tools in parallel."""
        manager = ToolManager("test_secret")
        company_id = uuid4()
        thread_id = "test_thread"

        tool_configs = [
            {
                "tool": "compliance_analysis",
                "kwargs": {
                    "business_profile": {"industry": "tech"},
                    "frameworks": ["GDPR"],
                },
            },
            {
                "tool": "evidence_collection",
                "kwargs": {
                    "company_id": str(company_id),  # Tool expects company_id as string
                    "frameworks": ["GDPR"],
                },
            },
        ]

        results = await manager.execute_parallel_tools(
            tool_configs=tool_configs, company_id=company_id, thread_id=thread_id
        )

        assert len(results) == 2
        assert all(isinstance(r, ToolResult) for r in results)
        assert all(r.success for r in results)


class TestToolStats:
    """Test tool statistics and monitoring."""

    def test_tool_stats_initialization(self):
        """Test tool stats are properly initialized."""
        manager = ToolManager("test_secret")

        stats = manager.get_tool_stats()
        assert len(stats) == 4  # One for each default tool

        # Check stat structure
        for _tool_name, tool_stats in stats.items():
            assert "total_executions" in tool_stats
            assert "successful_executions" in tool_stats
            assert "failed_executions" in tool_stats
            assert "avg_execution_time_ms" in tool_stats
            assert "last_executed" in tool_stats

            # Initial values
            assert tool_stats["total_executions"] == 0
            assert tool_stats["successful_executions"] == 0
            assert tool_stats["failed_executions"] == 0
            assert tool_stats["avg_execution_time_ms"] == 0.0
            assert tool_stats["last_executed"] is None

    def test_tool_stats_individual_tool(self):
        """Test getting stats for individual tool."""
        manager = ToolManager("test_secret")

        stats = manager.get_tool_stats("compliance_analysis")
        assert stats is not None
        assert "total_executions" in stats

        # Test non-existent tool
        missing_stats = manager.get_tool_stats("nonexistent")
        assert missing_stats == {}

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test ToolManager health check."""
        manager = ToolManager("test_secret")

        health = await manager.health_check()

        assert "status" in health
        assert "total_tools" in health
        assert "tools_by_category" in health
        assert "tool_statuses" in health

        assert health["status"] in ["healthy", "degraded"]
        assert health["total_tools"] == 4
        assert len(health["tool_statuses"]) == 4

        # All tools should be available initially
        for _tool_name, status in health["tool_statuses"].items():
            assert status == "available"


class TestRateLimiting:
    """Test tool rate limiting functionality."""

    def test_rate_limit_check(self):
        """Test rate limit checking."""
        tool = ComplianceAnalysisTool()

        # Initially should be within limits
        assert tool._check_rate_limit()

        # Simulate hitting rate limit
        tool._execution_count = tool.rate_limit_per_minute
        assert not tool._check_rate_limit()

        # Simulate time passing (reset period)
        from datetime import datetime, timedelta, timezone

        tool._last_reset = datetime.now(timezone.utc) - timedelta(seconds=61)
        assert tool._check_rate_limit()
        assert tool._execution_count == 0  # Should reset counter


class TestSignatureValidation:
    """Test HMAC signature validation."""

    def test_validate_signature(self):
        """Test HMAC signature validation."""
        tool = ComplianceAnalysisTool()
        secret = "test_secret_key"
        input_data = "test_input_data"

        # Generate valid signature
        import hmac
        import hashlib

        expected_signature = hmac.new(
            secret.encode(), input_data.encode(), hashlib.sha256
        ).hexdigest()

        # Test valid signature
        assert tool._validate_signature(input_data, expected_signature, secret)

        # Test invalid signature
        assert not tool._validate_signature(input_data, "invalid_signature", secret)

        # Test with different secret
        assert not tool._validate_signature(input_data, expected_signature, "wrong_secret")


@pytest.mark.asyncio
class TestErrorHandling:
    """Test error handling in tool execution."""

    async def test_tool_timeout_handling(self):
        """Test tool execution timeout handling."""
        # Create a tool with very short timeout
        tool = ComplianceAnalysisTool()
        tool.max_execution_time_seconds = 0.001  # 1ms timeout

        # Mock _execute to take longer than timeout
        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(0.01)  # 10ms delay
            return {"result": "success"}

        tool._execute = slow_execute

        with pytest.raises(ToolError) as exc_info:
            await tool._safe_execute(business_profile={"test": "data"}, frameworks=["GDPR"])

        assert exc_info.value.error_type == "timeout"
        assert "timed out" in exc_info.value.message

    async def test_tool_execution_exception(self):
        """Test tool execution exception handling."""
        tool = ComplianceAnalysisTool()

        # Mock _execute to raise exception
        async def failing_execute(*args, **kwargs):
            raise ValueError("Test error")

        tool._execute = failing_execute

        result = await tool._safe_execute(business_profile={"test": "data"}, frameworks=["GDPR"])

        assert isinstance(result, ToolResult)
        assert not result.success
        assert "Test error" in result.error
        assert result.execution_time_ms >= 0
