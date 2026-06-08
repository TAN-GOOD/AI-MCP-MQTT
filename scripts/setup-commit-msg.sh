#!/bin/bash
#
# 中文提交说明配置安装脚本
# 运行此脚本配置git使用中文提交说明模板和钩子
#

set -e

echo "正在配置中文提交说明环境..."

# 获取项目根目录
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

# 检查是否在git仓库中
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "错误：当前目录不是git仓库"
    exit 1
fi

# 设置git使用中文提交说明模板
echo "配置git提交说明模板..."
git config commit.template "$PROJECT_ROOT/.gitmessage"

# 复制git钩子文件
echo "安装git钩子..."
HOOKS_DIR="$PROJECT_ROOT/.git/hooks"
HOOKS_SOURCE="$PROJECT_ROOT/.githooks"

if [ -d "$HOOKS_SOURCE" ]; then
    # 备份现有的钩子文件
    for hook in prepare-commit-msg commit-msg; do
        if [ -f "$HOOKS_DIR/$hook" ]; then
            echo "备份现有钩子: $HOOKS_DIR/$hook -> $HOOKS_DIR/$hook.backup"
            cp "$HOOKS_DIR/$hook" "$HOOKS_DIR/$hook.backup"
        fi
    done
    
    # 复制新的钩子文件
    cp "$HOOKS_SOURCE"/* "$HOOKS_DIR/"
    chmod +x "$HOOKS_DIR"/*
    echo "钩子安装完成"
else
    echo "警告：未找到钩子源文件目录 $HOOKS_SOURCE"
fi

# 配置其他git设置
echo "配置其他git设置..."
git config core.autocrlf input
git config core.safecrlf warn

echo ""
echo "配置完成！"
echo ""
echo "现在您可以使用中文提交说明了。示例："
echo "  feat(auth): 添加用户注册功能"
echo "  fix(mqtt): 修复连接断开后无法重连的问题"
echo "  docs: 更新README安装说明"
echo ""
echo "提交说明格式：<类型>(<范围>): <主题>"
echo "类型：feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert"
echo "范围（可选）：auth, project, tool, mqtt, mcp, database, api, ui, config, deps"
echo ""
echo "祝您编码愉快！"