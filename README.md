# mysql_mcpserver_stdio  
mcp格式如此标准，一定可以批量复制server文件。  
批量生成基于mysql数据库的mcpserver,支持stdio传输。Generate MCP servers in batch based on MySQL database, supporting stdio transmission.  
语言python 前端FLASK  
安装：虚拟环境安装requirments.txt.  
运行：python app.py  
浏览器输入地址：127.0.0.1:5000  进入server文件生成页面。输入mysql数据库参数，包括：ip,端口，用户名（最好专门建一个账号），密码，数据库名。生成的mcp server名,需要带.py。目录下生成py文件。默认自带check_database函数，检查数据库连接用的。  
进入工具函数添加页面：输入你定义的工具函数名，SQL语句（mysql的mcpserver文件当然从查询工具开始），  
SQL查询后的输出格式（可以不填）参考下面：  
for row in rows:  
    content.append("设备账号: " + row['username'])  
    content.append("IPv4地址: " + row['user_ip4'])  
    content.append("MAC地址: " + row['user_mac'].replace(":", "-"))  
注意对齐，content前面有四个空格。  
生成的server文件可以先用MCP Inspector测试一下，看看工具调用是否正常。  
mcp client就直接用现成的工具。推荐用cherrystudio,比较方便。  
