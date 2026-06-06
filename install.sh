#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

REPO_URL="https://gitee.com/T510/ai-xiaozhi-mcp.git"
INSTALL_DIR="$HOME/ai-xiaozhi-mcp"
MYSQL_ROOT_PASSWORD="xiaozhi_$(openssl rand -hex 6 2>/dev/null || echo 'mcp2024secure')"
DB_NAME="xiaozhi_mcp"
DB_USER="root"
SECRET_KEY="$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | base64 | tr -d '\n/+=' | head -c 48)"

info()  { echo -e "${BLUE}[信息]${NC} $1"; }
ok()    { echo -e "${GREEN}[成功]${NC} $1"; }
warn()  { echo -e "${YELLOW}[注意]${NC} $1"; }
error() { echo -e "${RED}[错误]${NC} $1"; }

check_root() {
    if [ "$(id -u)" -eq 0 ]; then
        warn "检测到以 root 用户运行，建议使用普通用户"
        read -p "是否继续？(y/n): " choice </dev/tty
        if [ "$choice" != "y" ] && [ "$choice" != "Y" ]; then
            exit 0
        fi
    fi
}

check_os() {
    if [ ! -f /etc/os-release ]; then
        error "无法检测操作系统"
        exit 1
    fi
    . /etc/os-release
    info "检测到系统: $PRETTY_NAME"
}

install_system_deps() {
    info "更新软件源..."
    sudo apt-get update -qq

    local packages="git curl wget software-properties-common"
    local missing=""
    for pkg in $packages; do
        if ! dpkg -l | grep -q "^ii  $pkg "; then
            missing="$missing $pkg"
        fi
    done

    if [ -n "$missing" ]; then
        info "安装系统依赖:$missing"
        sudo apt-get install -y -qq $missing
        ok "系统依赖安装完成"
    else
        ok "系统依赖已就绪"
    fi
}

install_python() {
    if command -v python3 &>/dev/null; then
        local py_ver=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        local major=$(echo "$py_ver" | cut -d. -f1)
        local minor=$(echo "$py_ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 9 ]; then
            ok "Python $py_ver 已安装"
            return
        else
            warn "Python $py_ver 版本过低，需要 3.9+"
        fi
    fi

    info "安装 Python 3.11..."
    sudo add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3.11 python3.11-venv python3.11-dev python3-pip

    if command -v python3.11 &>/dev/null; then
        ok "Python 3.11 安装完成"
    else
        error "Python 安装失败，请手动安装 Python 3.9+"
        exit 1
    fi
}

get_python_cmd() {
    if command -v python3.11 &>/dev/null; then
        echo "python3.11"
    elif command -v python3 &>/dev/null; then
        echo "python3"
    else
        echo "python"
    fi
}

install_mysql() {
    if command -v mysql &>/dev/null; then
        local ver=$(mysql --version | grep -oP '\d+\.\d+\.\d+')
        ok "MySQL $ver 已安装"

        if systemctl is-active --quiet mysql 2>/dev/null || systemctl is-active --quiet mysqld 2>/dev/null; then
            ok "MySQL 服务正在运行"
        else
            info "启动 MySQL 服务..."
            sudo systemctl start mysql 2>/dev/null || sudo systemctl start mysqld 2>/dev/null || sudo service mysql start
            ok "MySQL 服务已启动"
        fi
        return
    fi

    info "安装 MySQL Server..."
    sudo apt-get install -y -qq mysql-server

    info "启动 MySQL 服务..."
    sudo systemctl start mysql
    sudo systemctl enable mysql

    ok "MySQL 安装完成"
}

setup_mysql() {
    info "配置 MySQL 数据库..."

    if sudo mysql -u root -e "SELECT 1" &>/dev/null; then
        sudo mysql -u root <<EOF
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '$MYSQL_ROOT_PASSWORD';
FLUSH PRIVILEGES;
CREATE DATABASE IF NOT EXISTS $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON $DB_NAME.* TO 'root'@'localhost';
FLUSH PRIVILEGES;
EOF
    elif mysql -u root -p"$MYSQL_ROOT_PASSWORD" -e "SELECT 1" &>/dev/null; then
        mysql -u root -p"$MYSQL_ROOT_PASSWORD" <<EOF
CREATE DATABASE IF NOT EXISTS $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON $DB_NAME.* TO 'root'@'localhost';
FLUSH PRIVILEGES;
EOF
        ok "数据库已存在，已复用"
        return
    else
        error "MySQL 无法连接，请手动检查 MySQL 配置"
        exit 1
    fi

    ok "数据库 $DB_NAME 创建完成"
}

clone_repo() {
    if [ -d "$INSTALL_DIR/.git" ]; then
        info "项目目录已存在，更新代码..."
        cd "$INSTALL_DIR"
        git pull --quiet
        ok "代码更新完成"
    else
        info "克隆项目代码..."
        git clone --quiet "$REPO_URL" "$INSTALL_DIR"
        ok "代码克隆完成"
    fi
    cd "$INSTALL_DIR"
}

setup_venv() {
    local python_cmd=$(get_python_cmd)

    if [ -d "$INSTALL_DIR/venv" ] && [ -f "$INSTALL_DIR/venv/bin/activate" ]; then
        ok "虚拟环境已存在"
        source "$INSTALL_DIR/venv/bin/activate"
        return
    fi

    info "创建 Python 虚拟环境..."
    $python_cmd -m venv "$INSTALL_DIR/venv"
    source "$INSTALL_DIR/venv/bin/activate"
    ok "虚拟环境创建完成"
}

install_pip_deps() {
    info "安装 Python 依赖（首次可能较慢）..."
    pip install --upgrade pip -q 2>/dev/null
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple -q
    ok "Python 依赖安装完成"
}

create_env() {
    if [ -f "$INSTALL_DIR/.env" ]; then
        warn ".env 文件已存在，跳过生成"
        MYSQL_ROOT_PASSWORD=$(grep DATABASE_URL "$INSTALL_DIR/.env" | sed 's/.*:([^@]*)@.*/\1/' | grep -oP '(?<=:)[^@]+(?=@)' || echo "$MYSQL_ROOT_PASSWORD")
        return
    fi

    info "生成配置文件..."
    cat > "$INSTALL_DIR/.env" <<EOF
DATABASE_URL=mysql+pymysql://$DB_USER:$MYSQL_ROOT_PASSWORD@localhost:3306/$DB_NAME
SECRET_KEY=$SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES=1440
EOF

    ok ".env 配置文件已生成"
}

init_database() {
    info "初始化数据库表..."
    cd "$INSTALL_DIR"
    source venv/bin/activate
    python init_db.py
    ok "数据库表初始化完成"
}

create_systemd_service() {
    local python_cmd="$INSTALL_DIR/venv/bin/python"

    info "创建系统服务（开机自启）..."
    sudo tee /etc/systemd/system/xiaozhi-mcp.service > /dev/null <<EOF
[Unit]
Description=XiaoZhi MCP-MQTT Management System
After=network.target mysql.service

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$INSTALL_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$python_cmd -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable xiaozhi-mcp
    sudo systemctl start xiaozhi-mcp

    ok "系统服务创建完成，已设置开机自启"
}

print_summary() {
    local ip=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "your-server-ip")

    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}    安装完成！${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    echo -e "  访问地址:  ${BLUE}http://$ip:8000${NC}"
    echo ""
    echo -e "  项目目录:  $INSTALL_DIR"
    echo -e "  数据库密码: ${YELLOW}$MYSQL_ROOT_PASSWORD${NC}"
    echo -e "  服务状态:  ${GREEN}$(systemctl is-active xiaozhi-mcp 2>/dev/null || echo 'running')${NC}"
    echo ""
    echo -e "  ${BLUE}常用命令:${NC}"
    echo -e "    查看状态:  sudo systemctl status xiaozhi-mcp"
    echo -e "    查看日志:  sudo journalctl -u xiaozhi-mcp -f"
    echo -e "    重启服务:  sudo systemctl restart xiaozhi-mcp"
    echo -e "    停止服务:  sudo systemctl stop xiaozhi-mcp"
    echo ""
    echo -e "  ${YELLOW}请保存好数据库密码，后续可能需要用到${NC}"
    echo ""
}

main() {
    echo ""
    echo -e "${BLUE}  ╔══════════════════════════════════════╗${NC}"
    echo -e "${BLUE}  ║  小智 MCP-MQTT 管理系统 一键安装    ║${NC}"
    echo -e "${BLUE}  ╚══════════════════════════════════════╝${NC}"
    echo ""

    check_root
    check_os

    echo ""
    info "即将开始安装，整个过程大约需要 3-5 分钟"
    read -p "按回车键开始安装，或按 Ctrl+C 取消..." _ </dev/tty
    echo ""

    install_system_deps
    install_python
    install_mysql
    setup_mysql
    clone_repo
    setup_venv
    install_pip_deps
    create_env
    init_database
    create_systemd_service

    print_summary
}

main "$@"
