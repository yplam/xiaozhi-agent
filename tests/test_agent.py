"""
Tests for the AI agent implementation.
"""
import asyncio
import os
import sys
import pytest

# Add parent directory to path to import app modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from app.agent.graph import AgentGraph
from app.agent.nodes.llm import LLMNode
from app.agent.nodes.tts import TTSNode


@pytest.mark.asyncio
async def test_llm_node():
    """Test that the LLM node generates responses correctly."""
    # Initialize LLM node
    llm_node = LLMNode()
    
    # Create a test state with user input
    state = {
        "transcription": "What time is it?",
        "conversation_context": {}
    }
    
    # Process the state
    result = await llm_node.process(state)
    
    # Check that we have a response
    assert "response_text" in result
    assert result["response_text"] != ""
    assert "emotion" in result


@pytest.mark.asyncio
async def test_graph_text_input():
    """Test the agent graph with direct text input."""
    # Initialize agent graph
    agent_graph = AgentGraph()
    
    # Process text input
    result = await agent_graph.process_text_input("Hello, how are you?", "test_session")
    
    # Check that we have a response
    assert "response_text" in result
    assert result["response_text"] != ""
    assert "emotion" in result


if __name__ == "__main__":
    # Run tests manually
    asyncio.run(test_llm_node())
    asyncio.run(test_graph_text_input())
    print("All tests passed!") 