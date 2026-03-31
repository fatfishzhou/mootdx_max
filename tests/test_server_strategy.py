import importlib

server_mod = importlib.import_module('mootdx.server')


def test_probe_failure_sets_cooldown():
    proxy = {'addr': '1.2.3.4', 'port': 7709, 'time': None, 'site': 'x'}
    server_mod._probe_state['HQ'].clear()

    server_mod._probe_failure('HQ', proxy, now=100.0)
    state = server_mod._probe_snapshot('HQ', proxy)

    assert state['failures'] == 1
    assert state['cooldown_until'] == 130.0


def test_available_hosts_skips_cooling_hosts():
    proxy = server_mod.hosts['HQ'][0]
    server_mod._probe_state['HQ'].clear()
    server_mod._probe_failure('HQ', proxy, now=10.0)

    hosts = server_mod._available_hosts('HQ', now=20.0)

    assert (proxy['addr'], int(proxy['port'])) not in {(item['addr'], int(item['port'])) for item in hosts}


def test_probe_success_clears_penalty():
    proxy = {'addr': '1.2.3.4', 'port': 7709, 'time': None, 'site': 'x'}
    server_mod._probe_state['HQ'].clear()
    server_mod._probe_failure('HQ', proxy, now=100.0)

    server_mod._probe_success('HQ', proxy)
    state = server_mod._probe_snapshot('HQ', proxy)

    assert state == {'failures': 0, 'cooldown_until': 0.0}
