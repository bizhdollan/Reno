# Development Guidelines

## Core Principle: Always Handle Errors Properly

**CRITICAL**: Whenever building any feature in this project, proper error handling is **mandatory**, not optional.

---

## Error Handling Standards

### 1. Backend (Python/FastAPI)

#### ✅ Required Error Handling Patterns

**All async functions must have try-except blocks:**
```python
async def my_function():
    try:
        # Function logic
        result = await some_operation()
        return result
    except SpecificError as e:
        logger.error(f"[my_function] Specific error: {e}", exc_info=True)
        # Handle or raise with context
    except Exception as e:
        logger.exception(f"[my_function] Unexpected error: {e}")
        # Graceful degradation or raise custom error
```

**Database operations must use try-finally:**
```python
db = SessionLocal()
try:
    # Database operations
    result = db.query(Model).filter(...).first()
    db.commit()
except Exception as e:
    logger.error(f"Database error: {e}", exc_info=True)
    db.rollback()
    raise
finally:
    db.close()
```

**LLM/API calls must handle retries:**
- All LLM calls automatically retry with exponential backoff (built into `LLMProvider`)
- Catch `LLMProviderError` separately from generic exceptions
- Provide user-friendly error messages

**File operations must handle I/O errors:**
```python
try:
    with open(file_path, 'r') as f:
        data = f.read()
except FileNotFoundError:
    logger.error(f"File not found: {file_path}")
    # Provide fallback or raise with context
except IOError as e:
    logger.error(f"I/O error reading {file_path}: {e}")
    raise
```

#### 📋 Logging Standards

- **`logger.error()`**: For errors that are handled
- **`logger.exception()`**: For errors with full stack trace (use in except blocks)
- **`logger.warning()`**: For non-critical issues
- **`logger.info()`**: For expected error conditions that recovered
- Always include context: function name, operation, relevant IDs

#### 🎯 Error Response Standards

```python
# Return structured errors to frontend
return {
    "error": "User-friendly error message",
    "detail": "Technical details for debugging",
    "code": "ERROR_CODE_IF_APPLICABLE"
}
```

---

### 2. Frontend (React/TypeScript)

#### ✅ Required Error Handling Patterns

**All API calls must be wrapped in try-catch:**
```typescript
try {
  const result = await api.someEndpoint();
  // Handle success
} catch (error) {
  if (error instanceof APIError) {
    if (error.isNetworkError) {
      setError("Unable to connect. Check your internet.");
    } else if (error.isTimeout) {
      setError("Request timed out. Please try again.");
    } else if (error.isServerError) {
      setError(error.message);
    }
  }
  console.error('[ComponentName] API error:', error);
} finally {
  setLoading(false); // Always clear loading states
}
```

**Components must manage error state:**
```typescript
const [error, setError] = useState<string | null>(null);
const [loading, setLoading] = useState(false);

// Clear errors on new attempts
setError(null);
setLoading(true);
```

**Display errors to users:**
```typescript
{error && (
  <div className="error-message">
    {error}
  </div>
)}
```

#### 🔄 Loading State Management

- Set loading state before async operations
- Clear loading state in `finally` block (always executes)
- Clear errors before new attempts

#### 🌐 Network Resilience

- Use `APIError` class for type-safe error handling
- Check error types: `isNetworkError`, `isTimeout`, `isServerError`, `isClientError`
- Provide retry options for transient failures

---

### 3. Common Pitfalls to Avoid

#### ❌ Don't Do This:

```python
# No error handling
async def bad_function():
    result = await risky_operation()
    return result
```

```python
# Silent failures
try:
    something()
except:
    pass  # BAD: Error is hidden
```

```python
# Generic error messages
except Exception:
    return "Error"  # BAD: Not helpful
```

```typescript
// No error handling
const data = await fetch('/api/endpoint').then(r => r.json());
```

```typescript
// Not clearing loading states
try {
  setLoading(true);
  await api.call();
  setLoading(false); // BAD: Won't execute on error
}
```

#### ✅ Do This:

```python
# Specific error handling with logging
async def good_function():
    try:
        result = await risky_operation()
        return result
    except SpecificError as e:
        logger.error(f"[good_function] Operation failed: {e}", exc_info=True)
        raise CustomError(f"User-friendly message: {str(e)}") from e
    except Exception as e:
        logger.exception(f"[good_function] Unexpected error")
        raise
```

```typescript
// Proper error handling with cleanup
try {
  setLoading(true);
  setError(null);
  await api.call();
} catch (error) {
  console.error('[Component] Error:', error);
  setError('User-friendly message');
} finally {
  setLoading(false); // Always executes
}
```

---

## Error Handling Checklist

Before committing code, verify:

### Backend
- [ ] All async functions have try-except blocks
- [ ] Database sessions are closed in finally blocks
- [ ] Errors are logged with appropriate level and context
- [ ] User-friendly error messages are returned to frontend
- [ ] Specific exceptions are caught before generic Exception
- [ ] Stack traces are logged for debugging (exc_info=True)
- [ ] Non-critical failures don't block the main workflow

### Frontend
- [ ] All API calls are in try-catch blocks
- [ ] Loading states are cleared in finally blocks
- [ ] Error states are managed and displayed to users
- [ ] Errors are logged to console for debugging
- [ ] Network/timeout errors are handled specifically
- [ ] APIError types are checked for appropriate handling

---

## Why This Matters

### User Experience
- ✅ Users see helpful error messages, not crashes
- ✅ Users know when to retry vs. report an issue
- ✅ Loading states don't get stuck

### Developer Experience
- ✅ Logs provide context for debugging
- ✅ Errors are traceable to their source
- ✅ Stack traces help identify root causes

### System Reliability
- ✅ Errors don't cascade and crash the system
- ✅ Transient failures are retried automatically
- ✅ Database connections don't leak
- ✅ Resources are properly cleaned up

---

## When Adding New Features

1. **Before writing code**: Consider what can go wrong
2. **While writing code**: Add try-except as you go
3. **Before testing**: Review error handling paths
4. **During testing**: Test error scenarios (network failures, bad inputs, etc.)
5. **Before committing**: Run through the checklist above

---

## Error Handling Examples by Use Case

### File Upload
```python
try:
    file_data = await request.file()
    if file_data.size > MAX_SIZE:
        raise ValueError("File too large")

    saved_path = await save_file(file_data)
    return {"url": saved_path}
except ValueError as e:
    logger.warning(f"Validation error: {e}")
    raise HTTPException(400, detail=str(e))
except IOError as e:
    logger.error(f"File save error: {e}", exc_info=True)
    raise HTTPException(500, detail="Failed to save file")
```

### Image Generation
```python
try:
    result = await provider.generate_image(...)
    if not result.get("image_data"):
        raise LLMProviderError("No image data returned")
    return result
except LLMProviderError as e:
    logger.error(f"[generate] LLM error: {e}", exc_info=True)
    return {
        "error": "Image generation failed. Please try again.",
        "detail": str(e)
    }
except Exception as e:
    logger.exception(f"[generate] Unexpected error")
    return {
        "error": "An unexpected error occurred.",
        "detail": "Please try again or contact support."
    }
```

### React Form Submission
```typescript
const handleSubmit = async (data: FormData) => {
  setError(null);
  setLoading(true);

  try {
    await api.submitForm(data);
    navigate('/success');
  } catch (error) {
    if (error instanceof APIError) {
      if (error.isClientError) {
        setError(error.message); // Validation error
      } else if (error.isNetworkError) {
        setError("No internet connection");
      } else {
        setError("Server error. Please try again.");
      }
    }
    console.error('[Form] Submit error:', error);
  } finally {
    setLoading(false);
  }
};
```

---

## Resources

### Backend
- LLM Provider: `/backend/src/core/llm/provider.py` - Built-in retry logic
- Logger: `from src.core.logger import get_logger`
- Custom Errors: `from src.core.llm.exceptions import LLMProviderError`

### Frontend
- API Client: `/frontend/src/lib/api.ts` - Enhanced error handling
- APIError class: Typed errors with classification
- ContextStream: Auto-reconnecting SSE with exponential backoff

---

## Remember

> **"If it can fail, it will fail. Handle it gracefully."**

Error handling is not extra work - it's core functionality. A feature without error handling is an incomplete feature.
