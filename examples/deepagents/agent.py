"""Build a fresh graph after the caller supplies this run's resources."""

import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from deepagents.middleware.skills import SkillsMiddleware
from deepagents.profiles.harness import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    register_harness_profile,
)
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI


@tool
def web_fetch(url: str) -> str:
    """Fetch the text of an HTTP or HTTPS page by URL."""
    if urlsplit(url).scheme not in {"http", "https"}:
        raise ValueError("web_fetch requires an HTTP(S) URL")
    with urlopen(url, timeout=30) as response:
        return response.read(256 * 1024).decode(response.headers.get_content_charset() or "utf-8", errors="replace")


async def build_agent_for_run(*, policy, mcp_servers, skills_directories, tools, middleware):
    model = ChatOpenAI(model=os.environ["AGENT_MODEL_NAME"])
    backend = LocalShellBackend(root_dir=os.getcwd(), virtual_mode=False)
    connections = {
        server["name"]: {
            "url": server["url"],
            "transport": "streamable_http" if server["transport"] == "http" else "sse",
        }
        for server in mcp_servers if policy.get("mcp") != "disabled"
    }
    mcp_tools = await MultiServerMCPClient(connections, tool_name_prefix=True).get_tools() if connections else []
    skills = []
    if policy.get("skills") != "disabled":
        candidates = [Path(__file__).parent / "skills", Path.cwd() / ".agents/skills",
                      Path.home() / ".agents/skills", *map(Path, skills_directories)]
        skills = list(dict.fromkeys(str(path.resolve()) for path in candidates if path.is_dir()))

    if policy.get("tools") == "none":
        # create_deep_agent registers filesystem and delegation tools even when tools=[].
        # Use its underlying LangChain graph with only explicitly supplied MCP tools.
        hooks = list(middleware)
        if skills:
            hooks.append(SkillsMiddleware(backend=backend, sources=skills))
        return create_agent(model=model, tools=mcp_tools, middleware=hooks)

    if policy.get("subagent") == "disabled":
        # The evaluator starts a fresh Python process for each solve.
        register_harness_profile(
            f"openai:{model.model_name}",
            HarnessProfile(general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)),
        )
    native_tools = [] if policy.get("webFetch") == "disabled" else [web_fetch]
    return create_deep_agent(
        model=model, backend=backend, tools=[*native_tools, *tools, *mcp_tools], skills=skills or None,
        middleware=list(middleware),
    )
