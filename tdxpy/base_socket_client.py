# cython: language_level=3
import datetime
import functools
import socket
import threading
import time
from collections import deque

import pandas as pd

from tdxpy.exceptions import TdxConnectionError
from tdxpy.exceptions import TdxFunctionCallError
from tdxpy.exceptions import ValidationException
from tdxpy.heartbeat import HeartBeatThread
from tdxpy.logger import logger
from tdxpy.parser.raw_parser import RawParser
from tdxpy.parser.base import ResponseHeaderRecvFails
from tdxpy.parser.base import ResponseRecvFails
from tdxpy.parser.base import SendRequestPkgFails
from tdxpy.parser.base import SocketClientNotReady

DEFAULT_HEARTBEAT_INTERVAL = 10.0

CONNECT_TIMEOUT = 5.000
RECV_HEADER_LEN = 0x10


class MootdxConnectionError(TdxConnectionError):
    def __init__(self, message=None, *, endpoint=None, original_exception=None):
        super().__init__(message or 'connection failed')
        self.endpoint = endpoint
        self.original_exception = original_exception


class MootdxConnectionTimeoutError(MootdxConnectionError):
    pass


class MootdxNotConnectedError(MootdxConnectionError):
    pass


class MootdxRequestError(TdxFunctionCallError):
    def __init__(self, message=None, *, endpoint=None, response=None, original_exception=None):
        super().__init__(message or 'request failed')
        self.endpoint = endpoint
        self.response = response
        self.original_exception = original_exception


class MootdxEmptyResponseError(MootdxRequestError):
    pass


def last_ack_time(func):
    """
    装饰器: 更新最后 ack 时间
    :param func:
    :return:
    """

    @functools.wraps(func)
    def wrapper(self, *args, **kw):
        self.last_ack_time = time.time()

        logger.debug(f"last ack time update to {self.last_ack_time}")

        if self.strict_io and (self.client is None or self.closed) and not self._endpoint:
            error = MootdxNotConnectedError('socket client not connected', endpoint=self._endpoint)
            self.last_error = error
            raise error

        if (self.client is None or self.closed) and self._endpoint:
            logger.debug(f"preflight reconnect to {self._endpoint}")
            self.reconnect()

        ret = None

        try:
            ret = func(self, *args, **kw)
        except (TypeError, ValueError) as e:
            raise ValidationException(*e.args)
        except Exception as e:
            # logger.exception(e)
            current_exception = e
            logger.debug(f"hit exception on req exception is {e}")
            self.last_error = e

            if self.auto_retry and self.client:
                for time_interval in self.retry_strategy.generate():
                    try:
                        time.sleep(time_interval)

                        self.disconnect()
                        if not self.reconnect():
                            current_exception = MootdxConnectionError(
                                'reconnect endpoint missing',
                                endpoint=self._endpoint,
                                original_exception=e,
                            )
                            break

                        ret = func(self, *args, **kw)
                        return ret

                    except Exception as retry_e:
                        logger.debug(f"hit exception on *retry* req exception is {retry_e}")
                        current_exception = retry_e

                logger.debug("perform auto retry on req ")

            # 最后交易失败
            # self last_transaction_failed is True

            # 如果 raise_exception=True 抛出异常
            if self.strict_io or self.raise_exception:
                to_raise = self._wrap_request_exception(current_exception)
                raise to_raise

        return ret

    return wrapper


class RetryStrategy:
    @classmethod
    def generate(cls):
        raise NotImplementedError("need to override")


class DefaultRetryStrategy(RetryStrategy):
    """
    默认的重试策略，您可以通过写自己的重试策略替代本策略, 改策略主要实现 generate 方法，该方法是一个生成器，
    返回下次重试的间隔时间, 单位为秒，我们会使用 time.sleep在这里同步等待之后进行重新connect,然后再重新发起
    源请求，直到 generate 结束。
    """

    @classmethod
    def generate(cls):
        yield from [0.1, 0.5, 1, 2]


class TrafficStatSocket(socket.socket):
    """
    实现支持流量统计的socket类
    """

    def __init__(self, sock, mode):
        super().__init__(sock, mode)

        # 流量统计相关
        self.send_pkg_num = 0  # 发送次数
        self.recv_pkg_num = 0  # 接收次数
        self.send_pkg_bytes = 0  # 发送字节
        self.recv_pkg_bytes = 0  # 接收字节数
        self.first_pkg_send_time = None  # 第一个数据包发送时间

        self.last_api_send_bytes = 0  # 最近的一次api调用的发送字节数
        self.last_api_recv_bytes = 0  # 最近一次api调用的接收字节数


class BaseSocketClient:
    def __init__(
        self,
        multithread=False,
        heartbeat=False,
        auto_retry=False,
        raise_exception=False,
        strict_io=False,
        request_interval=0.0,
        requests_per_minute=None,
    ):
        """
        构造函数
        :param multithread: 是否多线程
        :param heartbeat: 是否心跳
        :param auto_retry: 是否自动回复
        :param raise_exception: 是否抛出异常
        """

        self.need_setup = True
        self.closed = True
        self.client = None

        self.lock = (multithread or heartbeat) and threading.Lock() or None

        self.heartbeat = heartbeat
        self.heartbeat_thread = None

        self.stop_event = None
        self.heartbeat_interval = DEFAULT_HEARTBEAT_INTERVAL  # 默认10秒一个心跳包

        self.last_ack_time = time.time()
        # self last_transaction_failed = False

        self.ip, self.port = None, None
        self._endpoint = None

        # 是否重试
        self.auto_retry = auto_retry

        # 可以覆盖这个属性，使用新的重试策略
        self.retry_strategy = DefaultRetryStrategy()

        # 是否在函数调用出错的时候抛出异常
        self.raise_exception = raise_exception
        self.strict_io = strict_io
        self.last_error = None

        # 保守型节流，优先降低短时间请求密度
        self.request_interval = max(float(request_interval or 0.0), 0.0)
        self.requests_per_minute = None if requests_per_minute is None else max(int(requests_per_minute), 0)
        self._request_state_lock = threading.Lock()
        self._next_request_at = 0.0
        self._request_timestamps = deque()

    def _apply_rate_limit(self):
        if self.request_interval <= 0 and not self.requests_per_minute:
            return

        with self._request_state_lock:
            now = time.monotonic()

            if self.request_interval > 0 and self._next_request_at > now:
                delay = self._next_request_at - now
                logger.debug(f"rate limit sleep {delay:.4f}s for request interval")
                time.sleep(delay)
                now = time.monotonic()

            if self.requests_per_minute:
                window_start = now - 60

                while self._request_timestamps and self._request_timestamps[0] <= window_start:
                    self._request_timestamps.popleft()

                if len(self._request_timestamps) >= self.requests_per_minute:
                    delay = self._request_timestamps[0] + 60 - now
                    if delay > 0:
                        logger.debug(f"rate limit sleep {delay:.4f}s for requests_per_minute")
                        time.sleep(delay)
                        now = time.monotonic()

                        window_start = now - 60
                        while self._request_timestamps and self._request_timestamps[0] <= window_start:
                            self._request_timestamps.popleft()

            if self.request_interval > 0:
                self._next_request_at = now + self.request_interval

            if self.requests_per_minute:
                self._request_timestamps.append(now)

    def connect(self, ip: str = None, port: int = 7709, time_out=CONNECT_TIMEOUT, bind_port=None, bind_ip="0.0.0.0"):
        """
        连接服务器

        :param ip:  服务器ip 地址
        :param port:  服务器端口
        :param time_out: 连接超时时间
        :param bind_port: 绑定的本地端口
        :param bind_ip: 绑定的本地ip
        :return: 是否连接成功 True/False
        """

        if not ip:
            raise ValidationException("IP Address bad.")

        self.last_error = None

        try:
            self.ip, self.port = ip, port
            self._endpoint = (ip, port)

            self.client = TrafficStatSocket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.settimeout(time_out)

            logger.debug(f"connecting to server: {ip} on port: {port}")

            bind_port and self.client.bind((bind_ip, bind_port))

            self.client.connect((ip, port))
        except socket.timeout:
            logger.debug("connection expired")
            self._reset_connection_state(clear_endpoint=False)
            error = MootdxConnectionTimeoutError(
                'connection timeout error',
                endpoint=(ip, port),
                original_exception=None,
            )
            self.last_error = error

            if self.strict_io or self.raise_exception:
                raise error

            return False
        except Exception as e:  # noqa
            logger.debug(f"connection {e}")
            self._reset_connection_state(clear_endpoint=False)
            error = MootdxConnectionError(
                'other errors',
                endpoint=(ip, port),
                original_exception=e,
            )
            self.last_error = error
            if self.strict_io or self.raise_exception:
                raise error

            return False

        self.ip, self.port = ip, port
        self._endpoint = (ip, port)
        self.closed = False
        logger.debug("connected!")

        if self.need_setup:
            self.setup()

        # 启动心跳包
        if self.heartbeat:
            self.stop_event = threading.Event()
            self.heartbeat_thread = HeartBeatThread(
                client=self, stop_event=self.stop_event, interval=self.heartbeat_interval
            )
            self.heartbeat_thread.start()

        return self

    def _reset_connection_state(self, clear_endpoint=True):
        if self.client:
            try:
                self.client.close()
            except Exception:  # noqa
                pass

        self.client = None
        self.closed = True

        if clear_endpoint:
            self.ip, self.port = None, None
            self._endpoint = None

    def reconnect(self):
        """
        使用上一次成功连接的端点重连。
        """

        if not self._endpoint:
            logger.debug("reconnect skipped: no remembered endpoint")
            return False

        return self.connect(*self._endpoint)

    def disconnect(self):
        """
        断开连接
        """

        # 停止心跳事件
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.stop_event.set()

        if self.client:
            logger.debug("disconnecting")

            try:
                self.client.shutdown(socket.SHUT_RDWR)
                self.client.close()
                self.client = None
            except Exception as e:
                logger.debug(f"disconnect err: {e}")
                if self.raise_exception:
                    raise TdxConnectionError(f"disconnect err: {e}")
            finally:
                self.client = None

            logger.debug("disconnected")

        self.closed = True

    def close(self):
        """
        disconnect的别名，为了支持 with closing(obj): 语法
        :return:
        """
        self.disconnect()

    def get_traffic_stats(self):
        """
        获取流量统计的信息
        :return:
        """
        if self.client is None:
            return {
                "send_pkg_num": 0,
                "recv_pkg_num": 0,
                "send_pkg_bytes": 0,
                "recv_pkg_bytes": 0,
                "first_pkg_send_time": None,
                "total_seconds": None,
                "send_bytes_per_second": None,
                "recv_bytes_per_second": None,
                "last_api_send_bytes": 0,
            "last_api_recv_bytes": 0,
        }

        if self.client.first_pkg_send_time is not None:
            total_seconds = (datetime.datetime.now() - self.client.first_pkg_send_time).total_seconds()

            if total_seconds != 0:
                send_bytes_per_second = self.client.send_pkg_bytes // total_seconds
                recv_bytes_per_second = self.client.recv_pkg_bytes // total_seconds
            else:
                send_bytes_per_second = None
                recv_bytes_per_second = None
        else:
            total_seconds = None
            send_bytes_per_second = None
            recv_bytes_per_second = None

        return {
            "send_pkg_num": self.client.send_pkg_num,
            "recv_pkg_num": self.client.recv_pkg_num,
            "send_pkg_bytes": self.client.send_pkg_bytes,
            "recv_pkg_bytes": self.client.recv_pkg_bytes,
            "first_pkg_send_time": self.client.first_pkg_send_time,
            "total_seconds": total_seconds,
            "send_bytes_per_second": send_bytes_per_second,
            "recv_bytes_per_second": recv_bytes_per_second,
            "last_api_send_bytes": self.client.last_api_send_bytes,
            "last_api_recv_bytes": self.client.last_api_recv_bytes,
        }

    def send_raw_pkg(self, pkg):
        """
        发送原始数据包
        # for debuging and testing protocol

        :param pkg:
        :return:
        """
        cmd = RawParser(self.client, lock=self.lock)
        cmd.setParams(pkg)

        return cmd.call_api()

    def _wrap_request_exception(self, current_exception):
        if isinstance(current_exception, (ResponseHeaderRecvFails, ResponseRecvFails)):
            error = MootdxEmptyResponseError(
                'empty response from server',
                endpoint=self._endpoint,
                original_exception=current_exception,
            )
        elif isinstance(current_exception, SendRequestPkgFails):
            error = MootdxRequestError(
                'send request failed',
                endpoint=self._endpoint,
                original_exception=current_exception,
            )
        elif isinstance(current_exception, SocketClientNotReady):
            error = MootdxNotConnectedError(
                'socket client not ready',
                endpoint=self._endpoint,
                original_exception=current_exception,
            )
        elif isinstance(current_exception, TdxConnectionError):
            error = MootdxConnectionError(
                str(current_exception) or 'connection failed',
                endpoint=self._endpoint,
                original_exception=current_exception,
            )
        elif isinstance(current_exception, TdxFunctionCallError):
            error = MootdxRequestError(
                str(current_exception) or 'request failed',
                endpoint=self._endpoint,
                original_exception=current_exception,
            )
        else:
            error = MootdxRequestError(
                'request failed',
                endpoint=self._endpoint,
                original_exception=current_exception,
            )

        self.last_error = error
        return error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @staticmethod
    def to_df(v):
        """
        数据转换 df 格式
        :param v:
        :return:
        """

        v = v or ""

        if not v:
            return pd.DataFrame(data=None)

        if isinstance(v, list):
            return pd.DataFrame(data=v)

        if isinstance(v, dict):
            return pd.DataFrame(data=[v])

        return pd.DataFrame(data=[{"value": v}])

    def setup(self):
        """
        方法
        """
        pass
