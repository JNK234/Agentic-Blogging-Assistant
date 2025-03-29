"""
Serialization utilities for handling model serialization consistently across the application.
Provides functions to standardize serialization of different object types to JSON.
Also includes a decorator for FastAPI endpoints to ensure all responses are properly serialized.
"""
import json
import dataclasses
from typing import Any, Dict, List, Union, Optional
from pydantic import BaseModel


def serialize_object(obj: Any, depth: int = 0, max_depth: int = 10) -> Any:
    """
    Recursively serialize an object to a JSON-serializable format.
    
    This function handles various types of objects:
    - Pydantic models using model_dump()
    - Dataclasses using asdict()
    - Lists, tuples, and sets by recursively serializing elements
    - Dictionaries by recursively serializing keys and values
    - Basic types (str, int, float, bool, None) are returned as is
    
    Args:
        obj: Any object to serialize
        depth: Current recursion depth (used internally)
        max_depth: Maximum allowed recursion depth
        
    Returns:
        JSON-serializable representation of the object
    """
    # Check recursion depth
    if depth > max_depth:
        return str(obj)
    
    # Handle None
    if obj is None:
        return None
        
    # Handle Pydantic BaseModel instances
    if isinstance(obj, BaseModel):
        return serialize_object(obj.model_dump(), depth + 1, max_depth)
        
    # Handle dataclasses
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return serialize_object(dataclasses.asdict(obj), depth + 1, max_depth)
        
    # Handle lists, tuples, and sets
    if isinstance(obj, (list, tuple, set)):
        return [serialize_object(item, depth + 1, max_depth) for item in obj]
        
    # Handle dictionaries
    if isinstance(obj, dict):
        return {str(k): serialize_object(v, depth + 1, max_depth) for k, v in obj.items()}
        
    # Handle basic types
    if isinstance(obj, (str, int, float, bool)):
        return obj
        
    # Handle any other object by converting to string
    try:
        # Try to convert to dict if the object has a __dict__ attribute
        if hasattr(obj, "__dict__"):
            return serialize_object(obj.__dict__, depth + 1, max_depth)
        # Fallback to string representation
        return str(obj)
    except Exception:
        return str(obj)


def to_json(obj: Any, indent: Optional[int] = None) -> str:
    """
    Convert an object to a JSON string.
    
    Args:
        obj: Any object to convert to JSON
        indent: Optional indentation level for pretty-printing
        
    Returns:
        JSON string representation of the object
    """
    serialized = serialize_object(obj)
    return json.dumps(serialized, indent=indent)


def from_json(json_str: str) -> Any:
    """
    Convert a JSON string back to a Python object.
    
    Args:
        json_str: JSON string to parse
        
    Returns:
        Python dictionary or list representation of the JSON
    """
    return json.loads(json_str)


def model_to_dict(model: Union[BaseModel, Any]) -> Dict:
    """
    Convert a Pydantic model to a dictionary, handling nested models.
    
    Args:
        model: Pydantic model or other object to convert
        
    Returns:
        Dictionary representation of the model
    """
    return serialize_object(model)


import functools
import inspect
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger("serialization")

def serialize_response(func):
    """
    Decorator for FastAPI endpoint functions to ensure response is properly serialized.
    Will automatically handle exceptions and convert all responses to properly serialized JSONResponse objects.
    
    Usage:
        @app.post("/endpoint")
        @serialize_response
        async def my_endpoint():
            # Your code here
            return {"result": complex_object}  # Will be automatically serialized
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            # Call the original function
            result = await func(*args, **kwargs) if inspect.iscoroutinefunction(func) else func(*args, **kwargs)
            
            # If result is already a Response object, return it as is
            from fastapi.responses import Response
            if isinstance(result, Response):
                return result
                
            # Otherwise, serialize the result
            return JSONResponse(content=serialize_object(result))
            
        except Exception as e:
            # Log the exception
            logger.exception(f"Error in {func.__name__}: {str(e)}")
            
            # Create error response with detailed information
            error_detail = {
                "error": f"{func.__name__} failed: {str(e)}",
                "type": str(type(e).__name__),
                "details": str(e)
            }
            
            # Return serialized error response
            return JSONResponse(
                content=serialize_object(error_detail),
                status_code=500
            )
            
    return wrapper
