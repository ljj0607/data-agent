import asyncio

import jieba.analyse
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def extract_keywords(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    """
        提取查询关键字的节点
        功能：
        1、输出进度信息
        2、从 state 中获取用户查询
        3、使用 jieba 提取指定词性（名词、动词、形容词）的关键字
        4、原始查询加入关键词列表，合并后去重返回

    """

    await asyncio.sleep(1)
    # 获取流对象
    writer = runtime.stream_writer
    # 输出进度信息
    writer({"stage": "提取关键字"})
    try:
        # 获取问题
        query = state["query"]
    # 定义词性
        # 定义返回指定词性的元组
        allow_pos = (
            "n",  # 名词: 数据、服务器、表格
            "nr",  # 人名: 张三、李四
            "ns",  # 地名: 北京、上海
            "nt",  # 机构团体名: 政府、学校、某公司
            "nz",  # 其他专有名词: Unicode、哈希算法、诺贝尔奖
            "v",  # 动词: 运行、开发
            "vn",  # 名动词: 工作、研究
            "a",  # 形容词: 美丽、快速
            "an",  # 名形词: 难度、合法性、复杂度
            "eng",  # 英文
            "i",  # 成语
            "l",  # 常用固定短语
        )

        # jieba分词
        keywords: list[str] = jieba.analyse.extract_tags(query, allowPOS=allow_pos)
        # 避免缺失语义，确实关键字
        keywords = list(set(keywords + [query]))
        logger.info(f"提取关键字成功：{keywords}")
        return {"keywords": keywords}
    except Exception as e:
        logger.error(f"提取关键字异常:{str(e)}")

if __name__ == "__main__":
    from unittest.mock import MagicMock

    async def test1():
        state = {"query": "统计华北地区销售总额"}
        mock_runtime = MagicMock()
        mock_writer = MagicMock()
        mock_runtime.stream_writer = mock_writer

        result = await extract_keywords(state, mock_runtime)
        print("keywords:", result["keywords"])

    async def test2():
        state = {"query": "统计 2025年各地区销售总额"}
        mock_runtime = MagicMock()
        mock_writer = MagicMock()
        mock_runtime.stream_writer = mock_writer

        result = await extract_keywords(state, mock_runtime)
        print("keywords:", result)

    asyncio.run(test1())
    asyncio.run(test2())