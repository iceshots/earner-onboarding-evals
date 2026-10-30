"""The two fixed tools Bot A can call. Plain Python over SQLite; no LLM."""
from .aggregate_stuck import aggregate_stuck
from .errors import ToolValidationError
from .get_earner_status import get_earner_status

TOOL_FUNCTIONS = {
    "get_earner_status": get_earner_status,
    "aggregate_stuck": aggregate_stuck,
}


def dispatch(name: str, arguments: dict) -> dict:
    """Run a tool by name. Validation problems come back as {"error": ...} so the model can recover."""
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return {"error": f"Unknown tool {name!r}. Available tools: {', '.join(TOOL_FUNCTIONS)}."}
    try:
        return fn(**(arguments or {}))
    except ToolValidationError as e:
        return {"error": str(e)}
    except TypeError as e:  # wrong or missing argument names
        return {"error": f"Bad arguments for {name}: {e}"}
