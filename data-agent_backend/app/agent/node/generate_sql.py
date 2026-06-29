import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


async def generate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
        生成 sql 语句节点
        步骤：
        1、获取用户查询、表信息、指标信息、时间信息、数据库信息
        2、将所有信息序列化为 YAML 格式
        3、调用 LLM 根据上下文信息生气 sql 语句
        4、返回生成 sql
    """
    writer = runtime.stream_writer
    writer({"stage": "生成 sql 语句节点"})

    try:
        query = state.get("query")
        table_infos = state.get("table_infos")
        metric_infos = state["metric_infos"]
        date_info = state.get("date_info")
        db_info = state["db_info"]

        prompt = PromptTemplate(template=load_prompt("generate_sql"),
                                input_variables=["query", "table_infos", "metric_infos", "date_info", "db_info"])
        output_parser = StrOutputParser()
        chain = prompt | llm |output_parser
        sql = await  chain.ainvoke({
            "query": query,
            "table_infos": yaml.dump(table_infos, allow_unicode=True, sort_keys=False),
            "metric_infos": yaml.dump(metric_infos, allow_unicode=True, sort_keys=False),
            "date_info": yaml.dump(date_info, allow_unicode=True, sort_keys=False),
            "db_info": yaml.dump(db_info, allow_unicode=True, sort_keys=False)
        })
        logger.info(f"生成sql成功：{sql}")

        return {"sql": sql}

    except Exception as e:
        logger.error(f"生成 sql 语句节点 ：{str(e)}")
        raise
