import uuid
import uvicorn
from fastapi import FastAPI, Request
from app.api.routers.query_router import query_router
from app.core.context import set_request_id
from app.core.lifespan import lifespan

# 创建 FastAPI 应用实例
app = FastAPI(lifespan=lifespan)

# 注册路由
app.include_router(query_router)

# 整合中间件->设置异步协程上下文变量
@app.middleware("http")
async def add_request_cxt_var(request: Request, call_next):
    # 设置异步协程上下文变量
    set_request_id(uuid.uuid4())
    return await call_next(request)

if __name__ == "__main__":
    # 启动后台API服务
    uvicorn.run(app, host="0.0.0.0", port=8001)


