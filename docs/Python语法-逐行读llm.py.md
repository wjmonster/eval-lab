# Python 语法补课：逐行读 llm.py

> 给"不会 Python 但懂测试"的人。左边代码，右边人话。
> 前提：你知道"函数""变量""循环""异常"是什么（任何语言都有），只是不认识 Python 的写法。

---

## 第 0 部分：先认 8 个新零件（不认识这 8 个，下面全是天书）

| # | 语法 | 出现在 | 一句话 |
|---|---|---|---|
| 1 | `@dataclass` | 56 行 | 自动生成"构造函数"，不用手写 `__init__` |
| 2 | `field(default_factory=...)` | 73–75 行 | "每次新建对象时才现算一个默认值" |
| 3 | `@retry(...)` 装饰器 | 169 行 | 给函数套一层"出错自动重试"的外壳 |
| 4 | 闭包 + `nonlocal` | 153/163/176 行 | 内层函数改外层函数的变量，要显式声明 |
| 5 | `*` 单独一个星号 | 100 行 | 它后面的参数**必须写名字传**，不能按位置传 |
| 6 | `getattr / hasattr` | 44/47 行 | "取属性，没有就给我 None，别报错" |
| 7 | `*` 展开（元组里） | 219 行 | 把一个序列"铺开"塞进元组 |
| 8 | `re.compile(r"...")` | 214 行 | 正则表达式，用来扒代码围栏 |

### 零件 1+2：dataclass 和 field

```python
@dataclass
class CallRecord:
    case_id: str
    provider: str
    ...
    error: str = ""
    ts: float = field(default_factory=time.time)
```

- `@dataclass` 是**装饰器**：加在 `class` 头上，Python 会自动帮你生成构造函数。于是你能直接写 `CallRecord(case_id="x", provider="zhipu", ...)` 而不用自己写一堆 `self.xxx = xxx`。
- 每个 `名字: 类型` 就是**一个字段**。这次类型标注不是摆设——`dataclass` **真的会按顺序把它们变成参数**。
- `= ""` 是默认值。**有默认值的字段必须写在没默认值的后面**（72–75 行都在最后，就是这个原因），否则 Python 报 `non-default argument follows default argument`。
- `field(default_factory=time.time)`：**不能写 `= time.time()`**。因为写 `= time.time()` 是在"定义类的时候算一次"，所有记录会拿到同一个时间戳。`default_factory` 是"每 new 一个对象才调一次"。
- 同理 `default_factory=list`：**不能写 `= []`**，那个空列表会被所有实例共享（Python 最经典的坑）。
- `lambda: uuid.uuid4().hex[:8]`：一个没名字的小函数，调用它才生成随机 8 位编号。

### 零件 3：装饰器 `@retry(...)`

```python
@retry(retry=..., stop=_stop, wait=_wait, reraise=True)
def _do() -> Any:
    ...
```

念法：**"把下面这个 `_do` 函数包起来，以后每次调用 `_do()`，其实走的是 tenacity 这层壳"**。

壳的逻辑是：
1. 调 `_do()`
2. 如果抛出的异常属于 `RETRYABLE` → 调 `_wait` 问"等多久"，等完再调一次
3. 每次重试前调 `_stop` 问"还继续吗"，返回 True 就停
4. 停了还有异常 → `reraise=True` 表示**把最后的异常抛出去**（不设的话它会返回 None，你就丢掉了错误原因）

所以第 186 行那句 `resp = _do()`，**看起来只调了一次，实际可能调了 4 次**。

### 零件 4：闭包和 `nonlocal`

```python
attempts = 0                      # 150 行，在 call_llm 里面
def _do():                        # 175 行，在 call_llm 里面又定义一个函数
    nonlocal attempts             # 176 行
    attempts += 1
```

- 函数里可以再定义函数，内层能**看见**外层的 `attempts`（这叫闭包）
- 但"看见"不等于"能改"。不加 `nonlocal`，`attempts += 1` 会在内层新建一个同名局部变量，外层的还是 0 —— **这是最阴的 bug，不报错，只是数字永远是 0**
- `nonlocal attempts` 就是声明"我要改的是外层那个"

### 零件 5：`*` 分隔符（100 行）

```python
def call_llm(provider, prompt, *, case_id="", temperature=0.0, ...):
```

星号**后面**的参数叫"仅限关键字参数"：调用时必须写 `case_id=...`，不能靠位置。目的很实在——后面还有 8 个参数，靠位置传一定传错。

### 零件 6：`getattr` / `hasattr`

```python
resp = getattr(exc, "response", None)                      # 44 行
raw = resp.headers.get("retry-after") if hasattr(resp, "headers") else None   # 47 行
```

- `getattr(对象, "属性名", 默认值)` = "有就取，没有就给我默认值，**不要报错**"
- `hasattr` = "有没有这个属性"
- 为什么必须这么写：不是所有异常都带 `response`（纯网络错误就没有）。硬写 `exc.response` 会 `AttributeError`，把重试逻辑搞崩。

### 零件 7：元组里的 `*` 展开（219 行）

```python
for candidate in (text, *(m.group(1) for m in _FENCE.finditer(text))):
```

`(text, *一串东西)` = 第一个元素是 text，后面把那一串**摊平**接上去。等价于"先试原文，再试每个代码围栏里的内容"。

### 零件 8：正则

```python
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
```

- `r"..."` 是"原始字符串"，反斜杠不当转义
- `(?:json)?` = 可有可无的 `json`
- `(.*?)` = 要抓的内容（非贪婪，抓到第一个 ``` 就停）
- `re.S` = 让 `.` 也能匹配换行
- `m.group(1)` = 取括号里抓到的部分

---

## 第 1 部分：逐行讲

### 1–7 行：文档字符串（docstring）

三引号包起来的一段字，是**这个文件的说明**，`help(eval_lab.llm)` 能看到。它不影响运行，但第 3–6 行那三条设计原则是给面试讲的话术，别删。

### 8 行：`from __future__ import annotations`

上一轮讲过：让类型标注只存字符串，不解析。本项目 3.12 用不上，删了也跑。

### 10–16 行：导入标准库

- `json`：字典 ↔ 文本互转（落库用）
- `os`：读环境变量
- `re`：正则
- `time`：`time.time()` 取当前秒数、`time.sleep()` 睡觉
- `uuid`：生成随机 ID
- `from dataclasses import dataclass, asdict, field`：见零件 1、2，还有 `asdict`（把对象变成字典）
- `from typing import Any`：`Any` 就是"什么类型都行"的占位

### 18–27 行：导入第三方包

- `httpx`：HTTP 库，这里只用它的**异常类**（超时、传输错误）
- `openai`：OpenAI 官方 SDK，也只用异常类
- `from dotenv import load_dotenv`：读 `.env` 文件
- `from openai import OpenAI`：真正发请求的客户端
- `from tenacity import ...`：重试库，四个零件：
  - `retry`：装饰器本体
  - `retry_if_exception_type(RETRYABLE)`：只在异常是这几种时才重试
  - `stop_after_attempt`：按次数停 —— **注意：这个导进来了但全文没用（25 行是个死 import）**
  - `wait_exponential_jitter`：指数退避加随机抖动

### 29 行：从自己项目里取

`from .config import ...` —— 前面那个 `.` 表示"同一个包里的兄弟文件"。

### 31 行：`load_dotenv()`

读 `.env`，把里面的 `KEY=值` 塞进环境变量。**必须在使用 `os.getenv` 之前执行**，所以放在文件顶层第 31 行。

### 33–39 行：`RETRYABLE` 可重试清单

```python
RETRYABLE = (
    httpx.TimeoutException,       # 请求超时
    httpx.TransportError,         # 连接层错误（断网、DNS、TLS）
    openai.APIConnectionError,    # SDK 层连接问题
    openai.RateLimitError,        # 429 限流
    openai.InternalServerError,   # 5xx 服务端错
)
```

括号里用逗号分隔 = **元组**（不可变列表）。`retry_if_exception_type(RETRYABLE)` 拿它当"哪种错值得再试"的白名单。

**故意不包含 400 / 401**：那是"你参数写错了""你 key 错了"，重试 4 次还是同一个错，纯浪费。

### 42 行：函数定义

```python
def retry_after_seconds(exc: BaseException) -> float | None:
```

收一个异常对象，返回"浮点数或空"。`float | None` 就是"要么给秒数，要么给 None（表示服务端没说）"。

### 44–46 行：先看有没有 response

```python
resp = getattr(exc, "response", None)
if resp is None:
    return None
```

没 response 就老实返回 None，后面不用猜。

### 47–49 行：再取 header

```python
raw = resp.headers.get("retry-after") if hasattr(resp, "headers") else None
if not raw:
    return None
```

- `.get("retry-after")`：字典式取值，**没有这个 key 返回 None 而不报错**（比 `[]` 安全）
- `if not raw:`：空字符串、None 都算"假"，所以是"没拿到就返回 None"

### 50–53 行：转换 + 兜底

```python
try:
    return max(0.0, float(raw))
except (TypeError, ValueError):
    return None
```

- `float("2")` → `2.0`；但 `float("Wed, 21 Oct 2025...")`（有些服务给日期格式）会抛 `ValueError`
- `max(0.0, x)`：防止服务端给负数
- `except (TypeError, ValueError)`：一次接两种异常，括号里用逗号

### 56 行：`@dataclass`

见零件 1。一行顶掉十几行构造函数。

### 57–71 行：14 个必填字段

`case_id` 到 `finish_reason`，每个都是 `名字: 类型`，没有默认值。

**这 14 个的共同点：缺一个后面就算不出结论**（详见 `docs\核心代码解析.md` 第四节那张表）。

### 72–75 行：4 个有默认值的字段

```python
error: str = ""                                         # 默认空 = 没出错
ts: float = field(default_factory=time.time)            # 默认 = 现在
run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])  # 默认 = 随机 8 位
retry_waits_s: list[float] = field(default_factory=list) # 默认 = 空列表
```

四个都用了 `field(default_factory=...)`（除 `error`，因为字符串不可变，直接写 `""` 安全）。
`field(...)` 的规矩：**可变默认值（list/dict）和"要现算的值"（时间/随机数）必须用它**。

### 77–78 行：转成 JSON 文本

```python
def to_json(self) -> str:
    return json.dumps(asdict(self), ensure_ascii=False)
```

- `self` = "这个对象自己"（Java 的 `this`）
- `asdict(self)` = 把对象变成普通字典 `{"case_id": "...", ...}`
- `json.dumps(字典, ensure_ascii=False)` = 字典转 JSON 字符串；`ensure_ascii=False` 让中文原样输出，不变成 `\u4e2d\u6587`

**为什么要 `ensure_ascii=False`**：打开 jsonl 你能直接读中文，否则满屏转义码，出问题根本没法眼看。

### 81–83 行：追加写一行

```python
def _log(rec: CallRecord) -> None:
    with CALLS_LOG.open("a", encoding="utf-8") as f:
        f.write(rec.to_json() + "\n")
```

- `with ... as f:` = 打开文件、用完**自动关闭**（等价于 try/finally）
- `"a"` = append 模式，**永远追加，不覆盖**
- `encoding="utf-8"` = 中文必须指定，Windows 默认编码会出乱码
- `+ "\n"` = 每行末尾补换行，这样才是"一行一条"

**一行一条 jsonl 的好处**：追加不用读全文件、坏了只坏一行、能 `tail -1` 看最新一条。

### 86 行：mock 函数

```python
def _mock_call(prompt: str, delay: float = 0.0) -> tuple[str, int, int, str]:
```

返回四样东西：输出文本、输入 token、输出 token、结束原因。**返回四个值时 Python 用一个元组打包**。

### 88–89 行：要先睡

```python
if delay:
    time.sleep(delay)
```

`if delay:` = "delay 不为 0 就睡"（0 是假）。

### 90–93 行：写死的假输出

```python
out = (
    "这是 mock 回复。示例结构化输出：\n"
    '```json\n{"score": 1, "violations": [], "evidence": "示例依据"}\n```'
)
```

相邻两个字符串并排写，Python 会自动拼起来（不用 `+`）。第二行用单引号包，是为了里面能放双引号。

**这段故意写成"带 ````json` 围栏"的样子** —— 就是为了让 `parse_json_lenient` 有事可干。

### 94 行：一次返回四样

```python
return out, len(prompt) // 2, len(out) // 2, "stop"
```

- `//` 是**整除**（向下取整），`len(prompt) // 2` 是"拿字符数一半假装是 token 数"
- `"stop"` 是假的 `finish_reason`，跟真实 API 的取值对齐

### 97–110 行：`call_llm` 签名

```python
def call_llm(
    provider: str,
    prompt: str,
    *,
    case_id: str = "",
    ...
    mock_delay: float = 0.0,
) -> CallRecord:
```

- 前两个参数能按位置传：`call_llm("zhipu", "题目")`
- `*` 后面 9 个**必须写名字**
- `-> CallRecord` 表示返回一条调用记录
- `model_override` 和 `mock_delay` 是给测试用的后门（D3 就是靠 `model_override` 把 model 名换成 `fault-429`）

### 111–112 行：先验厂商名

```python
if provider not in PROVIDERS:
    raise ValueError(f"未知 provider: {provider}，可选 {list(PROVIDERS)}")
```

- `in` = "在不在这个字典的键里"
- `list(PROVIDERS)` = 把字典的键变成列表，好在报错信息里列出来
- `raise ValueError(...)` = **主动抛异常**，让调用方知道参数本身就不对（不是网络问题）

注意：这里抛的是 `ValueError`，而缺 key 抛的是 `RuntimeError`（146 行）。为什么分开：`cli.py:45` 只接 `RuntimeError` 来"跳过这家"，`ValueError` 会一路抛到顶 —— 因为"厂商名拼错"是程序 bug，不该被静默跳过。

### 114–116 行：取配置

```python
cfg = PROVIDERS[provider]                          # 拿到那家的三个字段
model = model_override or cfg["model"]             # 有覆盖就用覆盖，否则用配置
case_id = case_id or f"adhoc-{uuid.uuid4().hex[:6]}"
```

关键在 `or` 的用法：**空字符串也算假**，所以 `case_id=""` 时会自动生成一个 `adhoc-xxxxxx`。这样你随手跑一条也永远有 ID，不会出现"case_id 是空"的脏记录。

### 118 行：mock 走单独分支

```python
if provider == "mock":
```

mock 不发 HTTP，所以要另一套逻辑。**从 118 到 142 行整段是 mock 专用**，143 行之后才是真调用。

### 119 行：记开始时间

```python
t0 = time.time()
```

一个浮点秒数。后面所有 `latency_ms` 都是 `time.time() - t0` 算出来的。

### 121 行：一次拆四个（解包）

```python
out, tin, tout, finish = _mock_call(prompt, delay=mock_delay)
```

`_mock_call` 返回一个 4 元组，左边 4 个变量**按顺序对上**。数量不匹配会报 `ValueError`。

### 122–123 行：假超时

```python
if mock_delay > timeout_s:
    raise httpx.ReadTimeout("mock 超时")
```

**注意顺序**：`_mock_call` 里已经先 `sleep(delay)` 睡满了，这里才抛超时。所以 mock 的"超时"是**真的耗掉了那么多时间**，`latency_ms` 会是真实秒数，不是 0。这是有意的——否则测不出"超时记录里的 latency 是多少"。

### 124–131 行：成功记录

```python
rec = CallRecord(
    case_id=case_id, provider=provider, model=model,
    ...
    latency_ms=int((time.time() - t0) * 1000),
    cost_cny=0.0, attempts=1, finish_reason=finish,
)
```

- `int((time.time() - t0) * 1000)` = 秒差 × 1000 变整数毫秒
- `cost_cny=0.0`：mock 不花钱，写死 0
- `attempts=1`：mock 不重试，写死 1

### 132–140 行：mock 的失败记录

```python
except httpx.TimeoutException as e:
    rec = CallRecord(..., error=type(e).__name__, ...)
```

- `type(e).__name__` = 异常类名，这里就是 `"ReadTimeout"`。**只记类名不记消息**，因为 mock 的消息是写死的没信息量
- 注意 `attempts=1`、`output=""`、token 都是 0

### 141–142 行：两条路汇到一处

```python
_log(rec)
return rec
```

**这句在 try/except 块外面**，所以不管是 124 行那条还是 133 行那条，都会走到这里落库再返回。**这就是"成功失败都必须落库"的实现方式**——不是写两遍 `_log`，而是让两条路汇合。

### 144–146 行：真调用前先验 key

```python
api_key = os.getenv(cfg["key_env"], "")
if not api_key:
    raise RuntimeError(f"{provider} 缺少环境变量 {cfg['key_env']}...")
```

- `os.getenv(名字, 默认)` = 读环境变量，没有就返回 `""`
- `raise RuntimeError` 就是 `cli.py:45` 接住的那个 —— **"跳过这家"的约定靠这句话成立**

### 148 行：建客户端（全项目最重要的一行）

```python
client = OpenAI(base_url=cfg["base_url"], api_key=api_key, timeout=timeout_s, max_retries=0)
```

- `base_url`：每家不一样，所以走配置表
- `timeout=timeout_s`：单次请求超时
- **`max_retries=0`**：把 SDK 自带的 2 次重试关掉。不关的话你 4 次退避实际打出去 12 次请求，而 `attempts` 只记 4 —— **数字直接失真**

### 149–151 行：三个"账本"变量

```python
t0 = time.time()      # 起点，用于算总耗时和预算判断
attempts = 0          # 打了几次（含失败）
waits: list[float] = []  # 每次等了多久
```

这三个都在 `call_llm` 里，被下面的内层函数读写 —— 所以需要闭包和 `nonlocal`。

### 153–161 行：`_wait` 等多久

```python
def _wait(retry_state) -> float:
    base = wait_exponential_jitter(initial=1, max=20)(retry_state)
```

- `retry_state` 是 tenacity 传进来的"当前重试状态"，里面有"第几次""上次的异常"
- `wait_exponential_jitter(initial=1, max=20)` 是一个**函数工厂**：调它返回一个新函数，再 `(retry_state)` 去执行。这就是为什么有两层括号
- 效果：1 秒、2 秒、4 秒、8 秒……最多 20 秒，每档再随机抖一点

```python
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    ra = retry_after_seconds(exc) if exc else None
    if ra is not None:
        base = max(base, ra)
    waits.append(round(base, 2))
    return base
```

- `outcome` 是"上次调用的结果"，`.exception()` 取出异常
- `ra` 是服务端要求的秒数（可能就是 None）
- `max(base, ra)`：**取两者较大值**。服务端说等 2 秒，你只等 1 秒冲上去必然还是 429
- `waits.append(...)`：**把每次等了多少记下来**。不记的话"退避够不够"只能靠感觉
- `round(x, 2)`：保留两位小数

### 163–167 行：`_stop` 何时放弃

```python
def _stop(retry_state) -> bool:
    if retry_state.attempt_number >= max_attempts:
        return True
    return (time.time() - t0) > budget_s
```

两个出口：
1. 次数到了（第 4 次就停）
2. **从开始到现在超了预算**

第二个出口的必要性：如果只有次数出口，一条卡死的请求能拖很久（D3 实测 1 秒超时 × 4 次 = 11.42 秒）。

**已知缺陷**：预算是在"下一次尝试起跑前"判断的。第 3 次起跑时才 4 秒（没超 5 秒），跑完加上等待才超 —— 所以 5 秒预算实测跑了 6.97 秒。**要按预算的 1.4 倍预留**。

### 169–174 行：装饰器

```python
@retry(
    retry=retry_if_exception_type(RETRYABLE),
    stop=_stop,
    wait=_wait,
    reraise=True,
)
```

四个参数：什么错才重试、什么时候停、等多久、停了要不要抛异常。

**`reraise=True` 很关键**：不设的话重试耗尽后 tenacity 会把异常吞掉，`_do()` 返回 None，你在 186 行拿到的 `resp` 就是 None，后面 `.choices` 直接崩 —— 而且崩在一个莫名其妙的地方。

### 175–177 行：`_do` 计数

```python
def _do() -> Any:
    nonlocal attempts
    attempts += 1
```

`attempts += 1` 在**发请求之前**。所以即使第一次就失败，`attempts` 也是 1 而不是 0 —— "尝试过 1 次"和"没尝试"在统计上必须分开。

### 178–183 行：真正发请求

```python
return client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": prompt}],
    temperature=temperature,
    max_tokens=max_tokens,
)
```

- `messages` 是 OpenAI 的固定格式：一个列表，里面是 `{"role": "user", "content": "你的题"}`
- **`role` 只有三种**：`system`（设定）、`user`（用户）、`assistant`（模型）。现在项目只用 `user`，没有 system
- 这四个参数就是"一次调用的全部输入"

### 185–198 行：成功记录

```python
try:
    resp = _do()
```

**这一行看起来调一次，实际可能调了 4 次**（装饰器在重试）。

```python
    text = resp.choices[0].message.content or ""
```

- `choices` 是列表，因为 OpenAI 允许一次返回多个候选，这里只要第 0 个
- `.content` 可能是 `None`（模型返回空），`or ""` 兜底成空字符串

```python
    tin, tout = resp.usage.prompt_tokens, resp.usage.completion_tokens
```

`usage` 是 token 用量，名字是 OpenAI 定的。**这就是成本计算的唯一来源**。

```python
    latency_ms=int((time.time() - t0) * 1000),
```

**注意 `t0` 是 149 行那个**，也就是"含所有重试和等待的总耗时"，不是"最后一次请求的耗时"。这一点要能说清：这条记录的延迟包含退避等待。

```python
    cost_cny=estimate_cost_cny(model, tin, tout),
```

调 `config.py` 的算钱函数。价格表是占位的，所以现在成本基本是 0。

### 199–209 行：失败也要落库

```python
except Exception as e:
```

**写的是 `Exception` 而不是 `RETRYABLE`**，这是全文件最重要的取舍：

如果只写 `except RETRYABLE`，那么 400（参数错）、401（key 错）、JSON 解析崩这类"不可重试"的错会**直接抛穿**，210 行的 `_log` 不执行 —— 结果就是：**你的数据里只有成功的调用，失败率永远 0**。

```python
    error=f"{type(e).__name__}: {str(e)[:120]}",
```

- `type(e).__name__` = 异常类名（`RateLimitError`）
- `str(e)[:120]` = 消息截到 120 字。有些 SDK 异常带整个响应体，几十 KB，不截会把 jsonl 撑到读不动
- 拼成 `"RateLimitError: Error code: 429 - ..."`，**类名和消息都要有**：类名能归因，消息能复现

### 210–211 行：两条路又汇到一处

```python
_log(rec)
return rec
```

和 mock 分支的 141 行同一个套路：**成功、失败都从这里出去**。全文件就两个 `_log` 调用点（83、210 的内部），保证了"没有一次调用不留痕"。

### 214 行：正则

```python
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
```

- 编译一次，全局复用（比每次 `re.search` 快）
- 前面的 `_` 表示模块私有
- 匹配 ````json ... ``` ` 这种围栏，抓出中间的内容

### 217–218 行：函数签名 + 说明

返回 `(True, 解析结果)` 或 `(False, None)`。**注意"返回 False 而不是抛异常"** —— 解析失败算 0 分还是算 error，是评测语义，应由调用方决定，工具层不替你做主。

### 219 行：第一档，先试原文和围栏

```python
for candidate in (text, *(m.group(1) for m in _FENCE.finditer(text))):
```

拆开看：
- `_FENCE.finditer(text)` = 找出所有围栏匹配
- `m.group(1) for m in ...` = 每个匹配取括号里那截（**生成器**，不占内存）
- `*(...)` = 把它们摊平塞进元组
- 结果：`(原文, 围栏内容1, 围栏内容2, ...)`

### 220–223 行：试一个算一个

```python
    try:
        return True, json.loads(candidate)
    except json.JSONDecodeError:
        pass
```

- 成功就**立刻 return**（不再试后面的）
- `except json.JSONDecodeError: pass` = "这个不行就试下一个，什么都不做"

**`pass` 是 Python 里"这里要有句话但我不想做事"的占位符**，因为不允许空块。

### 224–226 行：第二档，截取大括号

```python
start, end = text.find("{"), text.rfind("}")
if 0 <= start < end:
    frag = text[start : end + 1]
```

- `find("{")` = 第一个 `{` 的位置，找不到返回 `-1`
- `rfind("}")` = **最后一个** `}` 的位置
- `0 <= start < end` 是**链式比较**，等价于 `start >= 0 and start < end`。这一步同时排掉了"找不到"（-1）和"括号顺序反了"两种情况
- `text[start : end + 1]` 是**切片**，左闭右开，所以 `+1` 才能把 `}` 带上

场景：模型前面说"好的，结果如下："，JSON 在后面 → 这一刀切掉前面的废话。

### 227–231 行：第三档，单引号换双引号

```python
for cand in (frag, frag.replace("'", '"')):
```

先试原样，再试"把所有单引号换成双引号"。因为 `{'a': 1}` 是 Python 风格，不是合法 JSON。**这是最后的救命一招**。

### 232 行：全败就老实说

```python
return False, None
```

不补括号、不猜字段、不编造。**"宽松解析"是宽容格式，不是修复数据**。

---

## 第 2 部分：三个你被问到必须答得出来的点

### 1. `max_retries=0`（148 行）

> "openai SDK 默认自己会重试 2 次。不关掉的话，我的 4 次退避实际打出去 12 次请求，而记录里的 `attempts` 只记 4 —— 可观测性直接失真。所以必须只留一层重试，而且这层必须是自己的。"

### 2. `except Exception`（199 行）

> "如果只捕可重试错误，400/401 会抛穿，落库那行不执行。数据里就只剩成功样本，**失败率永远是 0，分母悄悄变小**。这是评测里最隐蔽的一种谎言。"

### 3. `return False, None`（232 行）

> "解析失败不抛异常，因为'算 0 分还是算 error'是评测语义，不该由工具层替我决定。"

---

## 第 3 部分：这份代码现在的四个坑（诚实清单）

| 位置 | 问题 | 影响 |
|---|---|---|
| 25 行 | `stop_after_attempt` 导进来了但没用 | 无害的死 import，该删 |
| 163–167 行 | 预算判在起跑前，会溢出到约 1.4 倍 | 5 秒预算实测跑 6.97 秒，需按 1.4 倍预留 |
| `CallRecord` | **没有 `timeout_s` / `budget_s` 字段** | 事后无法知道那条记录当时设的超时和预算，复现时只能猜 |
| 118–142 行 | mock 分支完全不走预算逻辑 | 只影响 mock，真调用不受影响 |

第 3 个是**真缺口**，比前两个值钱：`temperature`、`max_tokens` 都进库了，唯独超时和预算没进。建议加两个字段。

---

## 阅读顺序建议

1. 先只看 **148 行** 和 **199 行** 这两句，把上面第 2 部分的三段话背下来
2. 再看 **153–183 行**（三个内层函数 + 装饰器），这是全部重试行为
3. 最后看 **214–232 行**（解析三档），拿 `_mock_call` 那段假输出自己试
