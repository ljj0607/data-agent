from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def validata_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
        校验SQL的节点
        步骤：
        1、获取生成的 sql 语句
        2、调用数据仓库验证 sql 语法是否正确
        3、验证通过返回 error=None，失败返回错误信息
    """
    writer = runtime.stream_writer
    writer({"stage": "校验SQL的节点"})

    try:
        # 1. 获取生成的 SQL 语句
        sql = state.get("sql")

        #  2、调用数据仓库验证 sql 语法是否正确
        dw_mysql_repository = runtime.context["dw_mysql_repository"]
        await dw_mysql_repository.validate_sql(sql)

        logger.info(f"sql验证正确：{sql}")
        return {"error": None}
    except Exception as e:
        logger.error(f"校验SQL的节点异常：{e}")
        return {"error": f"校验sql异常：str{str(e)}"}
