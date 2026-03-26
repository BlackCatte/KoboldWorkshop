import asyncio
import aiohttp
import json
import logging
from typing import AsyncGenerator, Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class KoboldCPPClient:
    """Client for KoboldCPP API with SSE streaming support"""
    
    def __init__(self, base_url: str = "http://localhost:5001"):
        self.base_url = base_url
        self.stream_endpoint = f"{base_url}/api/extra/generate/stream/"
        self.generate_endpoint = f"{base_url}/api/v1/generate"
        self.model_endpoint = f"{base_url}/api/v1/model"
        
    async def check_connection(self) -> bool:
        """Check if KoboldCPP is available"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"KoboldCPP connection failed: {e}")
            return False
    
    async def get_model_info(self) -> Optional[Dict[str, Any]]:
        """Get current model information"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.model_endpoint) as response:
                    if response.status == 200:
                        return await response.json()
                    return None
        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
            return None
    
    async def generate_stream(self, 
                            prompt: str, 
                            max_length: int = 200,
                            temperature: float = 0.7,
                            top_p: float = 0.9,
                            top_k: int = 40,
                            stop_sequences: Optional[list] = None) -> AsyncGenerator[str, None]:
        """Stream tokens from KoboldCPP using SSE"""
        
        payload = {
            "prompt": prompt,
            "max_length": max_length,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "n": 1,
        }
        
        if stop_sequences:
            payload["stop_sequence"] = stop_sequences
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Connection": "keep-alive"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.stream_endpoint,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=300)  # 5 min timeout
                ) as response:
                    
                    if response.status != 200:
                        logger.error(f"KoboldCPP returned status {response.status}")
                        return
                    
                    logger.info("Started SSE stream from KoboldCPP")
                    
                    async for line in response.content:
                        if line:
                            line_str = line.decode('utf-8').strip()
                            
                            # SSE format: "data: {json}"
                            if line_str.startswith('data: '):
                                try:
                                    data_str = line_str[6:]  # Remove "data: " prefix
                                    data = json.loads(data_str)
                                    
                                    # Extract token from response
                                    if 'token' in data:
                                        yield data['token']
                                    elif 'results' in data and len(data['results']) > 0:
                                        text = data['results'][0].get('text', '')
                                        if text:
                                            yield text
                                    
                                except json.JSONDecodeError:
                                    # Sometimes we get raw text
                                    if data_str:
                                        yield data_str
                                except Exception as e:
                                    logger.error(f"Error parsing SSE data: {e}")
                    
                    logger.info("SSE stream completed")
                    
        except asyncio.TimeoutError:
            logger.error("KoboldCPP stream timeout")
        except Exception as e:
            logger.error(f"Error during streaming: {e}")
    
    async def generate(self,
                      prompt: str,
                      max_length: int = 200,
                      temperature: float = 0.7,
                      top_p: float = 0.9,
                      top_k: int = 40,
                      stop_sequences: Optional[list] = None) -> Optional[str]:
        """Non-streaming generation (fallback)"""
        
        payload = {
            "prompt": prompt,
            "max_length": max_length,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
        }
        
        if stop_sequences:
            payload["stop_sequence"] = stop_sequences
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.generate_endpoint,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        if 'results' in data and len(data['results']) > 0:
                            return data['results'][0].get('text', '')
                    
                    logger.error(f"Generation failed with status {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error during generation: {e}")
            return None
    
    async def detect_tool_calls(self, text: str) -> list:
        """Parse text for potential tool calls (simple regex-based for now)"""
        import re
        
        # Pattern for function calls: function_name(arg1, arg2)
        pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\(([^)]*)\)'
        matches = re.findall(pattern, text)
        
        tool_calls = []
        for func_name, args_str in matches:
            tool_calls.append({
                'function': func_name,
                'arguments': args_str,
                'raw': f"{func_name}({args_str})"
            })
        
        return tool_calls
