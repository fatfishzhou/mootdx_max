from types import SimpleNamespace

import pytest

from mootdx.quotes import Quotes


class DummyStdApi:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.client = SimpleNamespace(_closed=True)
        self.connect_calls = []
        self._connect_result = True

    def connect(self, ip, port, time_out=None):
        self.connect_calls.append((ip, port, time_out))
        self.client._closed = not self._connect_result
        return self._connect_result

    def get_traffic_stats(self):
        return {'send_pkg_num': 1, 'recv_pkg_num': 2}

    def close(self):
        self.client._closed = True


def _patch_std_config(monkeypatch):
    monkeypatch.setattr('mootdx.quotes.config.setup', lambda: True)
    monkeypatch.setattr('mootdx.quotes.config.set', lambda *args, **kwargs: None)
    monkeypatch.setattr(
        'mootdx.quotes.config.get',
        lambda key, default=None: {
            'SERVER': {'HQ': [('110.41.147.114', 7709)]},
            'BESTIP': {'HQ': ('110.41.147.114', 7709)},
        }.get(key, default),
    )
    monkeypatch.setattr('mootdx.quotes.TdxHq_API', DummyStdApi)


def test_stdquotes_normalizes_request_controls_and_reports_health(monkeypatch):
    _patch_std_config(monkeypatch)

    client = Quotes.factory(
        market='std',
        timeout=3,
        request_interval='0.25',
        requests_per_minute='12',
        strict_connect='yes',
    )

    health = client.health()

    assert client.request_control == {
        'request_interval': 0.25,
        'requests_per_minute': 12,
        'strict_connect': True,
    }
    assert health['closed'] is False
    assert health['connected'] is True
    assert health['strict_connect'] is True
    assert health['request_control'] == client.request_control
    assert health['traffic'] == {'send_pkg_num': 1, 'recv_pkg_num': 2}
    assert health['client_type'] == 'DummyStdApi'


def test_stdquotes_strict_connect_raises_on_failure(monkeypatch):
    _patch_std_config(monkeypatch)

    class FailingStdApi(DummyStdApi):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self._connect_result = False

    monkeypatch.setattr('mootdx.quotes.TdxHq_API', FailingStdApi)

    with pytest.raises(RuntimeError, match='std connect failed'):
        Quotes.factory(market='std', timeout=3, strict_connect=True)


def test_diagnostics_alias_matches_health(monkeypatch):
    _patch_std_config(monkeypatch)

    client = Quotes.factory(market='std', timeout=3)

    assert client.diagnostics() == client.health()
