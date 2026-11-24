"""Provider 注册表、价格表、路径。

注意：PRICE 表的数字是占位值，只用来把"成本"这一列跑通。
请按各家控制台的实际单价改，不要在报告里直接引用这里的数字。
"""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
CALLS_LOG = RESULTS_DIR / "calls.jsonl"

# base_url 都以 OpenAI 兼容模式为准（国内三家都支持）
PROVIDERS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "key_env": "DEEPSEEK_API_KEY",
    },
    # 百炼：2026-09-30 起 dashscope.aliyuncs.com 进维护，新号一律用"业务空间专属域名"
    # 这个域名在 百炼控制台 → API-KEY 页顶部"按量付费 Base URL"里能抄到，每个账号不同
    "qwen": {
        "base_url": "https://ws-kzomyfwc27jeow0c.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "key_env": "DASHSCOPE_API_KEY",
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "key_env": "SILICONFLOW_API_KEY",
    },
    # 智谱：glm-4-flash 有免费额度，适合零成本把第四条链路跑通
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "key_env": "ZHIPU_API_KEY",
    },
    # D3 用的本地故障服务器（OpenAI 兼容），只在自己机器上跑，不产生费用
    # 行为由 model 名决定，见 src/eval_lab/faults.py
    "fault": {
        "base_url": "http://127.0.0.1:8791/v1",
        "model": os.getenv("FAULT_MODEL", "fault-ok"),
        "key_env": "FAULT_API_KEY",
    },
    # 不需要 key 的假 provider，用来在没有额度时验证整条链路
    "mock": {
        "base_url": "mock://local",
        "model": "mock-model",
        "key_env": "",
    },
}

# 元 / 百万 token（占位值，务必按控制台改）
PRICE_CNY_PER_MTOK = {
    "deepseek-chat": (1.0, 2.0),
    "qwen-plus": (0.8, 2.0),
    "Qwen/Qwen2.5-7B-Instruct": (0.0, 0.0),
    "glm-4-flash": (0.0, 0.0),
    "mock-model": (0.0, 0.0),
}


def estimate_cost_cny(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICE_CNY_PER_MTOK.get(model, (0.0, 0.0))
    return (input_tokens / 1_000_000) * price_in + (output_tokens / 1_000_000) * price_out
