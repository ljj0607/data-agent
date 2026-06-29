from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.prompt.prompt_loader import load_prompt


async def recall_value(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    """
        召回字段取值信息的节点
        步骤：
        1、获取用户查询和关键词
        2、使用 llm 扩展关键词
        3、合并原始关键词和扩展关键词
        4、遍历关键词查询 ES（文本检索，无需向量化）
        5、按取值 ID 去重，返回召回取值表
    """
    writer = runtime.stream_writer
    writer({"stage": "召回字段取值"})

    try:
        value_es_repository = runtime.context["value_es_repository"]
        query = state.get("query", "")
        keywords = state.get("keywords", "")

        # 1.扩展关键字
        prompt = PromptTemplate(template=load_prompt("extend_keywords_for_value_recall"), input_variables=["query"])
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser
        result = await chain.ainvoke({"query": query})

        # 2、合并关键字
        keywords = set(keywords+result)

        # 定义map去重收集取值结果
        value_maps: dict[str, ValueInfoEs] = {}

        # 3、召回字段取值
        for keyword in keywords:
            values:list[ValueInfoEs] = await value_es_repository.search(keyword)
            for value in values:
                value_id = value["id"]
                if value_id not in value_maps:
                    value_maps[value_id]=value

        # 转换结果结构
        recall_values: list[ValueInfoEs] = list(value_maps.values())
        logger.info(f"召回字段取值成功：{list(value_maps.keys())}")
        return {"recall_values": recall_values}

    except Exception as e:
        logger.error(f"召回字段取值异常{str(e)}")
        raise

