"""
IoT node for LangGraph.
"""
from typing import Any, Dict, List, Optional

from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class IoTNode:
    """
    LangGraph node for handling IoT device interactions.
    
    This node is responsible for processing IoT commands and device states.
    """
    
    def __init__(self):
        """Initialize the IoT node."""
        # Device registry to track known devices and their capabilities
        self.device_registry: Dict[str, Dict[str, Any]] = {}
    
    def register_device(self, device_id: str, capabilities: Dict[str, Any]) -> None:
        """
        Register a device and its capabilities.
        
        Args:
            device_id: The device identifier
            capabilities: Dictionary of device capabilities
        """
        self.device_registry[device_id] = capabilities
        logger.info(f"Device registered: {device_id}")
    
    def get_device_capabilities(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the capabilities of a device.
        
        Args:
            device_id: The device identifier
            
        Returns:
            Device capabilities or None if not found
        """
        return self.device_registry.get(device_id)
    
    def validate_command(self, command: Dict[str, Any]) -> bool:
        """
        Validate an IoT command against known device capabilities.
        
        Args:
            command: The command to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(command, dict):
            return False
        
        # Check for required fields
        if "device" not in command or "action" not in command:
            return False
        
        # Check if device exists
        device_id = command["device"]
        if device_id not in self.device_registry:
            # Allow unknown devices for flexibility
            logger.warning(f"Command for unknown device: {device_id}")
            return True
        
        # Future enhancement: Check if action is valid for this device
        # based on capabilities
        
        return True
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the state by handling IoT commands.
        
        Args:
            state: The current state of the conversation
                Expected keys:
                - iot_commands: List of IoT commands to process
                - device_states: Current device states (optional)
                
        Returns:
            Updated state with processed IoT commands
                Added keys:
                - processed_iot_commands: Commands after processing
                - iot_command_results: Results of command execution
        """
        logger.info("Processing in IoT node")
        
        # Check if there are IoT commands to process
        commands = state.get("iot_commands", [])
        
        if not commands:
            logger.info("No IoT commands to process")
            state["processed_iot_commands"] = []
            state["iot_command_results"] = {}
            return state
        
        # Process commands
        processed_commands = []
        command_results = {}
        
        for i, command in enumerate(commands):
            # Validate command
            if not self.validate_command(command):
                logger.warning(f"Invalid IoT command: {command}")
                command_results[f"command_{i}"] = {
                    "status": "error",
                    "message": "Invalid command format"
                }
                continue
            
            # Process command (in a real implementation, this would interact with actual devices)
            try:
                device_id = command.get("device", "")
                action = command.get("action", "")
                params = command.get("params", {})
                
                logger.info(f"Processing command for device {device_id}: {action} {params}")
                
                # Simulate command execution
                command_results[f"command_{i}"] = {
                    "status": "success",
                    "device": device_id,
                    "action": action,
                    "params": params,
                    "message": f"Command executed for {device_id}"
                }
                
                processed_commands.append(command)
            except Exception as e:
                logger.error(f"Error processing IoT command: {e}")
                command_results[f"command_{i}"] = {
                    "status": "error",
                    "message": str(e)
                }
        
        # Update state
        state["processed_iot_commands"] = processed_commands
        state["iot_command_results"] = command_results
        
        return state
    
    async def process_device_descriptors(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process device descriptors from client message.
        
        Args:
            state: The current state
                Expected keys:
                - device_descriptors: Device descriptors from client
                
        Returns:
            Updated state
        """
        descriptors = state.get("device_descriptors", {})
        
        if descriptors:
            # Register devices based on descriptors
            for device_id, capabilities in descriptors.items():
                self.register_device(device_id, capabilities)
            
            logger.info(f"Processed {len(descriptors)} device descriptors")
        
        return state
    
    async def process_device_states(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process device states from client message.
        
        Args:
            state: The current state
                Expected keys:
                - device_states: Device states from client
                
        Returns:
            Updated state
        """
        device_states = state.get("device_states", {})
        
        if device_states:
            # Store device states in state for use by other nodes
            state["current_device_states"] = device_states
            logger.info(f"Processed states for {len(device_states)} devices")
        
        return state
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call the appropriate processing method based on state.
        
        Args:
            state: The current state
            
        Returns:
            Updated state
        """
        # Check which type of processing is needed
        if "device_descriptors" in state:
            return await self.process_device_descriptors(state)
        elif "device_states" in state:
            return await self.process_device_states(state)
        else:
            return await self.process(state)