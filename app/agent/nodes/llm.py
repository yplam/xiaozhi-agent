"""
LLM (Language Model) node for LangGraph.
"""
import json
from typing import Any, Dict, List, Optional, Tuple

import openai
from httpx import AsyncClient, Client
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.config import (OPENAI_API_KEY, OPENAI_MODEL, OPENAI_TEMPERATURE,
                        PROXY_ENABLED, PROXY_URL)
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class LLMNode:
    """
    LangGraph node for handling language model processing.
    
    This node is responsible for generating responses using the LLM
    and determining next actions in the conversation flow.
    """
    
    def __init__(self):
        """Initialize the LLM node."""
        self.llm = self._create_llm()
        self.history: List[Dict[str, str]] = []
        self._setup_prompts()
    
    def _create_llm(self) -> ChatOpenAI:
        """
        Create an OpenAI LLM client.
        
        Returns:
            ChatOpenAI instance
        """
        http_client = None
        
        if PROXY_ENABLED and PROXY_URL:
            http_client = Client(proxy=PROXY_URL)
            logger.info(f"Using HTTP proxy for LLM: {PROXY_URL}")
        
        return ChatOpenAI(
            api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            temperature=OPENAI_TEMPERATURE,
            streaming=False,
            http_client=http_client,
        )
    
    def _setup_prompts(self) -> None:
        """Set up the prompt templates for the LLM."""
        self.chat_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful voice assistant. 
Respond to user queries in a natural, conversational way.
If specific IoT devices are mentioned, include commands for them in your response as JSON.
Keep your responses concise but helpful.
If you don't know something, say so honestly.
"""),
            ("human", "{input}"),
        ])
    
    async def _get_llm_response(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get a response from the LLM.
        
        Args:
            user_input: The user's input text
            context: Additional context
            
        Returns:
            Response data containing text, emotion, and any IoT commands
        """
        # Prepare the input for the LLM
        llm_input = {
            "input": user_input
        }
        
        # Get raw response from LLM
        chain = self.chat_prompt | self.llm
        response = await chain.ainvoke(llm_input)
        response_text = response.content
        
        # Parse for potential IoT commands
        iot_commands = self._extract_iot_commands(response_text)
        
        # Determine emotion (simple heuristic for now)
        emotion = self._determine_emotion(response_text)

        logger.info(f"LLM response: {response_text}")
        
        return {
            "text": response_text,
            "emotion": emotion,
            "iot_commands": iot_commands
        }
    
    def _extract_iot_commands(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract IoT commands from the response text.
        
        Args:
            text: The response text to parse
            
        Returns:
            List of IoT command dictionaries
        """
        commands = []
        
        # Look for JSON-like patterns in the text
        import re
        json_pattern = r'\{.+?\}'
        json_matches = re.findall(json_pattern, text, re.DOTALL)
        
        for json_str in json_matches:
            try:
                # Try to parse as JSON
                cmd = json.loads(json_str)
                
                # Check if it's an IoT command
                if isinstance(cmd, dict) and "device" in cmd and "action" in cmd:
                    commands.append(cmd)
            except:
                continue
        
        return commands
    
    def _determine_emotion(self, text: str) -> str:
        """
        Determine the emotional tone of the response text.
        
        Args:
            text: The response text
            
        Returns:
            Emotion label
        """
        # Simple keyword-based approach
        if any(word in text.lower() for word in ["sorry", "apologize", "regret"]):
            return "apologetic"
        elif any(word in text.lower() for word in ["happy", "great", "excellent", "!"]):
            return "happy"
        elif any(word in text.lower() for word in ["important", "caution", "warning"]):
            return "serious"
        else:
            return "neutral"
    
    def _update_history(self, user_input: str, response: Dict[str, Any]) -> None:
        """
        Update the conversation history.
        
        Args:
            user_input: The user's input text
            response: The response data
        """
        self.history.append({
            "role": "user",
            "content": user_input
        })
        
        self.history.append({
            "role": "assistant",
            "content": response["text"]
        })
        
        # Keep history at a reasonable size
        if len(self.history) > 10:
            self.history = self.history[-10:]
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the state by generating a response to the user's input.
        
        Args:
            state: The current state of the conversation
                Expected keys:
                - transcription: The transcribed user input
                - conversation_context: Additional context (optional)
                
        Returns:
            Updated state with response data
                Added keys:
                - response_text: The text response to the user
                - emotion: The emotional tone of the response
                - iot_commands: Any IoT commands to execute
        """
        logger.info("Processing in LLM node")
        
        # Check if there's user input to process
        user_input = state.get("transcription", "")
        
        if not user_input:
            logger.warning("No user input to process")
            state["response_text"] = "I didn't catch that. Could you please repeat?"
            state["emotion"] = "neutral"
            state["iot_commands"] = []
            return state
        
        # Get context
        context = state.get("conversation_context", {})
        
        # Log the user input for debugging
        logger.info(f"Processing user input: {user_input}")
        
        # Generate response
        try:
            response = await self._get_llm_response(user_input, context)
            
            # Update state
            state["response_text"] = response["text"]
            state["emotion"] = response["emotion"]
            state["iot_commands"] = response["iot_commands"]
            
            # Update history
            self._update_history(user_input, response)
            
            # Preserve the skip_tts flag if it was set
            if state.get("skip_tts", False):
                logger.info("Text-only mode: Skipping TTS for response")
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            state["response_text"] = "I'm having trouble right now. Please try again later."
            state["emotion"] = "apologetic"
            state["iot_commands"] = []
            state["error"] = str(e)
        
        return state
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call the process method.
        
        Args:
            state: The current state
            
        Returns:
            Updated state
        """
        return await self.process(state) 