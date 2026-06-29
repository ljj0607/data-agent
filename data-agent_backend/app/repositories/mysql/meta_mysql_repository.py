from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.mysql.table_info_mysql import TableInfoMySQL
from app.models.mysql.metric_info_mysql import MetricInfoMySQL
from app.models.mysql.column_metric_mysql import ColumnMetricMySQL
from app.models.mysql.column_info_mysql import ColumnInfoMySQL

class MetaMysqlRepository:
    """ 操作meta库的持久层类 """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_table_infos(self, table_infos: list[TableInfoMySQL]):
        """ 向table_info表中插入多条数据（已存在则跳过） """
        if not table_infos:
            return

        ids = [item.id for item in table_infos]
        existing = (await  self.session.execute(
            select(TableInfoMySQL.id).where(TableInfoMySQL.id.in_(ids))
        )).scalars().all()
        existing_set = set(existing)
        for item in table_infos:
            if item.id not in existing_set:
                self.session.add(item)

    async def save_column_infos(self, column_infos: list[ColumnInfoMySQL]):
        """ 向column_info表中插入多条数据（已存在则跳过）"""
        if not column_infos:
            return
        ids = [item.id for item in column_infos]
        existing = (await self.session.execute(
            select(ColumnInfoMySQL.id).where(ColumnInfoMySQL.id.in_(ids))
        )).scalars().all()
        existing_set = set(existing)
        for item in column_infos:
            if item.id not in existing_set:
                self.session.add(item)

    async def save_metric_infos(self, metric_infos: list[MetricInfoMySQL]):
        """ 向metric_info表中插入多条数据（已存在则跳过） """
        if not metric_infos:
            return
        ids = [item.id for item in metric_infos]
        existing = (await self.session.execute(
            select(MetricInfoMySQL.id).where(MetricInfoMySQL.id.in_(ids))
        )).scalars().all()
        existing_set = set(existing)
        for item in metric_infos:
            if item.id not in existing_set:
                self.session.add(item)

    async def save_column_metric_infos(self, column_metric_infos: list[ColumnMetricMySQL]):
        """ 向column_metric表中插入多条数据（已存在则跳过）"""
        if not column_metric_infos:
            return
        # 联合主键，逐条判断是否存在
        for item in column_metric_infos:
            existing = await self.session.get(
                ColumnMetricMySQL,
                {"column_id": item.column_id, "metric_id": item.metric_id}
            )
            if existing is None:
                self.session.add(item)

    async def get_column_info_by_id(self, id:str) -> ColumnInfoMySQL:
        """ 根据字段id查询列对象信息 """
        return await self.session.get(ColumnInfoMySQL, id)


    async def get_column_infos_by_table_id(self, table_id: str) -> list[ColumnInfoMySQL]:
        """ 根据表id，查询表的主外键字段 """
        sql = """
            select *
            from column_info
            where table_id = :table_id
            and role in ('primary_key', 'foreign_key') \
        """
        query = select(ColumnInfoMySQL).from_statement(text(sql))
        result = await self.session.execute(query, {"table_id": table_id})
        return result.scalars().all()

    async def get_table_info_by_id(self, table_id: str) -> TableInfoMySQL:
        """
        根据表id查询表信息TableInfoMysql
        """
        return await self.session.get(TableInfoMySQL, table_id)


if __name__ == "__main__":
    import asyncio
    from app.clients.mysql_client_manager import meta_mysql_client_manager

    async def test1():
        meta_mysql_client_manager.init()
        async with meta_mysql_client_manager.engin.begin() as conn:
            await conn.run_sync(TableInfoMySQL.metadata.create_all)
            await conn.run_sync(ColumnInfoMySQL.metadata.create_all)
            await conn.run_sync(MetricInfoMySQL.metadata.create_all)
            await conn.run_sync(ColumnMetricMySQL.metadata.create_all)

        async with meta_mysql_client_manager.session_factory() as session:
            repo = MetaMysqlRepository(session)
            await repo.save_table_infos([
                TableInfoMySQL(id="test_t1", name="orders", role="fact", description="订单表"),
                TableInfoMySQL(id="test_t2", name="users", role="dim", description="用户表"),
            ])
            await session.commit()
            await repo.save_table_infos([
                TableInfoMySQL(id="test_t1", name="orders", role="fact", description="订单表"),
            ])
            print("save_table_infos: ok")
        await meta_mysql_client_manager.close()

    async def test2():
        meta_mysql_client_manager.init()
        async with meta_mysql_client_manager.session_factory() as session:
            repo = MetaMysqlRepository(session)
            await repo.save_column_infos([
                ColumnInfoMySQL(id="test_c1", name="order_id", type="varchar", role="primary_key", examples=["a001"], description="订单ID", alias=["oid"], table_id="test_t1"),
                ColumnInfoMySQL(id="test_c2", name="user_id", type="varchar", role="foreign_key", examples=["u001"], description="用户ID", alias=["uid"], table_id="test_t1"),
                ColumnInfoMySQL(id="test_c3", name="amount", type="decimal", role="measure", examples=["99.99"], description="金额", alias=["money"], table_id="test_t1"),
            ])
            await session.commit()
            print("save_column_infos: ok")
        await meta_mysql_client_manager.close()

    async def test3():
        meta_mysql_client_manager.init()
        async with meta_mysql_client_manager.session_factory() as session:
            repo = MetaMysqlRepository(session)
            t = await repo.get_table_info_by_id("test_t1")
            print("get_table_info_by_id:", t.name if t else None)
            c = await repo.get_column_info_by_id("test_c1")
            print("get_column_info_by_id:", c.name if c else None)
            cols = await repo.get_column_infos_by_table_id("test_t1")
            print("get_column_infos_by_table_id:", len(cols))
        await meta_mysql_client_manager.close()

    async def test4():
        meta_mysql_client_manager.init()
        async with meta_mysql_client_manager.session_factory() as session:
            repo = MetaMysqlRepository(session)
            await repo.save_metric_infos([
                MetricInfoMySQL(id="test_m1", name="GMV", description="商品交易总额", relevant_columns=["test_c3"], alias=["总交易额"]),
            ])
            await session.commit()
            await repo.save_column_metric_infos([
                ColumnMetricMySQL(column_id="test_c3", metric_id="test_m1"),
            ])
            await session.commit()
            await repo.save_column_metric_infos([
                ColumnMetricMySQL(column_id="test_c3", metric_id="test_m1"),
            ])
            print("save_metric_infos: ok")
            print("save_column_metric_infos: ok")
        await meta_mysql_client_manager.close()

    asyncio.run(test1())
    asyncio.run(test2())
    asyncio.run(test3())
    asyncio.run(test4())

