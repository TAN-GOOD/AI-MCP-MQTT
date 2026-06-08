# 小智 MCP-MQTT 管理平台

基于 MCP (Model Context Protocol) 协议的物联网设备一站式 AI 语音控制解决方案。

本系统旨在通过**零代码、可视化**的配置方式，将传统 IoT 设备（如照明、温控、传感器等）无缝接入小智 AI。无需复杂的编程开发，即可实现基于自然语言的智能设备控制与状态监测。

---

## 核心特性

* **自然语言驱动**：向小智下发指令（如“打开卧室主灯”），系统将自动解析语义并转化为设备控制信号。
* **双向数据交互**：不仅支持控制设备，还支持反向查询传感器数据（如“查看当前室内温湿度”）。
* **多协议扩展能力**：原生支持 MQTT 消息发布与订阅，并提供 HTTP 接口调用功能，轻松兼容各类主流智能家居生态。
* **多租户与项目隔离**：单账号支持创建多个独立项目，实现不同物理空间或网络环境下的设备逻辑隔离。
* **全链路可视化日志**：内置实时操作日志面板，MCP 握手、工具调用与 MQTT 消息流转状态一目了然，极大降低排障门槛。

## 交互演示

```text
用户：小智，帮我把卧室的灯打开。
小智：好的，卧室灯已打开。
（系统底层处理：小智 AI 触发 `control_light` 工具 -> 系统自动向设备对应的 MQTT 主题发送 "on" 指令）

```

## 技术架构

整个系统的数据流转链路如下：

```text
用户语音指令 → 小智 AI 大模型 → MCP 协议 (WebSocket) → 本系统平台 → MQTT/HTTP 协议 → IoT 物理设备

```

* **后端支撑**：Python 3.11 + FastAPI + SQLAlchemy + paho-mqtt
* **前端呈现**：原生单页应用 (SPA)，采用 Linear 极简暗色主题
* **数据存储**：MySQL 关系型数据库
* **通信协议**：MCP (JSON-RPC 2.0 over WebSocket)

---

## 部署指南

为满足不同环境的运维需求，本系统提供三种部署途径。请根据您的实际服务器环境选择最合适的方式：

| 方案 | 适用场景 | 复杂度 | 核心优势 |
| --- | --- | --- | --- |
| **[Ubuntu 一键脚本]** | 全新的 Ubuntu 服务器 | ⭐ | 自动化程度高，自动配置环境与开机自启 |
| **[Docker 容器化部署]** | 任何已安装 Docker 的系统 | ⭐⭐ | 环境隔离性好，不污染宿主机，便于平滑升级 |
| **[源码手动构建]** | Windows/Mac/Linux 本地开发 | ⭐⭐⭐ | 适合需要二次开发、定制化修改的开发者 |

### 前置环境要求

若选择**源码手动部署**，请确保宿主机已安装以下组件：

* **Python 3.9+**（推荐 3.11）
* **MySQL 5.7+**
* **Git**

> **注**：若您的系统已部署 Anaconda/Miniconda，可直接复用其内置的 Python 环境。

---

### 一、 Ubuntu 一键安装（极简模式）

在终端中执行以下一键构建脚本，系统将自动完成依赖安装、数据库初始化及服务注册：

```bash
curl -fsSL https://gitee.com/T510/ai-xiaozhi-mcp/raw/master/install.sh | bash

```

**脚本自动执行流程包含**：

1. 环境检测与 Python 3.11、MySQL 安装。
2. 自动生成数据库及授权用户。
3. 代码克隆至 `~/ai-xiaozhi-mcp` 并构建 Python 虚拟环境。
4. 环境变量生成与数据库表结构初始化。
5. 注册 Systemd 守护进程以实现开机自启。

安装完毕后，终端将输出平台的访问地址及数据库初始凭证，请妥善留存。

---

### 二、 Docker 部署（官方推荐）

通过容器化技术，您可以免去繁琐的环境配置过程。请确保宿主机已正确安装 Docker 引擎及 Docker Compose。

**1. 获取源码**

```bash
git clone https://gitee.com/T510/ai-xiaozhi-mcp.git
cd ai-xiaozhi-mcp

```

**2. 调整配置（可选）**
如需修改默认安全策略，请编辑 `docker-compose.yml` 文件，更新数据库凭证与 JWT 密钥：

```yaml
# 请确保 MYSQL_ROOT_PASSWORD 与 DATABASE_URL 中的密码保持一致
MYSQL_ROOT_PASSWORD: your_secure_password
DATABASE_URL: mysql+pymysql://root:your_secure_password@db:3306/xiaozhi_mcp
SECRET_KEY: replace_with_your_random_secret_string

```

**3. 启动容器集群**

```bash
docker compose up -d

```

*(首次启动需拉取基础镜像，耗时视网络环境而定)*

**4. 初始化数据表**
容器正常运行后，执行以下命令完成数据库结构初始化：

```bash
docker exec xiaozhi-app python init_db.py

```

当控制台输出 `数据库表创建完成！`，即可通过浏览器访问：**http://localhost:8000**

**常用运维命令：**

* 查看服务状态：`docker compose ps`
* 追踪实时日志：`docker compose logs -f app`
* 平滑更新版本：`git pull && docker compose up -d --build`

---

### 三、 源码手动部署（开发者模式）

**1. 代码克隆与环境隔离**

```bash
git clone https://gitee.com/T510/ai-xiaozhi-mcp.git
cd ai-xiaozhi-mcp

# 创建并激活虚拟环境 (以 venv 为例)
python -m venv venv
source venv/bin/activate  # Windows 用户请执行 venv\Scripts\activate

```

**2. 安装依赖库**

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

```

**3. 配置数据库与环境变量**
在您的数据库管理工具中执行：`CREATE DATABASE xiaozhi_mcp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;`

随后复制配置文件模板并进行修改：

```bash
cp .env.example .env  # Windows 请使用 copy 命令

```

编辑 `.env` 文件，填入实际的 `DATABASE_URL` 与自定义的 `SECRET_KEY`。

**4. 初始化与启动**

```bash
python init_db.py
python run.py

```

服务默认监听 `[http://0.0.0.0:8000](http://0.0.0.0:8000)`。

---

## 操作手册

### 1. 账号体系

访问平台首页，完成账号注册并登录。首次使用需创建管理员账号。

### 2. 项目构建与 MCP 接入

1. 进入工作台，点击「新建项目」。
2. 填写核心通信参数：
* **项目名称**：自定义（如：家庭主网控）。
* **MCP 接入点**：登录 [小智开发者控制台 (xiaozhi.me)](https://xiaozhi.me)，在对应智能体的配置面板右下角提取 WebSocket 地址（`wss://...`）。
* **MQTT 代理配置**：填入您的 Broker 地址（如 `broker.emqx.io`）、端口及鉴权信息。



### 3. 定义设备工具

在项目详情页切换至「工具管理」进行挂载。支持以下三种模式：

| 工具类型 | 业务场景 | 配置示例 |
| --- | --- | --- |
| **MQTT 发送命令** | 状态控制 | 发送 `on`/`off` 报文以开关照明设备 |
| **MQTT 读取数据** | 状态采集 | 订阅温湿度传感器定时上报的 Topic |
| **HTTP 调用接口** | 外部网关对接 | 触发局域网内其他智能中枢（如 Home Assistant）的 Webhook |

**配置实战（以开关灯为例）：**

* **工具标识**：`control_light`
* **功能描述**：`控制卧室灯光的开关` *(注：大模型将依据此描述进行意图推断，请尽量准确)*
* **交互逻辑**：绑定目标 Topic 并定义有效 Payload（如 `on` -> 开灯）。

### 4. 链路激活与验证

1. 在「项目配置」**页右上角点击**「启动」。
2. 切换至「实时日志」，观察握手状态。出现 `MCP WebSocket 连接成功` 即表明系统已打通小智 AI。
3. 直接向小智设备发起语音测试。

---

## 常见问题 (FAQ)

**Q: 启动服务时抛出 `ModuleNotFoundError` 异常？**
A: 核心依赖缺失。请确保已激活正确的 Python 虚拟环境，并重新执行 `pip install -r requirements.txt`。

**Q: 无法连接至 MySQL 数据库？**
A: 请按顺序排查：1. MySQL 服务是否正常运行；2. `.env` 文件中的用户名、密码及端口是否准确无误；3. 目标数据库 `xiaozhi_mcp` 是否已手动建立。

**Q: 系统已显示连接成功，但小智对指令无响应？**
A: 通常由大模型意图识别偏差导致。请重点检查「工具描述」字段，确保使用清晰、无歧义的自然语言描述该工具的作用边界。

**Q: 如何更改 Web 服务的监听端口？**
A: 源码部署用户请直接编辑 `run.py`，修改 `port=8000` 为目标端口；Docker 用户请修改 `docker-compose.yml` 中的端口映射规则 `ports: - "8000:8000"`。

---

## API 参考

为方便系统集成，本平台对外暴露标准的 RESTful API 接口：

### 认证与账号

* `POST /api/auth/register` - 用户注册
* `POST /api/auth/login` - 换取访问凭证 (Token)
* `GET /api/auth/me` - 获取当前会话状态

### 项目生命周期管理

* `GET/POST /api/projects` - 查询项目列表 / 创建工程
* `PUT/DELETE /api/projects/{id}` - 更新配置 / 销毁项目
* `POST /api/projects/{id}/start` - 激活 MCP 连接
* `POST /api/projects/{id}/stop` - 中断通信链路
* `WS /api/projects/{id}/logs` - 建立实时日志监控通道 (WebSocket)

### 工具链路管理

* `GET/POST /api/projects/{id}/tools` - 工具集查询与新建
* `PUT/DELETE /api/projects/{id}/tools/{id}` - 工具规则更新与解绑

---

## 项目结构

```text
ai-xiaozhi-mcp/
├── app/                    # 核心业务逻辑
│   ├── routers/            # 路由控制器 (Auth, Projects, Tools)
│   ├── services/           # 底层服务层 (MQTT, MCP 握手, 日志广播)
│   ├── models.py           # ORM 数据实体映射
│   ├── schemas.py          # Pydantic 数据校验模型
│   └── static/             # Web 视图层资源
├── .env.example            # 环境变量配置参照
├── docker-compose.yml      # 容器编排清单
├── Dockerfile              # 应用镜像构建脚本
├── install.sh              # 自动化构建脚本
├── init_db.py              # 数据库迁移器
└── run.py                  # ASGI 服务引导入口

```

## 许可证

本项目基于 [MIT License］ 开源发布。保留所有权利。
