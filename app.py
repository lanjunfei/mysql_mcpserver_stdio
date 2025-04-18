#!/usr/bin/env python3
import os
import sys
import asyncio
import re
from flask import Flask, render_template, request, flash, redirect, url_for
from jinja2 import Template
import aiomysql
# ----------------------------------------------------------------------------
# Flask 应用
# ----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-me")

# ----------------------------------------------------------------------------
# Jinja2 模板：MCP Server 基本结构
# ----------------------------------------------------------------------------
server_template = r'''#!/usr/bin/env python3
import os, asyncio, logging,sys
import aiomysql
from mcp.server.fastmcp import FastMCP, Context

# 日志配置
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("mcp_server")

# MySQL 配置
DB = dict(
    host="{{ host }}",
    port={{ port }},
    user="{{ user }}",
    password="{{ password }}",
    db="{{ database }}",
    autocommit=True,
)

# 创建 MCP Server
mcp = FastMCP(
    name="{{ outfile[:-3] }}",
    description="{{ desc }}",
    version="1.0.0"
)

# 全局连接池
_pool = None
async def _query(ctx: Context, sql: str, params: tuple=()):
    global _pool
    if _pool is None:
        _pool = await aiomysql.create_pool(minsize=1, maxsize=8, **DB)
        log.info("MySQL pool created")
    async with _pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()

# === TOOLS ===

def main():
    """入口：支持 stdio 与 HTTP-SSE 双模式"""
    # Windows 事件循环兼容
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    import argparse
    parser = argparse.ArgumentParser(
        description="{{ outfile[:-3] }} — MCP Server (stdio / sse)")
    parser.add_argument("--http", action="store_true",
                        help="启用 HTTP+SSE 模式 (默认 stdio)")
    parser.add_argument("--host", default="0.0.0.0",
                        help="HTTP 绑定地址 (默认 0.0.0.0)")
    parser.add_argument("--port", type=int, default=9000,
                        help="HTTP 端口 (默认 9000)")
    args = parser.parse_args()

    log.info("启动模式: %s", "SSE" if args.http else "STDIO")
    if args.http:
        # SSE 模式
        os.environ["MCP_HOST"] = args.host
        os.environ["MCP_PORT"] = str(args.port)
        mcp.run(transport="sse")
    else:
        # 本地 stdio / subprocess 调用
        mcp.run(transport="stdio")

if __name__ == "__main__":
    main()

'''

# ----------------------------------------------------------------------------
# Jinja2 模板：单个工具函数
# ----------------------------------------------------------------------------
tool_template = r'''
@mcp.tool()
async def {{ func_name }}(ctx: Context{% if params %}, {{ params|join(", ") }}{% endif %}) -> dict:
    """
    {{ desc }}
    """
    rows = await _query(
        ctx,
        """{{ sql }}""",
        ({% if params %}{{ params|join(", ") }},{% endif %})
    )
{% if format_code %}
    content = []
{% for line in format_code.splitlines() %}
    {{ line }}
{% endfor %}
    return {"content": content}
{% else %}
    return {"content": rows}
{% endif %}
'''

def extract_params(sql: str):
    return [f"param{i+1}" for i in range(sql.count("%s"))]

# ----------------------------------------------------------------------------
# 根路由重定向到 /init
# ----------------------------------------------------------------------------
@app.route('/')
def index():
    return redirect(url_for('init_server'))

# ----------------------------------------------------------------------------
# 路由: 初始化 MCP Server 文件
# ----------------------------------------------------------------------------
@app.route('/init', methods=['GET', 'POST'])
def init_server():
    default_tools = ['check_database']  # 默认自动生成的工具
    if request.method == 'POST':
        outfile = request.form['outfile']
        host = request.form['host']
        port = int(request.form['port'])
        user = request.form['user']
        password = request.form['password']
        database = request.form['database']
        desc = request.form.get('desc', '')

        # 渲染基础模板
        tpl = Template(server_template)
        content = tpl.render(
            outfile=outfile,
            host=host, port=port,
            user=user, password=password,
            database=database, desc=desc
        )

        # 自动插入 check_database 工具
        check_code = Template(tool_template).render(
            func_name='check_database',
            desc='检查数据库连接和结构',
            sql='SHOW TABLES',
            params=[]
        )
        content = content.replace('# === TOOLS ===', '# === TOOLS ===\n' + check_code)

        # 写文件
        with open(outfile, 'w', encoding='utf-8') as f:
            f.write(content)

        flash(f"已生成 MCP Server 文件: {outfile}", 'info')
        # 渲染页面并显示已生成的文件名和默认工具
        return render_template('init.html',
                               outfile=outfile,
                               tools=default_tools)
    return render_template('init.html')

# ----------------------------------------------------------------------------
# 路由: 向已有 MCP Server 添加工具函数，并读取现有 DB 配置与工具列表
# ----------------------------------------------------------------------------

@app.route('/add_tool', methods=['GET', 'POST'])
def add_tool():
    files = [f for f in os.listdir('.') if f.endswith('.py')]
    # 1) 选定要操作的文件
    if request.method == 'POST':
        selected = request.form['server_file']
    else:
        selected = request.args.get('server_file') or (files[0] if files else None)

    # 2) 从脚本中提取 DB 配置 & 已有工具列表
    db_conf = {'host':'','port':3306,'user':'','password':'','database':''}
    existing_tools = []
    if selected and os.path.exists(selected):
        text = open(selected, encoding='utf-8').read()
        # 提取 DB 参数
        m = re.search(
            r'DB\s*=\s*dict\(\s*host="([^"]+)",\s*port=(\d+),\s*user="([^"]+)",\s*password="([^"]*)",\s*db="([^"]+)"',
            text
        )
        if m:
            db_conf = {
                'host': m.group(1),
                'port': int(m.group(2)),
                'user': m.group(3),
                'password': m.group(4),
                'database': m.group(5),
            }
        # 列出所有已定义的工具函数
        existing_tools = re.findall(r'@mcp\.tool\(\)\s*async def\s+(\w+)', text)

    if request.method == 'POST':
        # 3) 读取表单
        func_name   = request.form['func_name']
        desc        = request.form['desc']
        sql         = request.form['sql']
        test_params = [p.strip() for p in request.form.get('test_params','').split(',') if p.strip()]
        format_code = request.form.get('format_code','').strip()

        # 4) 验证 SQL
        try:
            async def _test():
                pool = await aiomysql.create_pool(
                    minsize=1, maxsize=1,
                    host=db_conf['host'],
                    port=db_conf['port'],
                    user=db_conf['user'],
                    password=db_conf['password'],
                    db=db_conf['database'],
                    autocommit=True
                )
                async with pool.acquire() as conn, conn.cursor() as cur:
                    if test_params:
                        await cur.execute(sql, tuple(test_params))
                    else:
                        await cur.execute(sql)
                pool.close()
                await pool.wait_closed()
            asyncio.run(_test())
        except Exception as e:
            flash(f"SQL 验证失败: {e}", 'danger')
            return redirect(url_for('add_tool', server_file=selected))

        # 5) 渲染并插入工具
        params    = extract_params(sql)
        tpl       = Template(tool_template)
        func_code = tpl.render(
            func_name=func_name,
            desc=desc,
            sql=sql,
            params=params,
            format_code=format_code
        )
        content   = open(selected, encoding='utf-8').read()
        new_cont  = content.replace('# === TOOLS ===', '# === TOOLS ===\n' + func_code)
        with open(selected, 'w', encoding='utf-8') as f:
            f.write(new_cont)

        flash(f"已在 {selected} 添加工具：{func_name}", 'info')
        return redirect(url_for('add_tool', server_file=selected))

    # 6) 渲染页面
    return render_template(
        'add_tool.html',
        files=files,
        selected=selected,
        existing_tools=existing_tools
    )

@app.route('/delete_tool', methods=['POST'])
def delete_tool():
    """
    删除已有的工具函数：从指定的 MCP Server 文件中
    移除 @mcp.tool() 装饰的整个函数定义。
    """
    selected  = request.form['server_file']
    func_name = request.form['func_name']

    if not selected or not os.path.exists(selected):
        flash(f"找不到文件 {selected}", 'danger')
        return redirect(url_for('add_tool'))

    # 1) 读取文件
    text = open(selected, encoding='utf-8').read()

    # 2) 构造正则：匹配 @mcp.tool() ... async def func_name ... 函数体
    #    支持 Windows (\r\n) 和 Unix (\n) 换行
    pattern = rf"""
        @mcp\.tool\(\)\s*                               # 装饰器行
        async\ def\ {func_name}\b                       # 函数定义行
        [\s\S]*?                                        # 非贪婪匹配函数体
        (?=                                             # 直到...
            (?:@mcp\.tool\(\))|                         # 下一个工具开始
            (?:if\ __name__\s*==\s*['\"]__main__['\"])  # 或文件末尾开始
        )
    """
    # 3) 替换为空
    new_text = re.sub(pattern, "", text, flags=re.MULTILINE|re.VERBOSE)

    # 4) 写回文件
    with open(selected, 'w', encoding='utf-8') as f:
        f.write(new_text)

    flash(f"已删除工具函数：{func_name}", 'info')
    return redirect(url_for('add_tool', server_file=selected))

# ----------------------------------------------------------------------------
# 启动
# ----------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)
