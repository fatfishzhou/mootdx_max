from unittest import mock

import pandas as pd

from mootdx.quotes import StdQuotes


def build_client():
    client = StdQuotes.__new__(StdQuotes)
    client.client = mock.Mock()
    client._read_cache = {}
    client.cache_ttls = dict(StdQuotes.DEFAULT_CACHE_TTLS)
    return client


def test_stocks_concat_once():
    client = build_client()
    client.stock_count = mock.Mock(return_value=2500)
    client.client.get_security_list.side_effect = [
        [{'code': '000001'}],
        [{'code': '000002'}],
        [{'code': '000003'}],
    ]

    with mock.patch('mootdx.quotes.pandas.concat', wraps=pd.concat) as concat_mock:
        result = client.stocks(0)

    assert result['code'].tolist() == ['000001', '000002', '000003']
    assert concat_mock.call_count == 1


def test_stock_count_uses_cache_until_refresh():
    client = build_client()
    client.client.get_security_count.return_value = 2500

    first = client.stock_count(0)
    second = client.stock_count(0)
    refreshed = client.stock_count(0, refresh=True)

    assert first == 2500
    assert second == 2500
    assert refreshed == 2500
    assert client.client.get_security_count.call_count == 2


def test_stocks_uses_cache_until_refresh():
    client = build_client()
    client.stock_count = mock.Mock(return_value=2500)
    client.client.get_security_list.side_effect = [
        [{'code': '000001'}],
        [{'code': '000002'}],
        [{'code': '000003'}],
        [{'code': '000101'}],
        [{'code': '000102'}],
        [{'code': '000103'}],
    ]

    first = client.stocks(0)
    second = client.stocks(0)
    refreshed = client.stocks(0, refresh=True)

    assert first['code'].tolist() == ['000001', '000002', '000003']
    assert second['code'].tolist() == ['000001', '000002', '000003']
    assert refreshed['code'].tolist() == ['000101', '000102', '000103']
    assert client.client.get_security_list.call_count == 6


def test_stock_all_skips_empty_frames():
    client = build_client()
    client.stocks = mock.Mock(side_effect=[pd.DataFrame(), pd.DataFrame([{'code': '000001'}])])

    with mock.patch('mootdx.quotes.pandas.concat', wraps=pd.concat) as concat_mock:
        result = client.stock_all()

    assert result['code'].tolist() == ['000001']
    assert concat_mock.call_count == 1


def test_stock_all_uses_cache_until_refresh():
    client = build_client()
    client.stocks = mock.Mock(
        side_effect=[
            pd.DataFrame([{'code': '000001'}]),
            pd.DataFrame([{'code': '000002'}]),
            pd.DataFrame([{'code': '000101'}]),
            pd.DataFrame([{'code': '000102'}]),
        ]
    )

    first = client.stock_all()
    second = client.stock_all()
    refreshed = client.stock_all(refresh=True)

    assert first['code'].tolist() == ['000001', '000002']
    assert second['code'].tolist() == ['000001', '000002']
    assert refreshed['code'].tolist() == ['000101', '000102']
    assert client.stocks.call_count == 4


def test_get_k_data_returns_empty_frame_when_all_chunks_empty():
    client = build_client()
    client.client.get_security_bars.return_value = []
    client.client.to_df.return_value = pd.DataFrame()

    result = client.get_k_data(code='600036', start_date='2024-01-01', end_date='2024-01-10')

    assert result.empty


def test_clear_cache_by_name():
    client = build_client()
    client._read_cache = {
        ('stock_count', 0): (999999.0, 1),
        ('stocks', 0): (999999.0, pd.DataFrame([{'code': '000001'}])),
    }

    client.clear_cache('stock_count')

    assert ('stock_count', 0) not in client._read_cache
    assert ('stocks', 0) in client._read_cache


def test_zero_ttl_disables_stock_count_cache():
    client = build_client()
    client.cache_ttls['stock_count'] = 0
    client.client.get_security_count.return_value = 2500

    first = client.stock_count(0)
    second = client.stock_count(0)

    assert first == second == 2500
    assert client.client.get_security_count.call_count == 2
