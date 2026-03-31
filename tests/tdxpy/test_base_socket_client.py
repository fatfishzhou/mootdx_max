from unittest import mock

from tdxpy.base_socket_client import BaseSocketClient


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def test_request_interval_rate_limit():
    clock = FakeClock()
    client = BaseSocketClient(request_interval=0.5)

    with mock.patch('tdxpy.base_socket_client.time.monotonic', side_effect=clock.monotonic):
        with mock.patch('tdxpy.base_socket_client.time.sleep', side_effect=clock.sleep):
            client._apply_rate_limit()
            client._apply_rate_limit()

    assert clock.sleeps == [0.5]


def test_requests_per_minute_rate_limit():
    clock = FakeClock()
    client = BaseSocketClient(requests_per_minute=2)

    with mock.patch('tdxpy.base_socket_client.time.monotonic', side_effect=clock.monotonic):
        with mock.patch('tdxpy.base_socket_client.time.sleep', side_effect=clock.sleep):
            client._apply_rate_limit()
            clock.now = 1.0
            client._apply_rate_limit()
            clock.now = 2.0
            client._apply_rate_limit()

    assert clock.sleeps == [58.0]
