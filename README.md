# MySQL MCP 服务器生成器（支持 stdio + SSE）

本项目用于**批量**生成基于 **MySQL** 的 MCP 服务器脚本。每个生成的脚本同时支持两种传输方式：

* **stdio** – 通过本地子进程 / 管道调用
* **SSE (HTTP)** – 通过 `/sse` 端点提供远程访问（适配 MCP Inspector）

---

## 安装

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux / WSL
source .venv/bin/activate

pip install -r requirements.txt
```

---

## 使用流程

### 1️⃣ 启动生成器界面

```bash
python app.py
```

在浏览器打开 **http://127.0.0.1:5000**，依次完成：

1. 输入 MySQL 连接信息（主机、端口、用户、密码、数据库）。
2. 指定输出文件名（**必须以 `.py` 结尾**，如 `my_server.py`）。
3. 点击 **生成**。脚本会自动包含一个 `check_database` 工具用于快速连通性测试。

### 2️⃣ 添加自定义工具

进入 **“新增工具函数”** 页面，为每条 SQL 查询填写：

| 字段 | 说明 |
|------|------|
| 工具函数名 | 使用 `snake_case` |
| 工具说明 | 1 行描述 |
| SQL 语句 | 使用 `%s` 占位符传参 |
| 输出格式(可选) | Python 代码片段，用 `content.append()` 拼接返回文本 |

示例格式化代码：

```python
for row in rows:
    content.append(f"设备账号: {row['username']}")
    content.append(f"IPv4: {row['user_ip4']}")
```

保存后脚本会自动插入工具函数。

### 3️⃣ 运行生成的服务器脚本

| 模式 | 命令 | 访问地址 |
|------|------|----------|
| **stdio**（默认） | `python my_server.py` | – |
| **SSE / HTTP**   | `python my_server.py --http` | `http://127.0.0.1:8000/sse` |

> 📌 **注意**
> 当前 `FastMCP.run()` 默认监听 `0.0.0.0:8000`。
> 若需自定义端口，可在启动前设置环境变量，例如：
>
> ```bash
> # Windows
> set MCP_PORT=9110
> # Linux / macOS / WSL
> export MCP_PORT=9110
> python my_server.py --http
> ```

### 4️⃣ 用 MCP Inspector 测试

```bash
npx @modelcontextprotocol/inspector
```

* Transport 选择 **SSE**
* URL 填写 **http://127.0.0.1:8000/sse**

连接成功后，即可在左侧看到自动发现的工具列表并进行调用。

---

## 项目结构

```
├── app.py            # Flask GUI 生成器
├── templates/        # Jinja2 + Bootstrap 页面
├── static/           # 前端静态资源
├── requirements.txt  # 依赖列表
└── README.md         # 使用说明（本文件）
```

祝你开发顺利，快速批量生成 MCP Server！


