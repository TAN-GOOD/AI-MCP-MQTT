# 小智 MCP-MQTT 管理系统

让小智 AI 通过 MCP 协议控制物联网设备的一站式管理平台。

你只需要在网页上点点鼠标，就能让小智语音控制你的灯、风扇、传感器等 IoT 设备，**不需要写任何代码**。

---

**快速导航**

[它能做什么](#它能做什么) · [效果演示](#效果演示) · [部署方式](#部署方式选择) · [Ubuntu 一键安装](#方式一ubuntu-一键安装最简单) · [Docker 部署](#方式二docker-部署推荐) · [源码手动部署](#方式三手动部署) · [使用指南](#使用指南) · [常见问题](#常见问题) · [API 接口](#api-接口一览) · [项目结构](#项目结构)

---

## 它能做什么？

- 对小智说 **"开灯"**，灯就亮了
- 对小智说 **"查看温度"**，小智会告诉你传感器的最新数据
- 对小智说 **"打开空调"**，系统会调用你的 HTTP 接口控制空调
- 一个账号可以创建 **多个项目**，每个项目连接不同的设备
- 所有操作都有 **实时日志**，方便排查问题

## 效果演示

```
你：小智，帮我把卧室的灯打开
小智：好的，灯已打开
（系统自动发送 MQTT 消息 "on" 到设备）
```

## 技术架构

```
用户说话 → 小智 AI（大模型）→ MCP 协议 → 本系统 → MQTT/HTTP → 你的设备
```

- **后端**：Python + FastAPI + SQLAlchemy + paho-mqtt
- **前端**：单页 HTML 应用（Linear 风格暗色主题）
- **数据库**：MySQL
- **协议**：MCP（JSON-RPC 2.0 over WebSocket）

## 环境要求

在开始之前，请确认你的电脑上已经安装了以下软件：

| 软件 | 最低版本 | 用途 | 下载地址 |
|------|---------|------|---------|
| Python | 3.9+ | 运行后端 | https://www.python.org/downloads/ |
| MySQL | 5.7+ | 存储数据 | https://dev.mysql.com/downloads/mysql/ |
| Git | 任意 | 下载代码 | https://git-scm.com/downloads |

如果你安装了 **Anaconda**，Python 已经自带了，不需要额外安装。

> 💡 **小白提示**：不确定有没有装 Python？打开命令行（Win+R 输入 cmd 回车），输入 `python --version`，如果显示版本号就说明已经装好了。

## 部署方式选择

| 方式 | 适合谁 | 难度 | 说明 |
|------|--------|------|------|
| [Ubuntu 一键安装](#方式一ubuntu-一键安装最简单) | 有 Ubuntu 服务器的用户 | ⭐ | 一条命令搞定，自动安装所有依赖 |
| [Docker 部署](#方式二docker-部署推荐) | 任何系统，已安装 Docker | ⭐⭐ | 一条命令启动，不污染系统环境 |
| [源码手动部署](#方式三手动部署) | Windows/Mac/Linux 开发者 | ⭐⭐⭐ | 适合需要二次开发的用户 |

---

### 方式一：Ubuntu 一键安装（最简单）

只需要一条命令，自动完成所有安装步骤：

```bash
curl -fsSL https://gitee.com/T510/ai-xiaozhi-mcp/raw/master/install.sh | bash
```

或者先下载再执行：

```bash
wget https://gitee.com/T510/ai-xiaozhi-mcp/raw/master/install.sh
chmod +x install.sh
./install.sh
```

脚本会自动完成以下操作：
1. 检测并安装 Python 3.11
2. 检测并安装 MySQL
3. 创建数据库和用户
4. 克隆项目代码到 `~/ai-xiaozhi-mcp`
5. 创建虚拟环境并安装依赖
6. 生成配置文件
7. 初始化数据库表
8. 注册为系统服务（开机自启）

安装完成后会显示访问地址和数据库密码，请妥善保存。

### 方式三：手动部署

#### 第一步：下载代码

打开命令行，执行：

```bash
git clone https://gitee.com/T510/ai-xiaozhi-mcp.git
cd ai-xiaozhi-mcp
```

或者直接在 Gitee 页面点击「克隆/下载」→「下载ZIP」，解压后进入文件夹。

### 第二步：创建 Python 虚拟环境

**方式 A：使用 Anaconda（推荐）**

```bash
# 创建虚拟环境
conda create --prefix ./venv python=3.11 -y

# 激活虚拟环境
conda activate ./venv
```

**方式 B：使用 Python 自带的 venv**

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境（Windows）
venv\Scripts\activate

# 激活虚拟环境（Mac/Linux）
source venv/bin/activate
```

激活成功后，命令行前面会出现 `(venv)` 字样。

### 第三步：安装依赖

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> 💡 使用了清华镜像源加速下载。如果网络好，也可以去掉 `-i ...` 部分。

### 第四步：创建 MySQL 数据库

打开 MySQL 命令行或任意数据库管理工具（如 Navicat、phpMyAdmin），执行：

```sql
CREATE DATABASE xiaozhi_mcp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 第五步：配置环境变量

复制配置模板：

```bash
# Windows
copy .env.example .env

# Mac/Linux
cp .env.example .env
```

用记事本打开 `.env` 文件，修改为你的实际配置：

```ini
# 数据库连接地址（格式：mysql+pymysql://用户名:密码@地址:端口/数据库名）
DATABASE_URL=mysql+pymysql://root:你的MySQL密码@localhost:3306/xiaozhi_mcp

# JWT 密钥（随便改一个复杂的字符串就行）
SECRET_KEY=my-super-secret-key-2024

# 登录有效期（分钟），1440 = 24小时
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

> ⚠️ `.env` 文件包含密码等敏感信息，**不要提交到 Git**（已在 .gitignore 中排除）。

### 第六步：初始化数据库表

```bash
python init_db.py
```

看到以下输出说明成功：

```
正在创建数据库表...
数据库表创建完成！

已创建的表：
  - users
  - projects
  - operation_logs
  - tools
```

### 第七步：启动服务

```bash
python run.py
```

看到以下输出说明启动成功：

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

打开浏览器访问：**http://localhost:8000**

---

## 方式二：Docker 部署（推荐）

如果你不想手动安装 Python 和 MySQL，Docker 是最简单的方式。**一条命令搞定所有环境。**

### 前提条件

安装 Docker Desktop：

- **Windows**：https://docs.docker.com/desktop/install/windows-install/
- **Mac**：https://docs.docker.com/desktop/install/mac-install/
- **Linux**：https://docs.docker.com/engine/install/

安装后打开终端，输入 `docker --version` 看到版本号说明安装成功。

### 第一步：下载代码

```bash
git clone https://gitee.com/T510/ai-xiaozhi-mcp.git
cd ai-xiaozhi-mcp
```

### 第二步：修改配置（可选）

编辑 `docker-compose.yml`，找到以下几行，改成你自己的密码：

```yaml
# MySQL root 密码（两个地方要保持一致）
MYSQL_ROOT_PASSWORD: xiaozhi123456          # 改这里
DATABASE_URL: mysql+pymysql://root:xiaozhi123456@db:3306/xiaozhi_mcp  # 和上面一样

# JWT 密钥（随便改一个复杂的字符串）
SECRET_KEY: change-this-to-a-random-string-in-production
```

> 💡 如果只是本地测试，不改也能用。

### 第三步：一键启动

```bash
docker compose up -d
```

第一次运行会自动下载 MySQL 和 Python 镜像，大约需要 2-5 分钟（取决于网速）。之后启动只需要几秒。

看到类似以下输出说明启动成功：

```
[+] Running 3/3
 ✔ Network xiaozhi-mcp_default    Created
 ✔ Container xiaozhi-mysql        Healthy
 ✔ Container xiaozhi-app          Started
```

### 第四步：初始化数据库

第一次启动后需要初始化数据库表：

```bash
docker exec xiaozhi-app python init_db.py
```

看到 `数据库表创建完成！` 就成功了。

### 第五步：访问

打开浏览器访问：**http://localhost:8000**

### 常用 Docker 命令

```bash
# 查看运行状态
docker compose ps

# 查看实时日志
docker compose logs -f app

# 停止服务
docker compose down

# 停止并删除数据库数据（慎用！会清空所有数据）
docker compose down -v

# 重新构建并启动（代码更新后执行）
docker compose up -d --build

# 进入应用容器内部（调试用）
docker exec -it xiaozhi-app bash
```

### 代码更新后如何部署？

```bash
# 拉取最新代码
git pull

# 重新构建并重启
docker compose up -d --build
```

---

## 使用指南

### 1. 注册和登录

1. 打开 http://localhost:8000
2. 点击「注册」标签，填写用户名、邮箱、密码
3. 注册后自动跳转到登录页面，使用刚注册的账号登录

### 2. 创建项目

1. 登录后点击「新建项目」
2. 填写项目信息：
   - **项目名称**：随便起，如"卧室灯光控制"
   - **MCP 接入点**：从 xiaozhi.me 控制台获取（见下方说明）
   - **MQTT 服务器**：你的 MQTT Broker 地址，如 `broker.emqx.io`
   - **MQTT 端口**：默认 `1883`
   - **MQTT 用户名/密码**：如果 Broker 需要认证就填，否则留空

#### 如何获取 MCP 接入点？

1. 登录 [xiaozhi.me](https://xiaozhi.me) 控制台
2. 进入你的智能体配置页面
3. 在右下角找到「MCP 接入点」，复制那个 WebSocket 地址（以 `wss://` 开头）

### 3. 添加工具

进入项目详情，切换到「工具管理」标签，点击「添加工具」。

**工具类型说明：**

| 类型 | 用途 | 举例 |
|------|------|------|
| MQTT 发送命令 | 发送 MQTT 消息到设备 | 开灯、关灯、调亮度 |
| MQTT 读取数据 | 读取设备上报的数据 | 查看温度、湿度 |
| HTTP 调用接口 | 调用外部 HTTP API | 控制空调、查询天气 |

**以"控制灯光"为例：**

1. 工具名称填 `control_light`
2. 工具类型选「MQTT 发送命令」
3. 工具描述填 `控制卧室灯光的开关`（AI 会根据这个描述决定何时调用）
4. 发布主题填 `device/light/control`（你的设备订阅的 MQTT 主题）
5. 添加命令选项：
   - `on` → 开灯
   - `off` → 关灯
   - `toggle` → 切换灯光
6. 点击保存

### 4. 启动项目

1. 切换到「项目配置」标签，确认配置无误
2. 点击右上角的「启动」按钮
3. 切换到「实时日志」标签，查看连接状态

看到 `MCP WebSocket连接成功` 说明已经和小智 AI 连接上了。

### 5. 语音测试

对着你的小智设备说：

- "帮我把灯打开" → 系统发送 `on`
- "关灯" → 系统发送 `off`
- "看看温度多少" → 系统返回传感器数据

## 项目结构

```
ai-xiaozhi-mcp/
├── .dockerignore           # Docker 构建忽略规则
├── .env.example            # 环境变量模板
├── .gitignore              # Git 忽略规则
├── Dockerfile              # Docker 镜像构建文件
├── docker-compose.yml      # Docker 一键部署配置
├── install.sh              # Ubuntu 一键安装脚本
├── requirements.txt        # Python 依赖清单
├── run.py                  # 启动入口
├── init_db.py              # 数据库初始化脚本
└── app/
    ├── main.py             # FastAPI 主应用
    ├── config.py           # 配置管理（读取 .env）
    ├── database.py         # 数据库连接
    ├── models.py           # 数据模型（4张表）
    ├── schemas.py          # 请求/响应数据结构
    ├── auth.py             # JWT 认证
    ├── routers/
    │   ├── auth.py         # 用户注册/登录 API
    │   ├── projects.py     # 项目管理 API + WebSocket 日志
    │   └── tools.py        # 工具管理 API
    ├── services/
    │   ├── log_service.py  # 实时日志广播
    │   ├── mqtt_manager.py # MQTT 客户端管理
    │   └── mcp_manager.py  # MCP WebSocket 连接管理
    └── static/
        └── index.html      # 前端页面
```

## API 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 用户登录 |
| GET | `/api/auth/me` | 获取当前用户信息 |
| GET | `/api/projects` | 获取项目列表 |
| POST | `/api/projects` | 创建项目 |
| GET | `/api/projects/{id}` | 获取项目详情 |
| PUT | `/api/projects/{id}` | 更新项目 |
| DELETE | `/api/projects/{id}` | 删除项目 |
| POST | `/api/projects/{id}/start` | 启动项目 |
| POST | `/api/projects/{id}/stop` | 停止项目 |
| POST | `/api/projects/{id}/restart` | 重启项目 |
| WS | `/api/projects/{id}/logs` | 实时日志（WebSocket） |
| GET | `/api/projects/{id}/tools` | 获取工具列表 |
| POST | `/api/projects/{id}/tools` | 创建工具 |
| PUT | `/api/projects/{id}/tools/{id}` | 更新工具 |
| DELETE | `/api/projects/{id}/tools/{id}` | 删除工具 |

## 常见问题

### Q: 启动时报错 `ModuleNotFoundError: No module named 'xxx'`

说明依赖没装全，重新执行：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q: 启动时报错 `Can't connect to MySQL server`

1. 确认 MySQL 服务已启动
2. 确认 `.env` 中的数据库密码正确
3. 确认数据库 `xiaozhi_mcp` 已创建

### Q: 启动项目后小智没有反应

1. 检查「实时日志」中是否有 `MCP WebSocket连接成功`
2. 确认 MCP 接入点地址正确（以 `wss://` 开头）
3. 确认工具描述写得清楚，AI 需要根据描述判断何时调用

### Q: MQTT 消息发送失败

1. 检查 MQTT 服务器地址和端口是否正确
2. 如果需要认证，确认用户名和密码正确
3. 在实时日志中查看具体错误信息

### Q: 如何修改服务端口？

编辑 `run.py` 文件，修改 `port=8000` 为你想要的端口号。

### Q: 如何在服务器上长期运行？

推荐使用 `systemd`（Linux）或 `NSSM`（Windows）将服务注册为系统服务。也可以使用 `screen` 或 `tmux`：

```bash
# Linux
screen -S xiaozhi-mcp
python run.py
# 按 Ctrl+A, D 断开会话
```

## 开发说明

本项目使用了小智 AI 的 MCP（Model Context Protocol）协议，基于 JSON-RPC 2.0 格式通过 WebSocket 通信。

**MCP 工作流程：**

1. 本系统连接到小智提供的 MCP 接入点（WebSocket）
2. 小智发送 `initialize` 握手请求
3. 小智发送 `tools/list` 获取可用工具列表
4. 用户对小智说话，大模型决定调用哪个工具
5. 小智发送 `tools/call` 请求，携带工具名和参数
6. 本系统执行对应操作（发 MQTT / 调 HTTP），返回结果
7. 小智根据结果回复用户

## 许可证

MIT License
