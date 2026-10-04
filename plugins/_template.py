"""
Drop-in Roohvi plugin template.

Copy this file, rename it (no leading underscore), fill in PLUGIN and run().
It is discovered automatically at startup.

Plugins for a wellness app must stay inside the product boundary: no diagnosis,
no medication advice, no computer control. Return a short sentence the
assistant can say in its own words.
"""

PLUGIN = {
    "name": "my_plugin",
    "description": "When the assistant should call this tool.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "example_arg": {"type": "STRING", "description": "What this argument means"},
        },
        "required": [],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        return f"Did the thing with {parameters.get('example_arg', '')}."
    except Exception as e:
        return f"my_plugin failed: {e}"
