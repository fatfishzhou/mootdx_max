from unittest import mock

import pytest

from tdxpy.base_socket_client import BaseSocketClient
from tdxpy.base_socket_client import MootdxConnectionError
from tdxpy.base_socket_client import MootdxConnectionTimeoutError
from tdxpy.base_socket_client import MootdxEmptyResponseError
from tdxpy.base_socket_client import MootdxNotConnectedError
from tdxpy.base_socket_client import MootdxRequestError
from tdxpy.base_socket_client import last_ack_time
from tdxpy.exceptions import TdxConnectionError
from tdxpy.exceptions import TdxFunctionCallError
from tdxpy.parser.base import ResponseRecvFails
from tdxpy.parser.base import SendRequestPkgFails


class DummySocket:
    def __init__(self, fail=False):
        self.fail = fail
        self.closed = False
        self.connect_calls = []

    def settimeout(self, timeout):
        self.timeout = timeout

    def connect(self, addr):
        self.connect_calls.append(addr)
        if self.fail:
            raise OSError("connect failed")

    def close(self):
        self.closed = True

    def shutdown(self, how):
        self.closed = True


def test_connect_failure_clears_state():
    client = BaseSocketClient()

    with mock.patch('tdxpy.base_socket_client.TrafficStatSocket', return_value=DummySocket(fail=True)):
        assert client.connect('127.0.0.1', 7709) is False

    assert client.closed is True
    assert client.client is None
    assert client.ip == '127.0.0.1'
    assert client.port == 7709
    assert client._endpoint == ('127.0.0.1', 7709)


def test_disconnect_marks_closed_and_keeps_endpoint_when_needed():
    client = BaseSocketClient()
    socket_obj = DummySocket()

    with mock.patch('tdxpy.base_socket_client.TrafficStatSocket', return_value=socket_obj):
        assert client.connect('127.0.0.1', 7709) is client

    client.disconnect()

    assert client.closed is True
    assert client.client is None
    assert client._endpoint == ('127.0.0.1', 7709)


def test_reconnect_uses_remembered_endpoint_only():
    client = BaseSocketClient()

    with mock.patch.object(client, 'connect', return_value=True) as connect_mock:
        assert client.reconnect() is False
        connect_mock.assert_not_called()

    client._endpoint = ('127.0.0.1', 7709)

    with mock.patch.object(client, 'connect', return_value=True) as connect_mock:
        assert client.reconnect() is True
        connect_mock.assert_called_once_with('127.0.0.1', 7709)


def test_connect_failure_keeps_endpoint_for_future_retry():
    client = BaseSocketClient()

    with mock.patch('tdxpy.base_socket_client.TrafficStatSocket', return_value=DummySocket(fail=True)):
        assert client.connect('127.0.0.1', 7709) is False

    assert client._endpoint == ('127.0.0.1', 7709)


def test_get_traffic_stats_when_not_connected():
    client = BaseSocketClient()

    stats = client.get_traffic_stats()

    assert stats['send_pkg_num'] == 0
    assert stats['recv_pkg_num'] == 0
    assert stats['first_pkg_send_time'] is None


def test_strict_connect_timeout_uses_explicit_exception():
    client = BaseSocketClient(strict_io=True)

    with mock.patch('tdxpy.base_socket_client.TrafficStatSocket', return_value=DummySocket(fail=True)):
        with pytest.raises(MootdxConnectionError) as exc:
            client.connect('127.0.0.1', 7709)

    assert isinstance(exc.value, MootdxConnectionTimeoutError | MootdxConnectionError)
    assert isinstance(exc.value, TdxConnectionError)
    assert client.last_error is exc.value


def test_strict_request_failure_wraps_send_errors():
    class DummyClient(BaseSocketClient):
        def __init__(self):
            super().__init__(strict_io=True)
            self.client = object()
            self.closed = False
            self._endpoint = ('127.0.0.1', 7709)

        @last_ack_time
        def boom(self):
            raise SendRequestPkgFails('send fails')

    client = DummyClient()

    with pytest.raises(MootdxRequestError) as exc:
        client.boom()

    assert isinstance(exc.value, TdxFunctionCallError)
    assert client.last_error is exc.value


def test_strict_request_failure_wraps_empty_response():
    class DummyClient(BaseSocketClient):
        def __init__(self):
            super().__init__(strict_io=True)
            self.client = object()
            self.closed = False
            self._endpoint = ('127.0.0.1', 7709)

        @last_ack_time
        def boom(self):
            raise ResponseRecvFails('recv fails')

    client = DummyClient()

    with pytest.raises(MootdxEmptyResponseError) as exc:
        client.boom()

    assert isinstance(exc.value, MootdxRequestError)
    assert client.last_error is exc.value


def test_strict_not_connected_raises_explicit_error():
    class DummyClient(BaseSocketClient):
        def __init__(self):
            super().__init__(strict_io=True)
            self.client = None
            self.closed = True
            self._endpoint = None

        @last_ack_time
        def ping(self):
            return True

    client = DummyClient()

    with pytest.raises(MootdxNotConnectedError):
        client.ping()
