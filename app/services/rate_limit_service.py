"""简单的内存限流服务（单进程）。

用于登录端点防止暴力破解。基于 IP + 用户名双维度计数。
注意：多 worker 部署下需替换为 Redis 实现。
"""
import time
from collections import defaultdict
from threading import Lock


class RateLimiter:
    """滑动窗口限流器"""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300, lockout_seconds: int = 600):
        # window_seconds 内 max_attempts 次失败后，锁定 lockout_seconds 秒
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._failures: dict = defaultdict(list)  # key -> [timestamp, ...]
        self._lockout_until: dict = {}  # key -> timestamp
        self._lock = Lock()

    def _key(self, ip: str, username: str) -> str:
        return f"{ip}:{username}"

    def is_locked(self, ip: str, username: str) -> bool:
        """是否处于锁定状态"""
        key = self._key(ip, username)
        with self._lock:
            until = self._lockout_until.get(key)
            if until and time.time() < until:
                return True
            if until:
                # 锁定已过期，清理
                del self._lockout_until[key]
            return False

    def record_failure(self, ip: str, username: str):
        """记录一次失败"""
        key = self._key(ip, username)
        now = time.time()
        with self._lock:
            # 清理过期记录
            self._failures[key] = [t for t in self._failures[key] if now - t < self.window_seconds]
            self._failures[key].append(now)
            # 超过阈值则锁定
            if len(self._failures[key]) >= self.max_attempts:
                self._lockout_until[key] = now + self.lockout_seconds

    def reset(self, ip: str, username: str):
        """登录成功后重置"""
        key = self._key(ip, username)
        with self._lock:
            self._failures.pop(key, None)
            self._lockout_until.pop(key, None)

    def remaining_lockout(self, ip: str, username: str) -> int:
        """剩余锁定秒数"""
        key = self._key(ip, username)
        with self._lock:
            until = self._lockout_until.get(key)
            if until and time.time() < until:
                return int(until - time.time())
            return 0


login_limiter = RateLimiter(max_attempts=5, window_seconds=300, lockout_seconds=600)
