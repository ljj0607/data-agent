import asyncio
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant



async def recall_column(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    """
        召回字段信息的节点
        步骤：
        1. 获取用户查询和关键词
        2. 使用 LLM 扩展关键词
        3. 合并原始关键词和扩展关键词
        4. 遍历关键词转向量后查询 Qdrant
        5. 按字段 ID 去重，返回召回字段列表
    """


    await asyncio.sleep(1)
    writer = runtime.stream_writer
    writer({"stage": "召回字段"})

    try:
        embedding_client=runtime.context["embedding_client"]
        column_qdrant_repository = runtime.context["column_qdrant_repository"]
        query = state.get("query", "") # 用户问题
        keywords = state.get("keywords", "") # 提取关键字

        #  1、扩展关键字
        prompt = PromptTemplate(template=load_prompt("extend_keywords_for_column_recall"), input_variables=["query"])
        output_parser= JsonOutputParser()
        chain = prompt | llm | output_parser
        result = await chain.ainvoke({"query": query})  # 需要 await
        keywords = set(keywords+result)

        # 定义字典去重字段对象
        recall_columns_map: dict[str, ColumnInfoQdrant] = {}

        # 2.召回字段
        for keyword in keywords:
            # 2.1 转换向量
            embeddings = await embedding_client.aembed_query(keyword)
            payloads: list[ColumnInfoQdrant] = await column_qdrant_repository.search(embeddings)
            for payload in payloads:
                column_id = payload["id"]
                if column_id not in recall_columns_map:
                    recall_columns_map[column_id] = payload
        # 获取去重的字段列表
        recall_columns: list[ColumnInfoQdrant] = list(recall_columns_map.values())
        logger.info(f"召回字段信息成功：f{list(recall_columns_map.keys())}")
        return {"recall_columns": recall_columns}

    except Exception as e:
        logger.error(f"召回字段信息异常：{str(e)}")
        raise


if __name__ == "__main__":
    from unittest.mock import MagicMock
    from app.clients.embedding_client_manager import embedding_client_manager
    from app.clients.qdrant_client_manager import qdrant_client_manager
    from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository

    async def test1():
        state = {
            "query": "统计华北地区去年销售总额",
            "keywords": ['地区', '销售总额', '统计 2025年各地区销售总额', '统计']
        }
        embedding_client_manager.init()
        qdrant_client_manager.init()
        mock_runtime = MagicMock()
        mock_writer = MagicMock()
        mock_runtime.stream_writer = mock_writer
        mock_runtime.context = {
            "embedding_client": embedding_client_manager.client,  # 新增
            "column_qdrant_repository": ColumnQdrantRepository(qdrant_client_manager.client)  # 新增
        }

        await recall_column(state, mock_runtime)
    asyncio.run(test1())