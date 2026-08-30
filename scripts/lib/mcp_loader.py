import json
import os
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _resolve_path(val, base_dir):
    """resolve relative paths (starting with ./) against base_dir."""
    if isinstance(val, str) and val.startswith('./'):
        return os.path.abspath(os.path.join(base_dir, val))
    return val


async def load_and_register_mcp_servers(stack: AsyncExitStack, config_path: str):
    """
    dynamically loads MCP servers from a standard JSON config file,
    boots them concurrently, and builds the OpenAI-compatible tool registry.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    base_dir = os.path.dirname(os.path.abspath(config_path))
    servers = config.get("mcpServers", {})
    devnull = open(os.devnull, "w")

    sessions = []

    # boot all servers defined in the config
    for server_name, server_config in servers.items():
        command = server_config.get("command")
        args = [_resolve_path(a, base_dir) for a in server_config.get("args", [])]
        env = server_config.get("env", None)

        # merge system env if custom env is provided to ensure PATH works
        if env is not None:
            env = {k: _resolve_path(v, base_dir) for k, v in env.items()}
            merged_env = os.environ.copy()
            merged_env.update(env)
            env = merged_env

        params = StdioServerParameters(command=command, args=args, env=env)

        try:
            transport = await stack.enter_async_context(
                stdio_client(params, errlog=devnull)
            )
            session = await stack.enter_async_context(
                ClientSession(transport[0], transport[1])
            )
            await session.initialize()
            sessions.append(session)
        except Exception as e:
            print(f"[[Error initializing MCP server '{server_name}': {e}]]")

    # build MCP tool registry
    tools_list = []
    tool_router = {}

    for session in sessions:
        tools_response = await session.list_tools()
        for tool in tools_response.tools:
            tools_list.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    },
                }
            )
            tool_router[tool.name] = session

    return tools_list, tool_router
