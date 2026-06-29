from langgraph.constants import START, END
from langgraph.graph import StateGraph

from app.agent.node.add_extra_context import add_extra_context
from app.agent.node.correct_sql import correct_sql
from app.agent.node.execute_sql import execute_sql
from app.agent.node.filter_table import filter_table
from app.agent.node.extract_keywords import extract_keywords
from app.agent.node.filter_metric import filter_metric
from app.agent.node.generate_sql import generate_sql
from app.agent.node.merge_retrieved_info import merge_retrieved_info
from app.agent.node.recall_column import recall_column
from app.agent.node.recall_metric import recall_metric
from app.agent.node.recall_value import recall_value
from app.agent.node.validata_sql import validata_sql
from app.agent.state import DataAgentState
from app.agent.context import DataAgentContext
from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw_mysql_repository import DWMysqlRepository
from app.repositories.mysql.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository

graph_builder = StateGraph(
    state_schema=DataAgentState,
    context_schema=DataAgentContext,
)

# 添加节点
graph_builder.add_node("extract_keywords",extract_keywords) # 提取关键字
graph_builder.add_node("recall_column", recall_column)  # 召回字段信息
graph_builder.add_node("recall_metric", recall_metric)  # 召回指标信息
graph_builder.add_node("recall_value", recall_value)  # 字段取值信息
graph_builder.add_node("merge_retrieved_info", merge_retrieved_info) # 合并多路召回
graph_builder.add_node("filter_metric", filter_metric) # 过滤指标节点
graph_builder.add_node("filter_table", filter_table) # 过滤表信息节点
graph_builder.add_node("add_extra_context", add_extra_context) # 添加额外上下文的节点
graph_builder.add_node("generate_sql", generate_sql) # 生成 sql 语句节点
graph_builder.add_node("validata_sql", validata_sql) # 校验SQL的节点
graph_builder.add_node("correct_sql", correct_sql) # 修正SQL的节点
graph_builder.add_node("execute_sql", execute_sql) # 执行SQL的节点

# 添加边
graph_builder.add_edge(START,"extract_keywords")
graph_builder.add_edge("extract_keywords","recall_column")
graph_builder.add_edge("extract_keywords","recall_metric")
graph_builder.add_edge("extract_keywords","recall_value")
graph_builder.add_edge("recall_column","merge_retrieved_info")
graph_builder.add_edge("recall_metric","merge_retrieved_info")
graph_builder.add_edge("recall_value","merge_retrieved_info")
graph_builder.add_edge("merge_retrieved_info","filter_metric")
graph_builder.add_edge("merge_retrieved_info","filter_table")
graph_builder.add_edge("filter_metric","add_extra_context")
graph_builder.add_edge("filter_table","add_extra_context")
graph_builder.add_edge("add_extra_context","generate_sql")
graph_builder.add_edge("generate_sql","validata_sql")

# 处理条件边
graph_builder.add_conditional_edges(
    "validata_sql",
    lambda state: "execute_sql" if state["error"] is None else "correct_sql" ,
    {
        "correct_sql":"correct_sql",
        "execute_sql":"execute_sql"
    }
)
graph_builder.add_edge("correct_sql","execute_sql")
graph_builder.add_edge("execute_sql",END)

# 编译图
graph = graph_builder.compile()

if __name__ == "__main__":
    import asyncio
    async def test():
        # 创建状态对象
        state = DataAgentState(query="统计华北地区去年销售总额")
        # 初始化客户端
        embedding_client_manager.init()
        qdrant_client_manager.init()
        es_client_manager.init()
        meta_mysql_client_manager.init()
        dw_mysql_client_manager.init()

        async with meta_mysql_client_manager.session_factory() as meta_session, dw_mysql_client_manager.session_factory() as dw_session:
            # 创建repository
            column_qdrant_repository = ColumnQdrantRepository(qdrant_client_manager.client)
            metric_qdrant_repository = MetricQdrantRepository(qdrant_client_manager.client)
            value_es_repository = ValueESRepository(es_client_manager.client)
            meta_mysql_repository = MetaMysqlRepository(meta_session)
            dw_mysql_repository = DWMysqlRepository(dw_session)
            # 创建上下文对象
            runtime = DataAgentContext(
                embedding_client=embedding_client_manager.client,
                column_qdrant_repository=column_qdrant_repository,
                metric_qdrant_repository=metric_qdrant_repository,
                value_es_repository=value_es_repository,
                meta_mysql_repository=meta_mysql_repository,
                dw_mysql_repository=dw_mysql_repository
            )

            # 执行图
            async  for chunk in graph.astream(input=state, context=runtime, stream_mode="custom"):
                pass


        # 释放资源
        await qdrant_client_manager.close()
        await es_client_manager.close()
        await meta_mysql_client_manager.close()
        await dw_mysql_client_manager.close()
    asyncio.run(test())

