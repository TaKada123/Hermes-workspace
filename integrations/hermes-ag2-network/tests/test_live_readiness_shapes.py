"""Public CLI gate rejects HTML and accepts the documented Sessions list API."""
import json



def test_documented_sessions_list_is_ready_without_exporting_private_rows(cli, endpoint):
    run, receipt, _, _ = cli
    url, state = endpoint
    state['body'] = '{"object":"list","data":[{"title":"private-title"}],"has_more":false}'
    result = run(url)
    assert result.returncode == 0
    saved = json.loads(receipt.read_text())
    assert saved['ready'] is True
    assert saved['profiles']['coding']['sessions_schema'] == 'list.data'
    assert 'private-title' not in result.stdout


def test_html_fallback_has_specific_safe_diagnosis(cli, endpoint):
    run, receipt, _, _ = cli
    url, state = endpoint
    state['body'] = '<!doctype html><html>private-title</html>'
    result = run(url)
    assert result.returncode == 2
    saved = json.loads(receipt.read_text())
    assert saved['profiles']['coding']['response_kind'] == 'html'
    assert 'HTML fallback' in ' '.join(saved['blockers'])
    assert 'private-title' not in result.stdout
