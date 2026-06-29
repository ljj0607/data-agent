import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


async def correct_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
        修正SQL的节点
        步骤：
        1、获取错误的 sql 语句和异常信息
        2、获取用户查询、表信息、指标信息、时间信息、数据库信息
        3、将所有信息序列化为 YAML 格式
        4、调用 LLM 根据错误信息修正 sql
        5、反正修正后的 sql
    """
    writer = runtime.stream_writer
    writer({"stage": "修正SQL的节点"})

    try:
        # 1、获取错误的 sql 语句和异常信息
        sql = state.get("sql")
        error = state.get("error")

        # 2、获取用户查询、表信息、指标信息、时间信息、数据库信息
        query = state.get("query")
        table_infos = state.get("table_infos")
        metric_infos = state.get("metric_infos")
        date_info = state.get("date_info")
        db_info = state.get("db_info")

        # 3、将所有信息序列化为 YAML 格式
        prompt = PromptTemplate(template=load_prompt("correct_sql"),
                                input_variables=["query", "table_infos", "metric_infos", "date_info", "db_info","error","sql"])
        output_parser = StrOutputParser()
        chain = prompt | llm | output_parser
        result = await chain.ainvoke({
            "query": query,
            "sql": sql,
            "error": error,
            "table_infos": yaml.dump(table_infos, allow_unicode=True, sort_keys=False),
            "metric_infos": yaml.dump(metric_infos, allow_unicode=True, sort_keys=False),
            "date_info": yaml.dump(date_info, allow_unicode=True, sort_keys=False),
            "db_info": yaml.dump(db_info, allow_unicode=True, sort_keys=False),

        })

        logger.info(f"校正sql成功：{result}")
        return {"sql": result}

    except Exception as e:
        logger.error(f"修正SQL的节点异常：{sql}")
        raise