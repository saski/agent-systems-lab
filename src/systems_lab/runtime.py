"""LangChain specialist loop behind a small, replaceable runtime contract."""

import json
from pathlib import Path
from typing import Any, Protocol

import httpx
import yaml
from langchain.agents import create_agent
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict

from systems_lab.gateway import TOOLS
from systems_lab.store import CAPABILITIES


class AgentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str
    model_mode: str
    summary: str
    evidence: dict[str, Any]


class AgentRuntime(Protocol):
    def run(self, role: str, gateway_url: str, token: str) -> AgentResult: ...


class LangChainRuntime:
    def __init__(self, root: Path) -> None:
        self.root = root

    def run(self, role: str, gateway_url: str, token: str) -> AgentResult:
        if role not in CAPABILITIES:
            raise ValueError("Unknown specialist")
        directory = self.root / "agents" / role
        definition = yaml.safe_load((directory / "agent.yaml").read_text())
        if definition["id"] != role or definition["model_route"] != "fixture":
            raise ValueError("Only registered fixture specialists are enabled")
        if not set(definition["requested_capabilities"]) <= CAPABILITIES[role]:
            raise ValueError("Agent requests capabilities outside central policy")
        instructions = (directory / "persona.md").read_text()
        for skill in sorted((directory / "skills").glob("*.md")):
            instructions += "\n\n" + skill.read_text()
        name, operation = TOOLS[role]

        def authorized_operation() -> dict[str, Any]:
            """Execute the specialist's registered operation for this task."""
            with httpx.Client(timeout=30, trust_env=False) as client:
                response = client.post(
                    f"{gateway_url}/tools/{operation}",
                    headers={"Authorization": f"Bearer {token}"},
                    json={},
                )
                response.raise_for_status()
                return response.json()

        tool = StructuredTool.from_function(
            authorized_operation,
            name=name,
            description=f"Run the authorized {operation} operation for the current task.",
        )
        with httpx.Client(timeout=30, trust_env=False) as model_client:
            model = ChatOpenAI(
                model="fixture",
                base_url=f"{gateway_url}/v1",
                api_key=token,
                http_client=model_client,
                max_retries=0,
                timeout=30,
                use_responses_api=False,
                stream_usage=False,
            )
            agent = create_agent(model=model, tools=[tool], system_prompt=instructions)
            output = agent.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "Complete your assigned experiment step using its registered tool. "
                                "Return JSON with role, model_mode, summary, and evidence."
                            ),
                        }
                    ]
                },
                config={"recursion_limit": 8},
            )
        content = output["messages"][-1].content
        if not isinstance(content, str):
            raise ValueError("Expected a JSON specialist result")
        result = AgentResult.model_validate(json.loads(content))
        if result.role != role or result.model_mode != "fixture":
            raise ValueError("Specialist result provenance does not match execution")
        return result
