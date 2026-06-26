#!/usr/bin/env bash
# ============================================================================
# 数据库备份脚本
# 使用 mysqldump 备份 MySQL 数据库，备份文件按日期时间命名存到 backups/ 目录
# 保留最近 N 天的备份，超出保留期的旧备份自动清理
#
# 用法：
#   ./backup_db.sh              # 使用默认保留天数（7 天）
#   ./backup_db.sh 14           # 指定保留 14 天
#   KEEP_DAYS=30 ./backup_db.sh # 通过环境变量指定保留 30 天
#
# 可用环境变量：
#   DB_NAME          数据库名（默认 xiaozhi_mcp，容器内会由 MYSQL_DATABASE 注入）
#   MYSQL_HOST       数据库主机（默认 localhost）
#   MYSQL_USER       数据库用户名（默认 root）
#   MYSQL_PASSWORD   数据库密码（默认空）
#   KEEP_DAYS        保留天数（默认 7）
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

# 脚本所在目录（用于定位 backups 目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 项目根目录（scripts 的上一级）
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# 备份目录
BACKUP_DIR="${PROJECT_ROOT}/backups"

# 默认保留天数
DEFAULT_KEEP_DAYS=7
# 保留天数：优先取第一个参数，其次 KEEP_DAYS 环境变量，最后默认值
KEEP_DAYS="${1:-${KEEP_DAYS:-$DEFAULT_KEEP_DAYS}}"

# ========== 前置检查 ==========
# 检查 mysqldump 是否存在
if ! command -v mysqldump >/dev/null 2>&1; then
  echo "[错误] 未找到 mysqldump 命令，请先安装 mysql-client。" >&2
  exit 1
fi

# 校验保留天数为非负整数
if ! [[ "${KEEP_DAYS}" =~ ^[0-9]+$ ]]; then
  echo "[错误] 保留天数必须是非负整数，当前输入：${KEEP_DAYS}" >&2
  exit 1
fi

# 创建备份目录（如不存在）
mkdir -p "${BACKUP_DIR}"

# ========== 构造 mysqldump 连接参数 ==========
MYSQL_OPTS=(-h "${MYSQL_HOST}" -u "${MYSQL_USER}")
if [[ -n "${MYSQL_PASSWORD}" ]]; then
  MYSQL_OPTS+=("-p${MYSQL_PASSWORD}")
fi

# 备份文件名：数据库名_年月日_时分秒.sql
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_$(date +%Y%m%d_%H%M%S).sql"

echo "[信息] 开始备份数据库 ${DB_NAME}@${MYSQL_HOST} -> ${BACKUP_FILE}"

# 执行备份：
#   --single-transaction  InnoDB 一致性快照，不锁表
#   --quick               流式输出，避免大表占满内存
#   --routines            包含存储过程/函数
#   --triggers            包含触发器
#   --events              包含事件
mysqldump "${MYSQL_OPTS[@]}" \
  --single-transaction \
  --quick \
  --routines \
  --triggers \
  --events \
  "${DB_NAME}" > "${BACKUP_FILE}"

# 校验备份文件非空
if [[ ! -s "${BACKUP_FILE}" ]]; then
  echo "[错误] 备份文件为空，备份可能失败。" >&2
  exit 1
fi

echo "[信息] 备份完成：${BACKUP_FILE}（$(du -h "${BACKUP_FILE}" | cut -f1)）"

# ========== 清理过期备份 ==========
echo "[信息] 清理超过 ${KEEP_DAYS} 天的旧备份..."
# 删除超过保留天数的本数据库备份文件
find "${BACKUP_DIR}" -type f -name "${DB_NAME}_*.sql" -mtime "+${KEEP_DAYS}" -delete

# 统计剩余备份数
REMAINING=$(find "${BACKUP_DIR}" -type f -name "${DB_NAME}_*.sql" | wc -l)
echo "[信息] 当前保留备份文件数：${REMAINING}"
