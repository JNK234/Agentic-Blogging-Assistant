# ABOUTME: Integration tests for automatic cost tracking wrapper with SQL persistence
# ABOUTME: Tests transparent wrapping, token counting, cost calculation, and SQL tracking

"""
Cost Tracking Integration Tests

Tests the complete cost tracking pipeline:
1. Model wrapping
2. Token counting
3. Cost calculation
4. SQL persistence
5. Error handling
"""

import asyncio
import pytest
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch

from root.backend.models.cost_tracking_wrapper import CostTrackingModel
from root.backend.services.sql_project_manager import SQLProjectManager
from root.backend.utils.token_counter import TokenCounter
from langchain.schema import AIMessage


@pytest.fixture
async def temp_db():
    """Create a temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield f"sqlite:///{path}"
    os.unlink(path)


@pytest.fixture
async def sql_pm(temp_db):
    """Create SQLProjectManager instance"""
    return SQLProjectManager(temp_db)


@pytest.fixture
async def project_id(sql_pm):
    """Create a test project"""
    return await sql_pm.create_project(
        project_name="Test Project",
        metadata={"test": True}
    )


@pytest.fixture
def mock_llm():
    """Create a mock LLM model"""
    llm = Mock()
    llm.model_name = "gpt-4o-mini"

    async def mock_ainvoke(prompt, **kwargs):
        return AIMessage(
            content="This is a test response from the mock LLM model.",
            response_metadata={
                "token_usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 12,
                    "total_tokens": 22
                }
            }
        )

    llm.ainvoke = AsyncMock(side_effect=mock_ainvoke)
    return llm


class TestCostTrackingWrapper:
    """Test suite for CostTrackingModel wrapper"""

    @pytest.mark.asyncio
    async def test_basic_wrapping(self, mock_llm):
        """Test that wrapper preserves model API"""
        wrapped = CostTrackingModel(
            base_model=mock_llm,
            model_name="gpt-4o-mini"
        )

        response = await wrapped.ainvoke("Test prompt")

        assert response.content == "This is a test response from the mock LLM model."
        assert mock_llm.ainvoke.called
        assert wrapped.session_costs["total_calls"] == 1

    @pytest.mark.asyncio
    async def test_token_counting(self, mock_llm):
        """Test that tokens are counted correctly"""
        wrapped = CostTrackingModel(
            base_model=mock_llm,
            model_name="gpt-4o-mini"
        )

        await wrapped.ainvoke("Test prompt")

        summary = wrapped.get_session_summary()
        assert summary["total_calls"] == 1
        assert summary["total_tokens"] > 0
        assert summary["total_cost"] > 0

    @pytest.mark.asyncio
    async def test_cost_calculation(self, mock_llm):
        """Test that costs are calculated correctly"""
        wrapped = CostTrackingModel(
            base_model=mock_llm,
            model_name="gpt-4o-mini"
        )

        await wrapped.ainvoke("Test prompt")

        summary = wrapped.get_session_summary()

        # GPT-4o-mini pricing: $0.15 input, $0.60 output per 1M tokens
        # With small token counts, cost should be very small
        assert 0 < summary["total_cost"] < 0.01

    @pytest.mark.asyncio
    async def test_sql_tracking(self, mock_llm, sql_pm, project_id):
        """Test SQL cost tracking integration"""
        wrapped = CostTrackingModel(
            base_model=mock_llm,
            model_name="gpt-4o-mini",
            sql_project_manager=sql_pm,
            project_id=project_id,
            agent_name="TestAgent"
        )

        await wrapped.ainvoke("Test prompt")

        # Check SQL tracking
        cost_summary = await sql_pm.get_cost_summary(project_id)

        assert cost_summary["total_cost"] > 0
        assert "TestAgent" in cost_summary["cost_by_agent"]
        assert "gpt-4o-mini" in cost_summary["cost_by_model"]

    @pytest.mark.asyncio
    async def test_multiple_calls(self, mock_llm, sql_pm, project_id):
        """Test tracking multiple LLM calls"""
        wrapped = CostTrackingModel(
            base_model=mock_llm,
            model_name="gpt-4o-mini",
            sql_project_manager=sql_pm,
            project_id=project_id,
            agent_name="TestAgent"
        )

        # Make 5 calls
        for i in range(5):
            await wrapped.ainvoke(f"Test prompt {i}")

        # Check session tracking
        summary = wrapped.get_session_summary()
        assert summary["total_calls"] == 5

        # Check SQL tracking
        cost_summary = await sql_pm.get_cost_summary(project_id)
        assert cost_summary["total_input_tokens"] > 0
        assert cost_summary["total_output_tokens"] > 0

    @pytest.mark.asyncio
    async def test_context_tracking(self, mock_llm, sql_pm, project_id):
        """Test context-aware cost tracking"""
        def get_context():
            return {
                "node_name": "test_node",
                "stage": "testing",
                "iteration": 1
            }

        wrapped = CostTrackingModel(
            base_model=mock_llm,
            model_name="gpt-4o-mini",
            sql_project_manager=sql_pm,
            project_id=project_id,
            agent_name="TestAgent",
            context_supplier=get_context
        )

        await wrapped.ainvoke("Test prompt")

        # Verify context was tracked
        analysis = await sql_pm.get_cost_analysis(project_id)
        assert len(analysis["timeline"]) == 1
        assert analysis["timeline"][0]["operation"] == "test_node"

    @pytest.mark.asyncio
    async def test_runtime_configuration(self, mock_llm, sql_pm, project_id):
        """Test configuring tracking at runtime"""
        # Create without SQL tracking
        wrapped = CostTrackingModel(
            base_model=mock_llm,
            model_name="gpt-4o-mini"
        )

        # First call - no SQL tracking
        await wrapped.ainvoke("Test prompt 1")
        cost_summary = await sql_pm.get_cost_summary(project_id)
        assert cost_summary["total_cost"] == 0

        # Configure SQL tracking
        wrapped.configure_tracking(
            sql_project_manager=sql_pm,
            project_id=project_id,
            agent_name="TestAgent"
        )

        # Second call - with SQL tracking
        await wrapped.ainvoke("Test prompt 2")
        cost_summary = await sql_pm.get_cost_summary(project_id)
        assert cost_summary["total_cost"] > 0

        # Local session should have both calls
        summary = wrapped.get_session_summary()
        assert summary["total_calls"] == 2

    @pytest.mark.asyncio
    async def test_error_handling_sql_failure(self, mock_llm):
        """Test that LLM calls succeed even if SQL tracking fails"""
        # Create with invalid SQL manager
        broken_sql = Mock()
        broken_sql.track_cost = AsyncMock(side_effect=Exception("DB Error"))

        wrapped = CostTrackingModel(
            base_model=mock_llm,
            model_name="gpt-4o-mini",
            sql_project_manager=broken_sql,
            project_id="test-project",
            agent_name="TestAgent"
        )

        # Call should succeed despite SQL error
        response = await wrapped.ainvoke("Test prompt")
        assert response.content == "This is a test response from the mock LLM model."

        # Local tracking should still work
        summary = wrapped.get_session_summary()
        assert summary["total_calls"] == 1
        assert summary["total_cost"] > 0

    @pytest.mark.asyncio
    async def test_model_name_normalization(self, mock_llm):
        """Test that model names are normalized correctly"""
        test_cases = [
            ("gpt-4o-mini", "gpt-4o-mini"),
            ("gpt4o-mini", "gpt-4o-mini"),
            ("claude-3.5-sonnet", "claude-3.5-sonnet"),
            ("claude3.5-sonnet", "claude-3.5-sonnet"),
        ]

        for input_name, expected_name in test_cases:
            wrapped = CostTrackingModel(
                base_model=mock_llm,
                model_name=input_name
            )
            assert wrapped.model_name == expected_name

    @pytest.mark.asyncio
    async def test_session_reset(self, mock_llm):
        """Test resetting session costs"""
        wrapped = CostTrackingModel(
            base_model=mock_llm,
            model_name="gpt-4o-mini"
        )

        # Make some calls
        await wrapped.ainvoke("Test 1")
        await wrapped.ainvoke("Test 2")

        summary = wrapped.get_session_summary()
        assert summary["total_calls"] == 2

        # Reset
        wrapped.reset_session_costs()

        summary = wrapped.get_session_summary()
        assert summary["total_calls"] == 0
        assert summary["total_cost"] == 0


class TestTokenCounter:
    """Test suite for TokenCounter utility"""

    def test_pricing_lookup(self):
        """Test that pricing is available for all major models"""
        counter = TokenCounter()

        test_models = [
            "gpt-4o",
            "gpt-4o-mini",
            "claude-3.5-sonnet",
            "claude-3.5-haiku",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "deepseek-v3"
        ]

        for model in test_models:
            pricing = counter.get_model_pricing_info(model)
            assert pricing["found"], f"Pricing not found for {model}"
            assert pricing["input_price_per_1m"] > 0
            assert pricing["output_price_per_1m"] > 0

    def test_cost_calculation(self):
        """Test cost calculation accuracy"""
        counter = TokenCounter()

        # Test with GPT-4o-mini: $0.15 input, $0.60 output per 1M tokens
        cost, breakdown = counter.calculate_cost(
            input_tokens=1000,
            output_tokens=2000,
            model_name="gpt-4o-mini"
        )

        expected_input = (1000 / 1_000_000) * 0.15
        expected_output = (2000 / 1_000_000) * 0.60
        expected_total = expected_input + expected_output

        assert abs(cost - expected_total) < 0.0001
        assert breakdown["input_tokens"] == 1000
        assert breakdown["output_tokens"] == 2000
        assert breakdown["total_tokens"] == 3000

    def test_token_counting(self):
        """Test token counting"""
        counter = TokenCounter()

        text = "This is a test sentence for token counting."
        tokens = counter.count_tokens(text, "gpt-4o")

        assert tokens > 0
        assert tokens < 20  # Should be around 10 tokens


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
