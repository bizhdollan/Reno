# Pre-Commit Checklist

Before committing ANY code to this project, verify all items below:

## ✅ Error Handling

### Backend (Python)
- [ ] All async functions have try-except blocks
- [ ] All database operations close sessions in `finally` blocks
- [ ] All errors are logged with `logger.error()` or `logger.exception()`
- [ ] Specific exceptions are caught before generic `Exception`
- [ ] User-friendly error messages are returned to frontend
- [ ] No silent failures (`except: pass`)
- [ ] Stack traces logged for debugging (`exc_info=True`)

### Frontend (TypeScript/React)
- [ ] All API calls are wrapped in try-catch blocks
- [ ] Loading states are cleared in `finally` blocks
- [ ] Error states are managed (useState) and displayed to users
- [ ] Errors are logged to console with component/function name
- [ ] `APIError` types are checked (`isNetworkError`, `isTimeout`, etc.)
- [ ] Error messages are user-friendly

## ✅ Code Quality

- [ ] No hardcoded values (use env variables or config)
- [ ] No commented-out code blocks (delete or explain why)
- [ ] Functions have clear, descriptive names
- [ ] Complex logic has explanatory comments
- [ ] No console.log() left in production code (use proper logging)

## ✅ Testing

- [ ] Tested happy path (feature works as expected)
- [ ] Tested error paths:
  - [ ] Invalid inputs
  - [ ] Network failures (if applicable)
  - [ ] Timeout scenarios (if applicable)
  - [ ] Missing resources (404s)
  - [ ] Server errors (500s)

## ✅ Performance

- [ ] No unnecessary API calls in loops
- [ ] Database queries are efficient (no N+1 queries)
- [ ] Large lists use pagination
- [ ] Images are optimized
- [ ] No memory leaks (event listeners cleaned up, streams closed)

## ✅ Security

- [ ] No sensitive data in logs
- [ ] User inputs are validated
- [ ] SQL injection prevented (use parameterized queries)
- [ ] XSS prevented (sanitize user input)
- [ ] CORS configured properly
- [ ] Authentication/authorization checked

## ✅ Documentation

- [ ] Complex logic is commented
- [ ] Function docstrings are accurate (if modified)
- [ ] README updated (if public API changed)
- [ ] Environment variables documented (if new ones added)

---

## Quick Error Handling Reference

### Backend Pattern
```python
async def my_function():
    try:
        result = await operation()
        return result
    except SpecificError as e:
        logger.error(f"[my_function] Error: {e}", exc_info=True)
        raise CustomError("User-friendly message") from e
    except Exception as e:
        logger.exception(f"[my_function] Unexpected error")
        raise
```

### Frontend Pattern
```typescript
try {
  setLoading(true);
  setError(null);
  const result = await api.call();
} catch (error) {
  if (error instanceof APIError) {
    setError(error.message);
  }
  console.error('[Component] Error:', error);
} finally {
  setLoading(false);
}
```

---

**Remember**: If it can fail, it will fail. Handle it gracefully.

See [DEVELOPMENT_GUIDELINES.md](./DEVELOPMENT_GUIDELINES.md) for detailed documentation.
