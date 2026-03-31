# Mootdx Max

通达信数据读取工具库，面向二次开发。

这个仓库的定位不是完整采集系统，而是一个可嵌入、可扩展、可诊断的底层工具库。你可以在它之上自行编写全市场抓取、调度、落库、回补和监控程序。

## 目标

- 提供稳定的通达信在线行情接口
- 提供本地 `vipdoc` / `T0002` 数据读取接口
- 提供财务文件下载与解析能力
- 暴露可控的连接、限速、缓存和诊断能力
- 支持你在外部程序中直接复用底层能力，而不是重复造轮子

## 当前状态

- Python: `3.8+`
- 支持系统: `Windows / macOS / Linux`
- 当前版本: `0.11.7`
- 协议层: 仓库内置 vendored `tdxpy`

本仓库已经不再依赖“外部安装一个单独的 `tdxpy` 包”才能开发底层逻辑。协议、socket、parser、reader 现在都在仓库内可控。

## 分层架构

项目目前分成两层。

### 1. 上层工具接口 `mootdx`

面向使用者，负责工厂、接口封装、缓存、配置和 CLI。

核心模块：

- [mootdx/quotes.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/mootdx/quotes.py)
  在线行情接口，标准市场 / 扩展市场入口
- [mootdx/reader.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/mootdx/reader.py)
  本地离线数据读取
- [mootdx/affair.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/mootdx/affair.py)
  财务文件下载、解析入口
- [mootdx/financial/financial.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/mootdx/financial/financial.py)
  财务文件解析与表结构转换
- [mootdx/server.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/mootdx/server.py)
  服务器测速、冷却与失败惩罚
- [mootdx/cache/file.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/mootdx/cache/file.py)
  文件缓存
- [mootdx/utils/__init__.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/mootdx/utils/__init__.py)
  数据转换、市场判断、输出等通用工具

### 2. 底层协议实现 `tdxpy`

负责 socket 连接、请求执行、响应解析、离线 reader。

核心模块：

- [tdxpy/base_socket_client.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/tdxpy/base_socket_client.py)
  连接、重连、限速、流量统计、严格失败语义
- [tdxpy/hq.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/tdxpy/hq.py)
  标准市场协议 API
- [tdxpy/exhq.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/tdxpy/exhq.py)
  扩展市场协议 API
- [tdxpy/parser/](/Users/zhoufeiyu/Quantsystem/mootdx_max/tdxpy/parser)
  请求与响应 parser
- [tdxpy/reader/](/Users/zhoufeiyu/Quantsystem/mootdx_max/tdxpy/reader)
  本地二进制 reader

## 这版仓库相对原始项目的关键改动

### 1. vendored `tdxpy`

底层协议源码已经纳入仓库，方便直接修改：

- socket 行为
- 重连策略
- 限速策略
- parser
- 离线 reader

### 2. 更明确的失败语义

默认兼容旧行为，但你可以开启严格模式：

- `strict_connect=True`
  初始化连接失败时直接报错
- `strict_io=True`
  请求失败时直接抛异常，而不是静默返回空结果

公共异常见：

- [mootdx/exceptions.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/mootdx/exceptions.py)

包含：

- `MootdxConnectionError`
- `MootdxConnectionTimeoutError`
- `MootdxNotConnectedError`
- `MootdxRequestError`
- `MootdxEmptyResponseError`
- `MootdxValidationException`

### 3. 请求控制参数标准化

在线 client 现在统一支持：

- `request_interval`
- `requests_per_minute`
- `strict_connect`
- `strict_io`
- `server`
- `bestip`
- `timeout`

这些参数会被标准化后透传到底层协议 client。

### 4. `raw` 原始输出模式

对于你自己写采集程序很重要。

默认返回 `DataFrame`，但现在支持：

- `raw=True`
- `as_dataframe=False`

一旦启用 raw 模式，会直接返回底层原始 `list` / `dict` / 原对象，跳过：

- `DataFrame` 构造
- 索引处理
- `volume` 补列
- 复权后处理

### 5. 健康与诊断接口

高层 `Quotes` client 现在有：

- `health()`
- `diagnostics()`
- `traffic()`

用于暴露：

- 当前服务器
- 连接状态
- 最近连接错误
- 请求控制参数
- 流量统计
- 缓存数量与 TTL

### 6. 保守缓存与服务器策略

已内置：

- `stock_count()` / `stocks()` / `stock_all()` 的短 TTL 内存缓存
- `xdxr` 文件缓存
- 空 `DataFrame` 不再落盘缓存
- 服务器测速失败惩罚与冷却期

## 安装

### 1. 普通安装

```bash
pip install -U mootdx
```

### 2. 开发安装

如果你是基于当前仓库开发：

```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
pip install -r requirements.txt
pip install pytest freezegun
```

## 核心接口

### 在线行情 `Quotes`

```python
from mootdx.quotes import Quotes

client = Quotes.factory(
    market='std',
    timeout=3,
    strict_connect=True,
    request_interval=0.1,
    requests_per_minute=60,
)

print(client.health())
```

#### 常用在线接口

标准市场常用方法在 [mootdx/quotes.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/mootdx/quotes.py)：

- `quotes(symbol=...)`
- `bars(symbol=..., frequency=..., start=..., offset=...)`
- `index(symbol=..., frequency=..., start=..., offset=...)`
- `minute(symbol=...)`
- `minutes(symbol=..., date=...)`
- `transaction(symbol=..., start=..., offset=...)`
- `transactions(symbol=..., date=..., start=..., offset=...)`
- `xdxr(symbol=...)`
- `finance(symbol=...)`
- `F10C(symbol=...)`
- `F10(symbol=..., name=...)`
- `stock_count(market=...)`
- `stocks(market=...)`
- `stock_all()`
- `block()`
- `k(symbol=..., begin=..., end=...)`

#### `DataFrame` 输出

```python
bars = client.bars(symbol='600036', offset=10)
print(type(bars))
```

#### `raw` 输出

```python
bars_raw = client.bars(symbol='600036', offset=10, raw=True)
print(type(bars_raw))
```

#### 健康状态

```python
info = client.health()
print(info['connected'])
print(info['request_control'])
print(info['traffic'])
```

#### 清理缓存

```python
client.clear_cache()                 # 清全部
client.clear_cache('stock_count')    # 只清某类缓存
```

### 本地离线读取 `Reader`

```python
from mootdx.reader import Reader

reader = Reader.factory(
    market='std',
    tdxdir='/path/to/tdx',
)

daily = reader.daily(symbol='600036')
minute = reader.minute(symbol='600036')
fzline = reader.fzline(symbol='600036')
```

支持：

- 标准市场 `std`
- 扩展市场 `ext`

### 财务文件接口 `Affair`

```python
from mootdx.affair import Affair

files = Affair.files()
Affair.fetch(downdir='tmp', filename='gpcw19960630.zip')
data = Affair.parse(downdir='tmp', filename='gpcw19960630.zip')
```

## CLI

CLI 入口见 [mootdx/__main__.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/mootdx/__main__.py)。

可用命令：

- `python -m mootdx quotes`
- `python -m mootdx reader`
- `python -m mootdx bestip`
- `python -m mootdx affair`
- `python -m mootdx bundle`

### 查看帮助

```bash
python -m mootdx --help
```

### 在线行情示例

```bash
python -m mootdx quotes -s 600036 -a daily
```

### 本地 reader 示例

```bash
python -m mootdx reader -d /path/to/tdx -s 600036 -a daily
```

### 测速并写入最佳服务器

```bash
python -m mootdx bestip -v
```

## 请求控制建议

如果你会在外部程序里高频调用，建议至少设置：

```python
client = Quotes.factory(
    market='std',
    strict_connect=True,
    request_interval=0.1,
    requests_per_minute=60,
)
```

如果你要把失败和空数据严格区分开，再在底层 client 使用 `strict_io=True`。

推荐思路：

- 外部程序自己做调度
- 这个库只负责底层请求和解析
- 高频路径优先用 `raw=True`
- 周期性读取 `health()` / `traffic()` 做监控

## 连接与失败语义

这是这个仓库目前最重要的增强点之一。

### 默认模式

为了兼容旧项目，默认仍尽量保持旧行为：

- 尽量不打断旧接口调用
- 某些失败场景可能返回空结果

### 严格模式

如果你把这个库作为底层工具库使用，建议启用严格模式：

- `strict_connect=True`
  初始化必须连上
- `strict_io=True`
  请求失败时明确抛异常

这样你的外部程序就能可靠地区分：

- 连接失败
- 请求失败
- 参数错误
- 真正的空数据

## 缓存策略

### 已启用的缓存

- `stock_count()` 短 TTL 内存缓存
- `stocks()` 短 TTL 内存缓存
- `stock_all()` 短 TTL 内存缓存
- `xdxr` 文件缓存

### 当前原则

- 空结果默认不写文件缓存
- 读到空缓存会刷新
- 缓存 TTL 可配置

## 服务器策略

[mootdx/server.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/mootdx/server.py) 现在不只是简单测速。

已包含：

- 服务器测速
- 失败惩罚
- 冷却期跳过
- 结果写回配置

目标是减少对坏节点的重复探测，避免无意义请求。

## 项目适合什么，不适合什么

### 适合

- 作为你自己程序的行情工具库
- 单股 / 多股查询
- 离线 reader
- 财务文件解析
- 作为更大采集系统的底层能力层

### 不适合

- 直接当完整的分布式采集系统
- 直接当任务调度器
- 直接当数据库落库框架

这些应该由你的外部程序来做。

## 测试

推荐的本地测试命令：

```bash
pytest
```

在线接口相关测试：

- [tests/quotes/test_quotes_std.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/tests/quotes/test_quotes_std.py)
- [tests/tools/test_reversion.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/tests/tools/test_reversion.py)

工具库增强相关测试：

- [tests/quotes/test_quotes_ergonomics.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/tests/quotes/test_quotes_ergonomics.py)
- [tests/quotes/test_quotes_perf.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/tests/quotes/test_quotes_perf.py)
- [tests/tdxpy/test_base_socket_client.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/tests/tdxpy/test_base_socket_client.py)
- [tests/tdxpy/test_base_socket_client_state.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/tests/tdxpy/test_base_socket_client_state.py)
- [tests/test_exceptions.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/tests/test_exceptions.py)
- [tests/test_server_strategy.py](/Users/zhoufeiyu/Quantsystem/mootdx_max/tests/test_server_strategy.py)

## 开发建议

如果你要基于这个库继续做自己的程序，建议：

1. 高频路径优先使用 `raw=True`
2. 外部程序默认启用 `strict_connect=True`
3. 对生产链路考虑启用 `strict_io=True`
4. 把 `health()` 作为监控输入
5. 让外部程序自己负责调度、落库和补采

## 许可证

MIT
