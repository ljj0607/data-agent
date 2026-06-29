import yaml
import json
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


async def filter_metric(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
        过滤指标节点
        步骤：
        1、获取用户查询和指标信息列表
        2、定义提示词模版，调用 LLM 筛选出查询相关的指标名称列表
        3、遍历指标列表，剔除不在 LLM 返回结果的指标
        4、返回过滤后的指标信息列表
    """

    writer = runtime.stream_writer
    writer({"stage": "过滤指标节点"})

    try:
        # 1、获取用户查询和指标信息列表
        query = state.get("query")
        metric_infos = state.get("metric_infos")

        # 2、定义提示词模版，调用 LLM 筛选出查询相关的指标名称列表
        prompt = PromptTemplate(template=load_prompt("filter_metric_info"), input_variables=["query", "metric_infos"])
        output_parser = JsonOutputParser() # 构建数据转换器
        chain = prompt | llm | output_parser
        result = await chain.ainvoke({
            "query": query,
            "metric_infos": yaml.dump(metric_infos, allow_unicode=True, sort_keys=False)
        })

        # 3、遍历指标列表，剔除不在 LLM 返回结果的指标
        for metric_info in metric_infos[:]:
            metric_name = metric_info["name"]
            if metric_name not in result:
                metric_infos.remove(metric_info)

        logger.info(f"过滤指标成功：{metric_infos}")
        return {"metric_infos": metric_infos}

    except Exception as e:
        logger.error(f"过滤指标异常：{str(e)}")
        raise