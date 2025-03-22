"""
IoT tools for the LangGraph agent.
"""
from typing import Any, Dict, List, Optional

from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class IoTTools:
    """
    Tools for interacting with IoT devices.
    
    These tools can be used by the agent's nodes to control and query IoT devices.
    """
    
    @staticmethod
    def generate_command(device_id: str, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate an IoT command.
        
        Args:
            device_id: The device identifier
            action: The action to perform
            params: Optional parameters for the action
            
        Returns:
            IoT command dictionary
        """
        command = {
            "device": device_id,
            "action": action,
        }
        
        if params:
            command["params"] = params
        
        return command
    
    @staticmethod
    def format_device_state(device_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format a device state for sending to clients.
        
        Args:
            device_id: The device identifier
            state: The device state
            
        Returns:
            Formatted device state
        """
        return {
            "device": device_id,
            "state": state
        }
    
    @staticmethod
    def get_device_capabilities_prompt(devices: Dict[str, Dict[str, Any]]) -> str:
        """
        Generate a prompt describing available IoT devices and their capabilities.
        
        This is useful for adding to the LLM system prompt to inform it about
        available devices and how to control them.
        
        Args:
            devices: Dictionary of devices and their capabilities
            
        Returns:
            Prompt text describing the devices
        """
        prompt = "Available IoT devices:\n\n"
        
        for device_id, capabilities in devices.items():
            prompt += f"Device: {device_id}\n"
            
            if "name" in capabilities:
                prompt += f"Name: {capabilities['name']}\n"
                
            if "type" in capabilities:
                prompt += f"Type: {capabilities['type']}\n"
                
            if "actions" in capabilities:
                prompt += "Actions:\n"
                for action, action_info in capabilities["actions"].items():
                    prompt += f"  - {action}: {action_info.get('description', '')}\n"
                    
                    if "params" in action_info:
                        prompt += "    Parameters:\n"
                        for param, param_info in action_info["params"].items():
                            prompt += f"      - {param}: {param_info.get('description', '')}\n"
            
            prompt += "\n"
        
        prompt += "\nTo control a device, include a command in your response in this format:\n"
        prompt += '{"device": "device_id", "action": "action_name", "params": {"param1": "value1"}}\n'
        
        return prompt


# Example usage
def test_iot_tools():
    """Test IoT tools functionality."""
    # Define example device capabilities
    devices = {
        "light1": {
            "name": "Living Room Light",
            "type": "light",
            "actions": {
                "turn_on": {
                    "description": "Turn the light on"
                },
                "turn_off": {
                    "description": "Turn the light off"
                },
                "set_brightness": {
                    "description": "Set the light brightness",
                    "params": {
                        "brightness": {
                            "description": "Brightness level (0-100)",
                            "type": "integer",
                            "min": 0,
                            "max": 100
                        }
                    }
                },
                "set_color": {
                    "description": "Set the light color",
                    "params": {
                        "color": {
                            "description": "Color name or hex code",
                            "type": "string"
                        }
                    }
                }
            }
        }
    }
    
    # Generate a command
    command = IoTTools.generate_command(
        "light1", 
        "set_brightness", 
        {"brightness": 75}
    )
    
    print(f"Command: {command}")
    
    # Generate a prompt
    prompt = IoTTools.get_device_capabilities_prompt(devices)
    
    print(f"Prompt:\n{prompt}")


if __name__ == "__main__":
    test_iot_tools() 