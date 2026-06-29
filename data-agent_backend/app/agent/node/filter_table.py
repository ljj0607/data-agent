import json
import yaml
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


async def filter_table(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
        过滤表信息节点
        步骤：
        1、获取用户查询和表信息列表
        2、调用 LLM 筛选出查询相关的表及字段（返回字典格式：{表名: [字段名列表]}）
        3、遍历表列表，剔除不在LLM 返回结果中的表
        4、遍历保留表中的字段，剔除不在 LLM 返回字段列表中的字段
        5、返回过滤的表信息列表

    """
    writer = runtime.stream_writer
    writer({"stage": "过滤表信息节点"})

    try:
        # 1、获取用户查询和表信息列表
        query = state.get("query")
        table_infos = state.get("table_infos")

        # 2、调用 LLM 筛选出查询相关的表及字段（返回字典格式：{表名: [字段名列表]}）
        prompt = PromptTemplate(template=load_prompt("filter_table_info"), input_variables=["query", "table_infos"])
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser
        result = await chain.ainvoke({
            "query": query,
            "table_infos": yaml.dump(table_infos, allow_unicode=True, sort_keys=False)
        })

        # 3、遍历表列表，剔除不在LLM 返回结果中的表
        for table_info in table_infos[:]:
            table_name = table_info["name"]
            if table_name not in result:
                table_infos.remove(table_info)
            else:
                # 4、遍历保留表中的字段，剔除不在 LLM 返回字段列表中的字段
                result_column = result[table_name]
                for column_info in table_info["columns"][:]:
                    column_name = column_info["name"]
                    if column_name not in result_column:
                        table_info["columns"].remove(column_info)

        logger.info(f"过滤表成功：{table_infos}")
        return {"table_infos": table_infos}

    except Exception as e:
        logger.error(f"过滤表信息异常：{e}")
        raise

