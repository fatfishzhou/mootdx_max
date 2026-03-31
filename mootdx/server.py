import asyncio
import functools
import json
import socket
import time
from copy import deepcopy
from functools import partial

from tdxpy.constants import hq_hosts
from tdxpy.exhq import TdxExHq_API
from tdxpy.hq import TdxHq_API

from mootdx.consts import CONFIG
from mootdx.consts import EX_HOSTS
from mootdx.consts import GP_HOSTS
from mootdx.consts import HQ_HOSTS
from mootdx.logger import logger
from mootdx.utils import get_config_path

hosts = {
    'HQ': [{'addr': hs[1], 'port': hs[2], 'time': 0, 'site': hs[0]} for hs in hq_hosts + HQ_HOSTS],
    'EX': [{'addr': hs[1], 'port': hs[2], 'time': 0, 'site': hs[0]} for hs in EX_HOSTS],
    'GP': [{'addr': hs[1], 'port': hs[2], 'time': 0, 'site': hs[0]} for hs in GP_HOSTS],
}

results = {k: [] for k in hosts}

DEFAULT_FAILURE_COOLDOWN = 30.0
MAX_FAILURE_COOLDOWN = 300.0
_probe_state = {k: {} for k in hosts}


def _proxy_key(proxy):
    return proxy.get('addr'), int(proxy.get('port'))


def _probe_snapshot(index, proxy):
    return _probe_state[index].get(_proxy_key(proxy), {'failures': 0, 'cooldown_until': 0.0})


def _probe_success(index, proxy):
    _probe_state[index][_proxy_key(proxy)] = {'failures': 0, 'cooldown_until': 0.0}


def _probe_failure(index, proxy, now=None):
    now = time.monotonic() if now is None else now
    state = _probe_snapshot(index, proxy)
    failures = state['failures'] + 1
    cooldown = min(DEFAULT_FAILURE_COOLDOWN * failures, MAX_FAILURE_COOLDOWN)
    _probe_state[index][_proxy_key(proxy)] = {
        'failures': failures,
        'cooldown_until': now + cooldown,
    }


def _is_in_cooldown(index, proxy, now=None):
    now = time.monotonic() if now is None else now
    return _probe_snapshot(index, proxy)['cooldown_until'] > now


def _available_hosts(index, now=None):
    now = time.monotonic() if now is None else now
    return [deepcopy(proxy) for proxy in hosts[index] if not _is_in_cooldown(index, proxy, now=now)]


def callback(res, key):
    """
    异步回调函数

    :param res:
    :param key:
    """
    result = res.result()

    if result.get('time'):
        results[key].append(result)

    # logger.debug(f"callback: {res.result()}")


def connect(proxy: dict, index='GP') -> dict:
    """
    连接服务器函数

    :param proxy: 代理IP信息
    :return:
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(.7)

        start = time.perf_counter()

        sock.connect((proxy.get('addr'), int(proxy.get('port'))))
        sock.close()

        proxy['time'] = (time.perf_counter() - start) * 1000
        _probe_success(index, proxy)

        logger.debug('{addr}:{port} 验证通过，响应时间：{time} ms.'.format(**proxy))
    except socket.timeout as ex:  # noqa
        logger.debug('{addr},{port} time out.'.format(**proxy))
        proxy['time'] = None
        _probe_failure(index, proxy)
    except ConnectionRefusedError as ex:  # noqa
        logger.debug('{addr},{port} 验证失败.'.format(**proxy))
        proxy['time'] = None
        _probe_failure(index, proxy)
    except Exception:  # noqa
        logger.debug('{addr},{port} 验证失败.'.format(**proxy))
        proxy['time'] = None
        _probe_failure(index, proxy)

    return proxy


def connect2(proxy, index='HQ'):
    if index == 'GP':
        return connect(proxy, index=index)

    api = (TdxHq_API(), TdxExHq_API())[index != 'HQ']
    fun = ('get_security_count', 'get_instrument_count')[index != 'HQ']

    proxy['time'] = None

    try:
        with api.connect(proxy.get('addr'), int(proxy.get('port')), time_out=0.7):
            tms = time.perf_counter()
            if getattr(api, fun)():
                proxy['time'] = (time.perf_counter() - tms) * 1000
                _probe_success(index, proxy)
                logger.debug('{addr}:{port} 验证通过，响应时间：{time} ms.'.format(**proxy))
            else:
                _probe_failure(index, proxy)
                logger.debug('{addr}:{port} 验证失败.'.format(**proxy))
    except socket.timeout:  # noqa
        logger.debug('{addr}:{port} time out.'.format(**proxy))
        proxy['time'] = None
        _probe_failure(index, proxy)
    except Exception:  # noqa
        logger.debug('{addr}:{port} 验证失败.'.format(**proxy))
        _probe_failure(index, proxy)

    return proxy


async def verify(proxy: dict, index):
    """
    检验代理连通性函数

    :param index:
    :param proxy: 代理IP信息
    :return:
    """
    return await asyncio.get_event_loop().run_in_executor(None, functools.partial(connect2, proxy=proxy, index=index))


def server(index=None, limit=5, console=False, sync=True):
    global results

    _hosts = _available_hosts(index)

    if not _hosts:
        logger.warning(f'{index} 当前所有候选服务器都处于冷却期，跳过本轮探测。')
        results[index] = []
        return []

    def async_event():
        event = asyncio.get_event_loop()
        tasks = []

        while len(_hosts) > 0:
            task = event.create_task(verify(_hosts.pop(0), index))
            task.add_done_callback(partial(callback, key=index))
            tasks.append(task)

        # event.is_closed()
        # event.is_running()
        event.run_until_complete(asyncio.wait(tasks))

    if sync:
        results[index] = [connect2(proxy, index=index) for proxy in _hosts]
        results[index] = [x for x in results[index] if x.get('time')]
    else:
        results[index] = []
        async_event()

    servers = results[index]

    # 结果按响应时间从小到大排序
    if console:
        from prettytable import PrettyTable

        servers.sort(key=lambda item: item['time'])

        if limit:
            servers = servers[:limit]

        logger.debug('[√] 最优服务器:')

        t = PrettyTable(['Name', 'Addr', 'Port', 'Time'])
        t.align['Name'] = 'l'
        t.align['Addr'] = 'l'
        t.align['Port'] = 'l'
        t.align['Time'] = 'r'
        t.padding_width = 1

        for host in servers:
            t.add_row(
                [
                    host['site'],
                    host['addr'],
                    host['port'],
                    '{:5.2f} ms'.format(host['time']),
                ]
            )

        logger.debug('\n' + str(t))

    return [(item['addr'], int(item['port'])) for item in servers]


def check_server(console=False, limit=5, sync=False) -> None:
    return bestip(console=console, limit=limit, sync=sync)


def bestip(console=False, limit=5, sync=False) -> None:
    config_ = get_config_path('config.json')
    default = dict(CONFIG)

    logger.info('[-] 选择最快的服务器...')
    logger.debug(f'sync => {sync}')

    for index in ['HQ', 'EX', 'GP']:
        try:
            data = server(index=index, limit=limit, console=console, sync=sync)

            if data:
                default['BESTIP'][index] = data[0]
        except RuntimeError:
            logger.error('请手动运行`python -m mootdx bestip`')
            break

    json.dump(default, open(config_, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)


if __name__ == '__main__':
    bestip(sync=False, limit=5, console=True)
