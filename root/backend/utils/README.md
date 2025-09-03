# Utility Modules

## Serialization

The `serialization.py` module provides robust utilities for handling JSON serialization across the application, solving common issues with complex object types.

### Key Features

- **Universal Object Serialization**: Handles any object type including Pydantic models, dataclasses, nested objects, and custom classes
- **Consistent Error Handling**: Provides standardized error formatting for API endpoints
- **Response Decorator**: Simplifies API endpoint code with automatic serialization

### Functions

#### `serialize_object(obj)`

Recursively serializes any object to a JSON-serializable format. Handles:
- Pydantic models
- Dataclasses
- Lists, tuples, and sets
- Dictionaries
- Basic types
- Custom objects with `__dict__` attribute

```python
from root.backend.utils.serialization import serialize_object

# Any complex object
result = serialize_object(my_complex_object)
```

#### `to_json(obj, indent=None)`

Converts any object to a JSON string.

```python
from root.backend.utils.serialization import to_json

json_string = to_json(my_object, indent=2)
```

#### `from_json(json_str)`

Parses a JSON string into Python objects.

```python
from root.backend.utils.serialization import from_json

data = from_json(json_string)
```

#### `model_to_dict(model)`

Specifically converts Pydantic models to dictionaries, handling nested models.

```python
from root.backend.utils.serialization import model_to_dict

model_dict = model_to_dict(my_pydantic_model)
```

### Decorator Usage

The `@serialize_response` decorator automatically handles serialization and error handling for FastAPI endpoints.

```python
from fastapi import APIRouter
from root.backend.utils.serialization import serialize_response

router = APIRouter()

@router.post("/process")
@serialize_response
async def process_data(data: dict):
    # Your logic here
    return {
        "result": complex_object,  # Will be properly serialized
        "status": "success"
    }
```

### Best Practices

1. **For New Endpoints**: Use the `@serialize_response` decorator
2. **For Manual Serialization**: Use `serialize_object` for dictionaries before passing to `JSONResponse`
3. **For Error Handling**: Let the decorator handle it, or use the pattern:
   ```python
   try:
       # Your code
   except Exception as e:
       error_detail = {
           "error": f"Operation failed: {str(e)}",
           "type": str(type(e).__name__),
           "details": str(e)
       }
       return JSONResponse(
           content=serialize_object(error_detail),
           status_code=500
       )
   ```

### Type Support

| Object Type | Handling Method |
|-------------|-----------------|
| Pydantic BaseModel | Uses `model_dump()` |
| Dataclasses | Uses `dataclasses.asdict()` |
| Lists/Tuples | Recursively serializes elements |
| Dictionaries | Recursively serializes keys and values |
| Basic types | Returned as-is |
| Custom objects | Uses `__dict__` or string representation |