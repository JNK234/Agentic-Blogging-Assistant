import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from backend.models.cost_tracking_wrapper import CostTrackingModel

@pytest.mark.asyncio
async def test_cost_tracking_duration():
    # Mock dependencies
    mock_base_model = AsyncMock()
    mock_base_model.ainvoke.return_value = "Response"
    
    mock_sql_manager = AsyncMock()
    mock_aggregator = MagicMock()
    
    # Initialize model
    model = CostTrackingModel(
        base_model=mock_base_model,
        model_name="gpt-4",
        cost_aggregator=mock_aggregator,
        sql_project_manager=mock_sql_manager,
        project_id="test-project",
        agent_name="test-agent"
    )
    
    # Invoke
    await model.ainvoke("Test prompt")
    
    # Verify track_cost called with duration_seconds
    assert mock_sql_manager.track_cost.called
    call_args = mock_sql_manager.track_cost.call_args[1]
    assert "duration_seconds" in call_args
    assert isinstance(call_args["duration_seconds"], float)
    assert call_args["duration_seconds"] >= 0
    
    # Verify aggregator record_cost called with duration_seconds
    assert mock_aggregator.record_cost.called
    record = mock_aggregator.record_cost.call_args[0][0]
    assert "duration_seconds" in record
    assert isinstance(record["duration_seconds"], float)
