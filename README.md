<p align="center">
  <h1 align="center">🤖 小智 MCP-MQTT 管理平台</h1>
  <p align="center">
    <em>让 AI 听懂你的话，控制你的智能设备</em>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
    <img src="https://img.shields.io/badge/MQTT-Paho-orange?style=flat-square&logo=mqtt&logoColor=white" alt="MQTT">
    <img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License">
    <img src="https://img.shields.io/badge/Status-Active-green?style=flat-square" alt="Status">
  </p>
</p>

---

## 📖 这是什么？

想象一下：你对小智说一句"帮我把卧室灯打开"，灯就真的亮了。

这不是魔法，而是 **MCP-MQTT 管理平台** 做的事情。它是一座桥梁，连接了 AI 大模型和你家里的智能设备。

**核心思路**：你说的话 → 小智 AI 理解 → 通过 MQTT 告诉设备 → 设备执行

```mermaid
graph LR
    A[🗣️ 你的语音] --> B[🤖 小智 AI]
    B --> C[🔌 MCP 协议]
    C --> D[🖥️ 本平台]
    D --> E[📡 MQTT/HTTP]
    E --> F[💡 智能设备]
```

---

## ✨ 为什么选它？

| 特性 | 说明 |
|------|------|
| 🗣️ **说人话就行** | 不用写代码，直接用自然语言控制设备 |
| 🔄 **双向沟通** | 不仅能控制，还能查询设备状态（比如"现在室温多少？"）|
| 🔌 **多协议支持** | MQTT、HTTP 都能用，兼容主流智能家居生态 |
| 🏠 **多项目隔离** | 一个账号管理多个空间，互不干扰 |
| 📊 **实时日志** | 每一步操作都看得见，出问题一目了然 |

---

## 🚀 三分钟快速上手

### 方式一：Docker 一键部署（推荐）

```bash
# 1. 克隆代码
git clone https://gitee.com/T510/ai-xiaozhi-mcp.git
cd ai-xiaozhi-mcp

# 2. 启动
docker compose up -d

# 3. 初始化数据库
docker exec xiaozhi-app python init_db.py

# 4. 打开浏览器访问
# http://localhost:8000
```

就这么简单！

### 方式二：Ubuntu 一键脚本

```bash
curl -fsSL https://gitee.com/T510/ai-xiaozhi-mcp/raw/master/install.sh | bash
```

脚本会自动搞定一切，安装完成后会告诉你访问地址和初始密码。

### 方式三：源码部署（开发者）

```bash
git clone https://gitee.com/T510/ai-xiaozhi-mcp.git
cd ai-xiaozhi-mcp
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
cp .env.example .env  # 编辑 .env 填入数据库配置
python init_db.py
python run.py
```

---

## 📋 使用指南

### 1️⃣ 注册登录

打开浏览器，访问你的部署地址，注册一个账号。

### 2️⃣ 创建项目

进入工作台，点击「新建项目」，填写：
- **项目名称**：随便起，比如"我的卧室"
- **MCP 接入点**：去 [小智开发者控制台](https://xiaozhi.me) 找到你的智能体，复制 WebSocket 地址
- **MQTT 配置**：填入你的 MQTT Broker 地址、端口、用户名和密码

### 3️⃣ 添加设备工具

切换到「工具管理」，添加你要控制的设备：

| 工具类型 | 用途 | 例子 |
|----------|------|------|
| MQTT 发送 | 控制设备 | 开灯、关空调 |
| MQTT 读取 | 查询状态 | 温度、湿度 |
| HTTP 调用 | 对接其他系统 | Home Assistant |

**配置小贴士**：
- 「工具标识」用英文，比如 `control_light`
- 「功能描述」要写清楚人话，AI 靠这个理解你想干嘛，比如"控制卧室灯光的开关"

### 4️⃣ 启动测试

在项目页面点击「启动」，切换到「实时日志」看看有没有显示「MCP WebSocket 连接成功」。成功了就对着小智说句话试试！

---

## 💬 交互示例

```
你：小智，帮我把卧室的灯打开
小智：好的，卧室灯已打开。
    ↓
（后台：control_light 工具被触发 → MQTT 发送 "on" → 灯亮了）
```

---

## 🛠️ 常见问题

<details>
<summary><b>❌ 启动报 ModuleNotFoundError</b></summary>

Python 环境没激活或者依赖没装全。确保激活了虚拟环境，然后：
```bash
pip install -r requirements.txt
```
</details>

<details>
<summary><b>❌ 连不上 MySQL 数据库</b></summary>

检查这几项：
1. MySQL 服务有没有启动？
2. `.env` 文件里的数据库用户名、密码、端口对不对？
3. 数据库 `xiaozhi_mcp` 有没有创建？
</details>

<details>
<summary><b>❌ 连接成功了但小智没反应</b></summary>

大概率是「工具描述」写得不清楚。AI 靠描述来理解意图，写得越清楚越好。比如：
- ❌ "灯"（太模糊）
- ✅ "控制卧室主灯的开关，on=开灯，off=关灯"
</details>

<details>
<summary><b>❌ 想改端口号</b></summary>

- 源码部署：编辑 `run.py`，改 `port=8000` 里的数字
- Docker 部署：编辑 `docker-compose.yml`，改 `ports: - "8000:8000"` 前面的数字
</details>

---

## 📡 API 接口

提供标准 RESTful API，方便集成：

### 认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录 |
| GET | `/api/auth/me` | 获取当前用户 |

### 项目管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects` | 项目列表 |
| POST | `/api/projects` | 创建项目 |
| PUT | `/api/projects/{id}` | 更新项目 |
| DELETE | `/api/projects/{id}` | 删除项目 |
| POST | `/api/projects/{id}/start` | 启动连接 |
| POST | `/api/projects/{id}/stop` | 停止连接 |
| WS | `/api/projects/{id}/logs` | 实时日志 |

### 工具管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects/{id}/tools` | 工具列表 |
| POST | `/api/projects/{id}/tools` | 添加工具 |
| PUT | `/api/projects/{id}/tools/{id}` | 更新工具 |
| DELETE | `/api/projects/{id}/tools/{id}` | 删除工具 |

---

## 📁 项目结构

```
ai-xiaozhi-mcp/
├── app/                    # 核心代码
│   ├── routers/            # API 路由
│   ├── services/           # 业务逻辑（MQTT、MCP、日志）
│   ├── models.py           # 数据库模型
│   ├── schemas.py          # 数据校验
│   └── static/             # 前端页面
├── .env.example            # 环境变量模板
├── docker-compose.yml      # Docker 配置
├── Dockerfile              # 镜像构建
├── install.sh              # 一键安装脚本
├── init_db.py              # 数据库初始化
└── run.py                  # 启动入口
```

---

## 📄 许可证

[MIT License](LICENSE) - 随便用，随便改。

---

<p align="center">
  <em>如果觉得有用，给个 ⭐ Star 支持一下吧！</em>
</p>
