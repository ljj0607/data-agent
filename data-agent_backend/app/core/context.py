from contextvars import ContextVar

"""
    创建上下文变量对象， 用于在异步/多请求场景下存储和获取当前请求的唯一标识request_id
"""

_req_id_context_var: ContextVar[int] = ContextVar("request_id", default=1)

def set_request_id(request_id: int):
    """ 保存 id"""
    _req_id_context_var.set(request_id)

def get_request_id(request_id: int):
    """ 读取 id"""
    return _req_id_context_var.get()

if __name__ == "__main__":
    import asyncio

    # 测试同一个请求中的操作
    async def test1():
        set_request_id(3)
        print(_req_id_context_var.get())
        set_request_id(4)
        print(_req_id_context_var.get())
    asyncio.run(test1())

    # 模拟请求 1 操作
    async def req1():
        print(_req_id_context_var.get())
        set_request_id(5)
        print(_req_id_context_var.get())

    # 模拟请求 2 操作
    async def req2():
        print(_req_id_context_var.get())
        set_request_id(6)
        print(_req_id_context_var.get())

    async def test2():
        cor1 = req1()
        cor2 = req2()

        await asyncio.gather(cor1, cor2)

    asyncio.run(test2())
