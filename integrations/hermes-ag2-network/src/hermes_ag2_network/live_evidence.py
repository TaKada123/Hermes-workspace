"""Fail-closed public transcript evidence; private arguments/results never exported."""
from __future__ import annotations

import json

from .live_runtime import AcceptanceBlocked, digest


def turn_tools(rows: list[dict], input_text: str, output: str, created_at=None, updated_at=None) -> tuple[list[str], list[dict]]:
    starts = [i for i, row in enumerate(rows) if row.get('role') == 'user' and row.get('content') == input_text]
    if created_at is not None or updated_at is not None:
        if (not isinstance(created_at, (int, float)) or not isinstance(updated_at, (int, float))
                or created_at > updated_at):
            raise AcceptanceBlocked('Run timing boundaries unavailable')
        starts = [i for i in starts if isinstance(rows[i].get('timestamp'), (int, float))
                  and created_at <= rows[i]['timestamp'] <= updated_at]
    if not input_text or len(starts) != 1 or not isinstance(output, str) or not output:
        raise AcceptanceBlocked('Run input/output boundaries unavailable or ambiguous; no session-wide evidence accepted')
    start = starts[0]
    end = next((i for i in range(start + 1, len(rows)) if rows[i].get('role') == 'user'), len(rows))
    turn = rows[start + 1:end]
    if not turn or turn[-1].get('role') != 'assistant' or turn[-1].get('content') != output:
        raise AcceptanceBlocked('Run terminal output does not correlate with current input turn')
    if created_at is not None and (not isinstance(turn[-1].get('timestamp'), (int, float))
            or not created_at <= turn[-1]['timestamp'] <= updated_at):
        raise AcceptanceBlocked('Run terminal output timestamp is outside Run boundaries')
    names, evidence = [], []
    seen = set()
    for i, row in enumerate(turn):
        for call in row.get('tool_calls') or []:
            identifier = call.get('id')
            function = call.get('function', {})
            name = function.get('name')
            if not identifier or identifier in seen or not isinstance(name, str):
                raise AcceptanceBlocked('Malformed/duplicated tool-call evidence')
            seen.add(identifier)
            results = [r for r in turn[i + 1:] if r.get('role') == 'tool' and r.get('tool_call_id') == identifier]
            if len(results) != 1 or results[0].get('content') is None:
                raise AcceptanceBlocked('Tool invocation lacks exactly one correlated result')
            arguments = function.get('arguments', {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except ValueError:
                    raise AcceptanceBlocked('Malformed tool arguments evidence') from None
            if not isinstance(arguments, dict):
                raise AcceptanceBlocked('Malformed tool arguments evidence')
            invoked = [name]
            if name == 'tool_call':
                calls = arguments.get('calls')
                if not isinstance(calls, list) or not calls:
                    raise AcceptanceBlocked('Malformed deferred invocation evidence')
                for child in calls:
                    if not isinstance(child, dict) or not isinstance(child.get('name'), str) or not isinstance(child.get('arguments'), dict):
                        raise AcceptanceBlocked('Malformed deferred invocation evidence')
                    invoked.append(child['name'])
            names.extend(invoked)
            evidence.append({'tool_call_id': identifier, 'tool_names': invoked,
                             'arguments_sha256': digest(json.dumps(arguments, sort_keys=True)),
                             'result_sha256': digest(json.dumps(results[0]['content'], sort_keys=True))})
    return names, evidence
