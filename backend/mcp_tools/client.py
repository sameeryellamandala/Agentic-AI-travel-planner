"""Managed stdio MCP connection and an authoritative ledger of tool responses."""

import json
import os
import sys
from contextlib import asynccontextmanager, contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any, Type
from anyio.from_thread import start_blocking_portal
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, PrivateAttr, create_model
from schemas.research import ResearchFindings
from utils.evidence import compact


def disable_tool_cache(*args):
    return False


@asynccontextmanager
async def connect(requirements):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_tools.server"],
        cwd=str(Path(__file__).resolve().parents[1]),
        env={**os.environ, "TRAVEL_REQUIREMENTS": json.dumps(requirements)},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(
            read, write, read_timeout_seconds=timedelta(seconds=90)
        ) as session:
            await session.initialize()
            yield session


class ResearchLedger:
    def __init__(self):
        self.findings = ResearchFindings()

    def record(self, name, args, result):
        f = self.findings
        f.tool_trace.append(
            {
                "tool": name,
                "args": args,
                "result": result,
                "cached": result.get("cached", False),
            }
        )
        if not result.get("success"):
            f.warnings.append(
                f"{name}: {result.get('reason', 'Information unavailable')}"
            )
        for warning in result.get("warnings", []):
            f.warnings.append(f"{name}: {warning}")
        if name == "get_weather":
            f.weather[str(args["day"])] = result
        elif name == "search_transport":
            f.transport[args["leg_id"]] = result
        elif name == "search_stay":
            f.stays[args["stay_id"]] = result
        else:
            for item in result.get("places", []) + result.get("food_items", []):
                f.candidates[item["candidate_id"]] = item


@contextmanager
def research_tools(requirements):
    from crewai.tools import BaseTool

    class MCPTool(BaseTool):
        args_schema: Type[BaseModel]
        _portal: Any = PrivateAttr()
        _session: Any = PrivateAttr()
        _ledger: Any = PrivateAttr()

        def _run(self, **kwargs):
            response = self._portal.call(self._session.call_tool, self.name, kwargs)
            if response.isError:
                result = {"success": False, "reason": "MCP tool returned an error"}
            elif response.structuredContent is not None:
                result = response.structuredContent
            else:
                result = json.loads(
                    "".join(
                        block.text for block in response.content if block.type == "text"
                    )
                )
            self._ledger.record(self.name, kwargs, result)
            prompt_result = compact(result)
            for field in ("places", "food_items"):
                prompt_result[field] = [
                    {
                        key: (
                            value[:220]
                            if key == "description" and isinstance(value, str)
                            else value
                        )
                        for key, value in item.items()
                        if key
                        in (
                            "candidate_id",
                            "name",
                            "description",
                            "day",
                            "location",
                            "kind",
                        )
                        and not (
                            key == "description" and result.get("knowledge_reused")
                        )
                    }
                    for item in prompt_result.get(field, [])
                ]
            return json.dumps(prompt_result)

    ledger = ResearchLedger()
    with start_blocking_portal() as portal:
        with portal.wrap_async_context_manager(connect(requirements)) as session:
            available = portal.call(session.list_tools)
            tools = []
            for spec in available.tools:
                fields = {}
                for name, field in spec.inputSchema.get("properties", {}).items():
                    annotation = int if field.get("type") == "integer" else str
                    default = (
                        ...
                        if name in spec.inputSchema.get("required", [])
                        else field.get("default", "")
                    )
                    fields[name] = (annotation, default)
                tool = MCPTool(
                    name=spec.name,
                    description=spec.description or spec.name,
                    args_schema=create_model(f"{spec.name}Arguments", **fields),
                    cache_function=disable_tool_cache,
                )
                tool._portal, tool._session, tool._ledger = portal, session, ledger
                tools.append(tool)
            yield tools, ledger
