"""
LangGraph implementation for the AI agent.
"""
from typing import Any, Dict, List, Optional, Union, Annotated

import asyncio
from langchain.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

# For graph visualization
try:
    from IPython.display import Image, display
    HAS_IPYTHON = True
except ImportError:
    HAS_IPYTHON = False

from app.agent.nodes.asr import ASRNode
from app.agent.nodes.iot import IoTNode
from app.agent.nodes.llm import LLMNode
from app.agent.nodes.tts import TTSNode
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


# Define state schema for the graph
class AgentState(TypedDict, total=False):
    session_id: Annotated[str, "unique identifier for the session"]
    message_type: str
    audio_buffer: Optional[List[bytes]]
    transcription: Optional[str]
    has_new_user_input: bool
    response_text: Optional[str]
    audio_response: Optional[bytes]
    emotion: Optional[str]
    iot_commands: Optional[List[Dict[str, Any]]]
    device_descriptors: Optional[List[Dict[str, Any]]]
    device_states: Optional[Dict[str, Any]]
    abort: Optional[bool]
    abort_reason: Optional[str]
    conversation_context: Optional[Dict[str, Any]]
    error: Optional[str]
    skip_tts: bool


class AgentGraph:
    """
    Main agent graph implementation using LangGraph.
    
    This class coordinates the flow between different processing nodes
    to handle the conversation flow.
    """
    
    def __init__(self):
        """Initialize the agent graph."""
        # Initialize nodes
        self.asr_node = ASRNode()
        self.llm_node = LLMNode()
        self.tts_node = TTSNode()
        self.iot_node = IoTNode()
        
        # Build the graph
        self.graph = self._build_graph()
        logger.info("Agent graph initialized")
    
    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph state graph.
        
        Returns:
            StateGraph instance
        """
        # Create a new graph with state schema
        builder = StateGraph(state_schema=AgentState)
        
        # Define nodes
        builder.add_node("asr", self.asr_node)
        builder.add_node("llm", self.llm_node)
        builder.add_node("iot", self.iot_node)
        builder.add_node("tts", self.tts_node)
        
        # Set the ASR node as the default entry point
        builder.set_entry_point("asr")
        
        # Connect nodes sequentially
        builder.add_edge("asr", "llm")
        builder.add_edge("llm", "iot")
        builder.add_edge("iot", "tts")
        builder.add_edge("tts", END)
        
        # Compile the graph
        return builder.compile()
    
    async def process_message(self, message_type: str, data: Any, session_id: str) -> Dict[str, Any]:
        """
        Process a message through the agent graph.
        
        Args:
            message_type: Type of message (e.g., "listen", "iot")
            data: Message data
            session_id: Client session ID
            
        Returns:
            Processing results
        """
        # Initialize state based on message type
        state = self._init_state_from_message(message_type, data, session_id)
        
        if not state:
            logger.warning(f"Unsupported message type: {message_type}")
            return {"error": f"Unsupported message type: {message_type}"}
        
        # Run the graph
        try:
            # Create a config to ensure we don't concurrently update the same keys
            config = {"configurable": {"session_id": session_id}}
            
            # Use the config when invoking the graph
            result = await self.graph.ainvoke(state, config=config)
            return result
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {"error": str(e)}
    
    def _init_state_from_message(
        self, message_type: str, data: Any, session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Initialize state dictionary based on message type.
        
        Args:
            message_type: Type of message
            data: Message data
            session_id: Client session ID
            
        Returns:
            Initial state dictionary or None if unsupported message type
        """
        # Common state initialization
        state: Dict[str, Any] = {
            "session_id": session_id,
            "message_type": message_type,
            "conversation_context": {},  # Initialize empty context
            "has_new_user_input": False,
            "skip_tts": message_type == "text"  # Skip TTS for direct text input
        }
        
        if message_type == "listen":
            # Handle audio data
            if isinstance(data, bytes):
                state["audio_buffer"] = [data]
            elif isinstance(data, list):
                state["audio_buffer"] = data
            
            state["has_new_user_input"] = bool(state["audio_buffer"])
            
        elif message_type == "text":
            # Direct text input (for testing or non-audio clients)
            state["transcription"] = data
            state["has_new_user_input"] = bool(data)
            logger.info(f"Processing direct text input: {data}")
            
        elif message_type == "iot":
            # Handle IoT-related messages
            if "descriptors" in data:
                state["device_descriptors"] = data["descriptors"]
            elif "states" in data:
                state["device_states"] = data["states"]
                
        elif message_type == "abort":
            # Handle abortion of the current conversation
            state["abort"] = True
            state["abort_reason"] = data.get("reason", "user_request")
            
        else:
            # Unsupported message type
            return None
        
        return state
    
    async def process_audio_buffer(self, audio_buffer: List[bytes], session_id: str) -> Dict[str, Any]:
        """
        Process an audio buffer through the agent graph.
        
        Args:
            audio_buffer: List of audio frames
            session_id: Client session ID
            
        Returns:
            Processing results
        """
        return await self.process_message("listen", audio_buffer, session_id)
    
    async def process_text_input(self, text: str, session_id: str) -> Dict[str, Any]:
        """
        Process text input through the agent graph.
        
        Args:
            text: Input text
            session_id: Client session ID
            
        Returns:
            Processing results
        """
        return await self.process_message("text", text, session_id)
    
    def print_graph(self) -> None:
        """
        Print the structure of the agent graph.
        """
        logger.info("Agent Graph Structure:")
        # Simply print the node names we know
        logger.info(f"Nodes: asr, llm, iot, tts")
        logger.info(f"Edges: asr -> llm -> iot -> tts -> END")
        logger.info(f"Graph type: {type(self.graph)}")
        print(self.graph.get_graph().draw_mermaid())


# If the file is run directly, print the graph structure
if __name__ == "__main__":
    import asyncio
    
    async def test_graph():
        logger.info("Creating agent graph...")
        agent = AgentGraph()
        agent.print_graph()
        
        # Test text input processing
        logger.info("Testing text input...")
        result = await agent.process_text_input("你好，你是谁？", "test_session")
        logger.info(f"Text input result keys: {result.keys()}")
        if "response_text" in result:
            logger.info(f"Response: {result['response_text']}")
        
    # Run the test
    asyncio.run(test_graph()) 