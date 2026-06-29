from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def execute_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
        执行SQL的节点
        步骤：
        1、获取校验通过的 sql 语句
        2、调用数据仓库执行 sql
        3、将执行结果通过流式输出返回
        4、记录日志
    """
    writer = runtime.stream_writer
    writer({"stage":"执行SQL的节点"})

    try:
        # 1、获取校验通过的 sql 语句
        sql = state.get("sql")

        # 2、调用数据仓库执行 sql
        dw_mysql_repository = runtime.context["dw_mysql_repository"]
        result = await dw_mysql_repository.execute_sql(sql)

        # 3、将执行结果通过流式输出返回
        writer({"result":result})
        logger.info(f"执行sql成功：{result}")

    except Exception as e:
        logger.error(f"执行SQL异常：{e}")
        raise