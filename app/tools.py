"""Function tools: the @tool decorator, strict JSON schemas and a safe executing registry."""

from __future__ import annotations

import asyncio
import inspect
import json
import re
import time
import typing
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, ValidationError, create_model

TRUNCATION_MARKER = "…[truncated]"
_TOOL_NAME_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")
_MAX_ERROR_CHARS = 1000
# Schema keywords that are noise for the model or rejected by OpenAI strict mode.
_DROP_KEYS = frozenset({"title", "default", "examples", "discriminator"})


@dataclass
class ToolResult:
    ok: bool
    output: str
    error: str | None
    duration_ms: int
    truncated: bool


@dataclass
class Tool:
    name: str
    description: str
    params_model: type[BaseModel]
    func: Callable[..., Any]  # sync or async
    untrusted_output: bool = False  # external content -> injection scan + spotlight
    timeout_s: float = 20.0
    max_output_chars: int = 6000

    def schema(self) -> dict:
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": strict_schema(self.params_model),
            "strict": True,
        }

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Call the underlying function directly (handy in tests and scripts)."""
        return self.func(*args, **kwargs)


def tool(
    _func: Callable[..., Any] | None = None,
    /,
    *,
    name: str | None = None,
    description: str | None = None,
    untrusted_output: bool = False,
    timeout_s: float = 20.0,
    max_output_chars: int = 6000,
) -> Any:
    """Turn a typed function into a Tool. Use as ``@tool()`` or ``@tool(name=..., ...)``.

    Parameters come from the type hints (str, int, float, bool, list[str], Literal,
    Optional, Annotated[..., Field(description=...)]); the description defaults to
    the docstring. Returns the Tool object.
    """

    def build(func: Callable[..., Any]) -> Tool:
        tool_name = name or func.__name__
        if not _TOOL_NAME_RE.fullmatch(tool_name):
            raise ValueError(f"invalid tool name {tool_name!r}: use letters, digits, _ or - (max 64)")
        doc = description or inspect.getdoc(func) or tool_name.replace("_", " ")
        return Tool(
            name=tool_name,
            description=doc.strip(),
            params_model=params_model_from_function(func, _pascal(tool_name) + "Params"),
            func=func,
            untrusted_output=untrusted_output,
            timeout_s=timeout_s,
            max_output_chars=max_output_chars,
        )

    return build(_func) if _func is not None else build


def params_model_from_function(func: Callable[..., Any], model_name: str) -> type[BaseModel]:
    """Pydantic model with one field per function parameter (extra keys are rejected)."""
    try:
        hints = typing.get_type_hints(func, include_extras=True)
    except Exception as exc:
        raise TypeError(f"cannot resolve type hints of {func.__qualname__}: {exc}") from exc
    field_defs: dict[str, Any] = {}
    for param in inspect.signature(func).parameters.values():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD, param.POSITIONAL_ONLY):
            raise TypeError(f"tool {func.__qualname__}: parameter {param.name!r} must be a normal named parameter")
        if param.name not in hints:
            raise TypeError(f"tool {func.__qualname__}: parameter {param.name!r} needs a type hint")
        default = ... if param.default is inspect.Parameter.empty else param.default
        field_defs[param.name] = (hints[param.name], default)
    return create_model(model_name, __config__=ConfigDict(extra="forbid"), **field_defs)


def _pascal(name: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in re.split(r"[_\-]+", name) if part) or "Tool"


# --- strict JSON schema ---------------------------------------------------------------


def strict_schema(model: type[BaseModel]) -> dict:
    """``model_json_schema()`` made acceptable to OpenAI strict mode.

    $refs are inlined (recursive models are rejected), every object gets
    ``additionalProperties: false`` and ``required`` = all of its properties,
    ``title``/``default`` noise is removed, ``oneOf`` becomes ``anyOf`` and
    Optional fields stay ``anyOf [..., {"type": "null"}]``. Free-form dicts are
    not representable in strict mode and end up as empty objects.
    """
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})
    return _strictify(_inline_refs(schema, defs, ()))


def _inline_refs(node: Any, defs: dict, stack: tuple[str, ...]) -> Any:
    if isinstance(node, list):
        return [_inline_refs(item, defs, stack) for item in node]
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if isinstance(ref, str):
        prefix = "#/$defs/"
        def_name = ref[len(prefix):] if ref.startswith(prefix) else None
        if def_name not in defs:
            raise ValueError(f"cannot resolve schema reference {ref!r}")
        if def_name in stack:
            raise ValueError(f"recursive model {def_name!r} cannot be used in a strict schema")
        resolved = _inline_refs(defs[def_name], defs, (*stack, def_name))
        siblings = {k: _inline_refs(v, defs, stack) for k, v in node.items() if k != "$ref"}
        return {**resolved, **siblings}
    return {key: _inline_refs(value, defs, stack) for key, value in node.items()}


def _strictify(node: Any) -> Any:
    if isinstance(node, list):
        return [_strictify(item) for item in node]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in _DROP_KEYS:
            continue
        if key == "properties" and isinstance(value, dict):
            # Keys here are field names (a field may well be called "title"); keep them all.
            out[key] = {prop: _strictify(sub) for prop, sub in value.items()}
        elif key == "oneOf":
            out["anyOf"] = _strictify(value)
        else:
            out[key] = _strictify(value)

    all_of = out.get("allOf")
    if isinstance(all_of, list) and len(all_of) == 1 and isinstance(all_of[0], dict):
        rest = {k: v for k, v in out.items() if k != "allOf"}
        out = {**all_of[0], **rest}

    if out.get("type") == "object" or "properties" in out:
        properties = out.setdefault("properties", {})
        out["required"] = list(properties)
        out["additionalProperties"] = False
    return out


# --- registry and execution -------------------------------------------------------------


def truncate(text: str, limit: int) -> tuple[str, bool]:
    if limit and len(text) > limit:
        return text[:limit] + TRUNCATION_MARKER, True
    return text, False


def _parse_arguments(arguments: Any) -> dict:
    if isinstance(arguments, dict):
        return arguments
    if arguments is None or not str(arguments).strip():
        return {}
    data = json.loads(arguments)
    if not isinstance(data, dict):
        raise TypeError("tool arguments must be a JSON object")
    return data


def _format_validation_error(exc: ValidationError) -> str:
    parts = []
    for error in exc.errors(include_url=False)[:5]:
        location = ".".join(str(part) for part in error.get("loc", ())) or "arguments"
        parts.append(f"{location}: {error.get('msg', 'invalid')}")
    return "invalid arguments: " + "; ".join(parts)


def _elapsed_ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


class ToolRegistry:
    def __init__(self, tools: Iterable[Tool] = ()) -> None:
        self._tools: dict[str, Tool] = {}
        for item in tools:
            self.register(item)

    def register(self, tool: Tool) -> Tool:
        if not isinstance(tool, Tool):
            raise TypeError("register() expects a Tool; decorate the function with @tool() first")
        existing = self._tools.get(tool.name)
        if existing is not None and existing is not tool:
            raise ValueError(f"a different tool named {tool.name!r} is already registered")
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def schemas(self, names: list[str]) -> list[dict]:
        missing = [n for n in names if n not in self._tools]
        if missing:
            raise ValueError(f"unknown tool(s) in allowlist: {', '.join(missing)}")
        return [self._tools[n].schema() for n in names]

    async def execute(self, name: str, arguments_json: str) -> ToolResult:
        """Validate and run a tool. Never raises: every failure becomes ``ok=False``."""
        started = time.perf_counter()
        tool = self._tools.get(name)
        try:
            if tool is None:
                raise LookupError(f"unknown tool {name!r}")
            params = tool.params_model.model_validate(_parse_arguments(arguments_json))
            kwargs = {key: getattr(params, key) for key in type(params).model_fields}
            if inspect.iscoroutinefunction(tool.func):
                pending = tool.func(**kwargs)
            else:
                pending = asyncio.to_thread(tool.func, **kwargs)
            value = await asyncio.wait_for(pending, timeout=tool.timeout_s)
            text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
            text, truncated = truncate(text, tool.max_output_chars)
            return ToolResult(ok=True, output=text, error=None, duration_ms=_elapsed_ms(started), truncated=truncated)
        except (asyncio.TimeoutError, TimeoutError):
            timeout = tool.timeout_s if tool else 0
            error = f"TimeoutError: tool {name!r} timed out after {timeout:g}s"
        except ValidationError as exc:
            error = f"ValidationError: {_format_validation_error(exc)}"
        except json.JSONDecodeError as exc:
            error = f"JSONDecodeError: arguments are not valid JSON ({exc})"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        if len(error) > _MAX_ERROR_CHARS:
            error = error[: _MAX_ERROR_CHARS - 1] + "…"
        return ToolResult(
            ok=False, output=f"ERROR: {error}", error=error, duration_ms=_elapsed_ms(started), truncated=False
        )
