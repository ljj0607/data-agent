from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.clients.mysql_client_manager import dw_mysql_client_manager

class DWMysqlRepository:
    """ 操作dw数据库的持久层类 """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_column_values(self, table_name: str, column_name: str, limit: int = 10):
        """ 查询指定字段的取值 """
        # 定义sql
        sql = f"select distinct {column_name} from {table_name} limit {limit}"
        # 执行sql
        result = await self.session.execute(text(sql))
        # [row(C001),row(C002),row(C003)]
        return result.scalars().all()

    async def get_column_types(self, table_name: str):
        """ 查询表中字段的类型 """
        # 定义sql
        sql = f"show columns from {table_name}"
        # 执行sql
        result = await self.session.execute(text(sql))
        # [row(),row(),row()]

        # 获取结果，组装数据
        return {row.Field: row.Type for row in result.all()}

    async def get_db_info(self):
        """ 查询数据库信息 """
        # 查询数据的版本
        result = await self.session.execute(text("select version()"))
        # 获取版本
        version = result.scalar()

        # 查询数据库方言
        dialect = self.session.bind.dialect.name

        return {"version": version, "dialect": dialect}

    async def validate_sql(self, sql: str):
        """ 使用explain 关键字校验sql """
        await  self.session.execute(text(f"explain {sql}"))

    async def execute_sql(self, sql: str):
        """ 使用explain 关键字校验sql """
        # [(),(),()]
        result = await self.session.execute(text(sql))
        # 调整格式 [{RowMapping对象（key:value）},{}]
        return [dict(row) for row in result.mappings().all()]


if __name__ == '__main__':
    import asyncio
    async def test1():
        dw_mysql_client_manager.init()
        async with dw_mysql_client_manager.session_factory() as session:
            rep = DWMysqlRepository(session)
            result = await rep.get_column_values("dim_customer", "customer_name")
        await dw_mysql_client_manager.close()

    async def test2():
        dw_mysql_client_manager.init()
        async with dw_mysql_client_manager.session_factory() as session:
            rep = DWMysqlRepository(session)
            result = await rep.get_column_types("dim_customer")
        await dw_mysql_client_manager.close()

    asyncio.run(test1())
    asyncio.run(test2())

