#!/usr/bin/env bash
# ============================================================================
# 数据库恢复脚本
# 从 backups/ 目录恢复最新的或指定的备份文件到 MySQL 数据库
#
# 用法：
#   ./restore_db.sh              # 恢复最新的一份备份
#   ./restore_db.sh <file>       # 恢复指定备份文件（支持绝对路径或相对 backups 目录的文件名）
#
# 可用环境变量：
#   DB_NAME          数据库名（默认 xiaozhi_mcp，容器内会由 MYSQL_DATABASE 注入）
#   MYSQL_HOST       数据库主机（默认 localhost）
#   MYSQL_USER       数据库用户名（默认 root）
#   MYSQL_PASSWORD   数据库密码（默认空）
#   SKIP_CONFIRM     设为 1 跳过交互确认（便于自动化）
# ============================================================================
set -euo pipefail

# ========== 配置（从环境变量读取，带默认值） ==========
# 数据库名：优先 DB_NAME，其次 MYSQL_DATABASE，默认 xiaozhi_mcp
DB_NAME="${DB_NAME:-${MYSQL_DATABASE:-xiaozhi_mcp}}"
# 数据库主机
MYSQL_HOST="${MYSQL_HOST:-localhost}"
# 数据库用户名
MYSQL_USER="${MYSQL_USER:-root}"
# 数据库密码（可为空）
MYSQL_PASSWORD="${MYSQL_PASSWORD:-}"

# 脚本与备份目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_DIR="${PROJECT_ROOT}/backups"

# ========== 前置检查 ==========
# 检查 mysql 客户端是否存在
if ! command -v mysql >/dev/null 2>&1; then
  echo "[错误] 未找到 mysql 命令，请先安装 mysql-client。" >&2
  exit 1
fi

# ========== 确定要恢复的备份文件 ==========
if [[ $# -ge 1 ]]; then
  # 指定文件：优先按原路径，找不到则尝试相对 backups 目录
  RESTORE_FILE="$1"
  if [[ ! -f "${RESTORE_FILE}" ]]; then
    RESTORE_FILE="${BACKUP_DIR}/$1"
  fi
else
  # 未指定：选取 backups 目录中最新的 .sql 备份文件
  RESTORE_FILE="$(ls -t "${BACKUP_DIR}"/*.sql 2>/dev/null | head -n 1 || true)"
  if [[ -z "${RESTORE_FILE}" ]]; then
    echo "[错误] 在 ${BACKUP_DIR} 中未找到任何 .sql 备份文件。" >&2
    exit 1
  fi
fi

# 校验文件存在且非空
if [[ ! -f "${RESTORE_FILE}" ]]; then
  echo "[错误] 备份文件不存在：${RESTORE_FILE}" >&2
  exit 1
fi
if [[ ! -s "${RESTORE_FILE}" ]]; then
  echo "[错误] 备份文件为空：${RESTORE_FILE}" >&2
  exit 1
fi

# ========== 构造 mysql 连接参数 ==========
MYSQL_OPTS=(-h "${MYSQL_HOST}" -u "${MYSQL_USER}")
if [[ -n "${MYSQL_PASSWORD}" ]]; then
  MYSQL_OPTS+=("-p${MYSQL_PASSWORD}")
fi

# ========== 交互确认（恢复会覆盖现有数据） ==========
echo "[警告] 即将把 ${RESTORE_FILE} 恢复到数据库 ${DB_NAME}@${MYSQL_HOST}！"
echo "[警告] 该操作将覆盖目标数据库中的现有数据。"
if [[ "${SKIP_CONFIRM:-0}" != "1" ]]; then
  read -r -p "确认继续？(输入 yes 继续)：" CONFIRM
  if [[ "${CONFIRM}" != "yes" ]]; then
    echo "[信息] 已取消恢复。"
    exit 0
  fi
fi

# ========== 执行恢复 ==========
echo "[信息] 开始恢复..."
mysql "${MYSQL_OPTS[@]}" "${DB_NAME}" < "${RESTORE_FILE}"

echo "[信息] 恢复完成：${RESTORE_FILE} -> ${DB_NAME}@${MYSQL_HOST}"
