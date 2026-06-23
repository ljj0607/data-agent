"""
操作mysql数据库数据的客户端管理器模块
"""
import asyncio
from typing import Optional
from urllib.parse import quote_plus
from sqlalchemy import text, Select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession, async_sessionmaker
from app.conf.app_config import app_config, DBConfig
from app.models.mysql.table_info_mysql import TableInfoMySQL

class MysqlClientManager:
    """ mysql数据库数据 """

    def __init__(self, config: DBConfig):
        self.config = config
        self.engin: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None

    # 获取连接字符串
    def _get_url(self):
        pwd = quote_plus(self.config.password)
        return f"mysql+asyncmy://{self.config.user}:{pwd}@{self.config.host}:{self.config.port}/{self.config.database}?charset=utf8mb4"
    # 初始化
    def init(self):
        # 创建一个异步引擎
        self.engin = create_async_engine(
            self._get_url(),
            pool_size=10, # 内部连接池中缓存的长久连接数   默认是5
            pool_pre_ping = True, # 是否开启自动检测连接是否可用的开关，true代表开启检测，防止连接意外被关闭导致失败 默认是False
        )
        self.session_factory = async_sessionmaker(
            self.engin,
            autoflush=False,  # 查询看不到前面未提交的修改
            autobegin=True,  # 自动开启事务
            expire_on_commit=False  # 提交事务后，ORM对象不过期，还可以读取它的属性数据
        )
    # 释放资源
    async def close(self):
        await self.engin.dispose()

# 创建操作dw库的客户端管理器
dw_mysql_client_manager = MysqlClientManager(app_config.db_dw)
# 创建操作meta库的客户端管理器
meta_mysql_client_manager = MysqlClientManager(app_config.db_meta)

if __name__  == "__main__":
    async def test_orm():
        # 初始化meta客户端对象
        meta_mysql_client_manager.init()

        # 自动创建表（不存在才创建）
        async with meta_mysql_client_manager.engin.begin() as  conn:
            await conn.run_sync(TableInfoMySQL.metadata.create_all)

        # 创建异步会话
        async with meta_mysql_client_manager.session_factory() as session:
            session: AsyncSession

            # 添加一条数据
            info1 = TableInfoMySQL(
                id="dim_customer5",
                name="dim_customer5",
                role="dim",
                description="客户信息维度表5"
            )
            session.add(info1)
            # 再添加一条数据
            info2 = TableInfoMySQL(
                id="dim_customer6",
                name="dim_customer6"
                ,
                role="dim",
                description="客户信息维度表6"
            )
            session.add(info2)

            # 提交事务
            await session.commit()

            # 查询一条数据
            table_info = await session.get(TableInfoMySQL, "dim_customer1")

            # 查询多条数据
            result = await session.execute(Select(TableInfoMySQL).limit(2))
            rows: list[TableInfoMySQL] = result.scalars().all()
            print(rows)
            print(rows[0].description)

            # 看是否可以在提交事务后读取ORM对象的属性
            print(info1.name)

        # 释放资源
        await meta_mysql_client_manager.close()

    asyncio.run(test_orm())