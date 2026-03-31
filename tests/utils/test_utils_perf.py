import pandas as pd

from mootdx.consts import MARKET_SH
from mootdx.consts import MARKET_SZ
from mootdx.utils import get_stock_markets
from mootdx.utils import to_data


def test_get_stock_markets_keeps_mapping():
    assert get_stock_markets(['600036', '000001']) == [
        [MARKET_SH, '600036'],
        [MARKET_SZ, '000001'],
    ]


def test_to_data_empty_dict_returns_empty_frame():
    assert to_data({}).empty


def test_to_data_dataframe_passthrough():
    frame = pd.DataFrame([{'code': '000001'}])
    result = to_data(frame)
    assert result.equals(frame)


def test_to_data_raw_returns_list_unchanged():
    data = [{'aa': 'aa'}]
    result = to_data(data, raw=True)
    assert result is data


def test_to_data_as_dataframe_false_returns_dict_unchanged():
    data = {'abc': 123}
    result = to_data(data, as_dataframe=False)
    assert result is data


def test_to_data_raw_bypasses_adjustment():
    data = [{'code': '000001'}]
    result = to_data(data, raw=True, symbol='000001', adjust='qfq')
    assert result is data
