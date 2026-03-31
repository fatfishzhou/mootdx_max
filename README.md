通达信数据读取接口
==================

[![image](https://badge.fury.io/py/mootdx.svg)](http://badge.fury.io/py/mootdx)
[![image](https://img.shields.io/travis/bopo/mootdx.svg)](https://travis-ci.org/mootdx/mootdx)
[![Documentation Status](https://readthedocs.org/projects/mootdx/badge/?version=latest)](https://mootdx.readthedocs.io/zh/latest/?badge=latest)
[![Updates](https://pyup.io/repos/github/mootdx/mootdx/shield.svg)](https://pyup.io/repos/github/mootdx/mootdx/)

如果喜欢本项目可以在右上角给颗⭐！你的支持是我最大的动力😎！

**郑重声明: 本项目只作学习交流, 不得用于任何商业目的.**

-   开源协议: MIT license
-   在线文档: <https://www.mootdx.com>
-   国内镜像: <https://gitee.com/ibopo/mootdx>
-   项目仓库: <https://github.com/mootdx/mootdx>
-   问题交流: <https://github.com/mootdx/mootdx/issues>

版本更新(倒序)
--------------

版本更新日志: <https://mootdx.readthedocs.io/zh_CN/latest/history/>

运行环境
--------

-   操作系统: Windows / MacOS / Linux 都可以运行.
-   Python: 3.8 以及以上版本.

项目说明
--------

-   当前仓库已经内置 `tdxpy` 协议层源码，不再依赖外部安装的 `tdxpy` 才能开发和调试底层逻辑。
-   在线接口已经补充了更适合二次开发的工具库能力:
    - `strict_connect=True`: 初始化时连不上直接失败
    - `strict_io=True`: 请求失败时显式抛错，而不是静默返回空结果
    - `raw=True` 或 `as_dataframe=False`: 直接返回原始 list/dict 结构，跳过 `DataFrame` 转换
    - `health()` / `diagnostics()`: 返回连接状态、流量统计、请求控制和缓存概况
    - `request_interval` / `requests_per_minute`: 用于保守限速，减少对服务器的冲击
-   低风险只读接口已经带短 TTL 缓存，包括 `stock_count()`、`stocks()`、`stock_all()`；`xdxr` 文件缓存也已修正为空结果不落盘。

安装方法
--------

> 新手建议使用 `pip install -U 'mootdx[all]'` 安装

### PIP 安装方法
```shell

# 包含核心依赖安装
pip install 'mootdx'

# 包含命令行依赖安装, 如果使用命令行工具可以使用这种方式安装
pip install 'mootdx[cli]'

# 包含所有扩展依赖安装, 如果不清楚各种依赖关系就用这个命令
pip install 'mootdx[all]'
```

### 升级安装

```shell
pip install -U mootdx
```

> 如果不清楚各种依赖关系就用这个命令 `pip install -U 'mootdx[all]'`

使用说明
--------

> 以下只列举一些例子, 详细说明请查看在线文档: <https://www.mootdx.com>

通达信离线数据读取

```python
from mootdx.reader import Reader

# market 参数 std 为标准市场(就是股票), ext 为扩展市场(期货，黄金等)
# tdxdir 是通达信的数据目录, 根据自己的情况修改

reader = Reader.factory(market='std', tdxdir='C:/new_tdx')

# 读取日线数据
reader.daily(symbol='600036')

# 读取分钟数据
reader.minute(symbol='600036')

# 读取时间线数据
reader.fzline(symbol='600036')
```

通达信线上行情读取

```python
from mootdx.quotes import Quotes

# 标准市场
client = Quotes.factory(
    market='std',
    heartbeat=True,
    strict_connect=True,     # 初始化连不上时直接失败
    request_interval=0.1,    # 请求最小间隔(秒)
    requests_per_minute=60,  # 每分钟最大请求数
)

# k 线数据
client.bars(symbol='600036', frequency=9, offset=10)

# 指数
client.index(symbol='000001', frequency=9)

# 分钟
client.minute(symbol='000001')

# 原始结果，适合你外部程序自己做落库/处理
client.bars(symbol='600036', offset=10, raw=True)

# 健康状态/诊断信息
client.health()
```

工具库增强示例
--------------

```python
from mootdx.quotes import Quotes

client = Quotes.factory(
    market='std',
    strict_connect=True,
    request_interval=0.2,
    requests_per_minute=120,
)

try:
    # 默认返回 pandas.DataFrame
    bars_df = client.bars(symbol='600036', offset=5)

    # raw 模式直接返回底层 list/dict
    bars_raw = client.bars(symbol='600036', offset=5, raw=True)

    # 查看连接、流量和缓存状态
    print(client.health())
finally:
    client.close()
```

通达信财务数据读取

```python
from mootdx.affair import Affair

# 远程文件列表
files = Affair.files()

# 下载单个
Affair.fetch(downdir='tmp', filename='gpcw19960630.zip')

# 下载全部
Affair.parse(downdir='tmp')
```

加微信交流
----------

![](docs/img/IMG_2851.JPG)

常见问题
--------

M1 mac 系统PyMiniRacer不能使用，访问:
<https://github.com/sqreen/PyMiniRacer/issues/143>


## Stargazers over time

[![Stargazers over time](https://starchart.cc/mootdx/mootdx.svg)](https://starchart.cc/mootdx/mootdx)
