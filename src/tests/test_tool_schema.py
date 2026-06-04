import pytest
from google.genai import types

from app.service.message_service import _build_initiate_call_payload


pytestmark = pytest.mark.no_db_reset


def test_initiate_call_nested_payload_properties_are_gemini_compatible() -> None:
    config = {
        "url": "https://api.voice-agents.miraiminds.co/v2/call/initiate",
        "description": "Places an outbound voice call to the user.",
        "headers": {
            "properties": [
                {"name": "Authorization", "value": "Bearer token"},
            ]
        },
        "body": {
            "required": ["payload"],
            "properties": [
                {"name": "agentId", "type": "string", "value": "agent-123"},
                {
                    "name": "payload",
                    "type": "object",
                    "description": "Arguments for the mock investor call.",
                    "required": ["first_name", "call_goal"],
                    "properties": [
                        {
                            "name": "first_name",
                            "type": "string",
                            "description": "User first name.",
                        },
                        {
                            "name": "call_goal",
                            "type": "string",
                            "description": "Goal of the mock investor call.",
                            "value": None,
                        },
                    ],
                },
            ],
        },
    }

    tool = _build_initiate_call_payload(config, "918200962919")

    assert tool is not None
    function_declaration = tool["definition"]["functionDeclarations"][0]
    payload_schema = function_declaration["parameters"]["properties"]["payload"]

    assert isinstance(payload_schema["properties"], dict)
    assert payload_schema["properties"]["first_name"] == {
        "type": "string",
        "description": "User first name.",
    }
    assert payload_schema["properties"]["call_goal"] == {
        "type": "string",
        "description": "Goal of the mock investor call.",
    }
    assert tool["execution"]["body"] == [
        {"name": "phoneNumber", "value": "918200962919"},
        {"name": "agentId", "value": "agent-123"},
    ]

    types.GenerateContentConfig(tools=[tool["definition"]])
