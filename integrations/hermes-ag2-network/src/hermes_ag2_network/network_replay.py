"""Authenticated native-WAL replay of completed outbound operations; no new envelopes."""
import json

from ag2.network import EV_TEXT
from .types import ExecutionUncertain


def matching_completed_reply(envelopes, *, sender_id, peer_id, operation_id, text, artifact_refs):
    """Only a peer's correlated successful terminal reply permits local replay.

    Rejected/pending/status operations keep the existing admission/reconciliation path.
    Payload mismatch is rejected before submission even after transport reservation release.
    """
    requests = [e for e in envelopes if e.event_type == EV_TEXT and e.sender_id == sender_id
                and e.event_data.get('kind') == 'request' and e.event_data.get('operation_id') == operation_id]
    ids = {request.envelope_id for request in requests}
    completed = next((e for e in envelopes if e.event_type == EV_TEXT and e.sender_id == peer_id
                     and e.event_data.get('kind') == 'reply' and e.event_data.get('operation_id') == operation_id
                     and e.causation_id in ids), None)
    if completed is None:
        return None
    expected = json.dumps({'text': text, 'artifact_refs': artifact_refs}, sort_keys=True, separators=(',', ':'))
    for request in requests:
        actual = json.dumps({'text': request.event_data.get('text'),
                             'artifact_refs': request.event_data.get('artifact_refs', [])},
                            sort_keys=True, separators=(',', ':'))
        if actual != expected:
            raise ExecutionUncertain('operation_id reused with different input in this project channel; no automatic retry')
    return completed
