# HCI Service Log Map

用于维护“服务名 -> 常见日志路径”的映射，帮助在已知服务名时快速定位候选日志文件。

## 目录约定

- 服务日志根目录通常在 `/sf/log/`
- 当天日志通常在 `today/` 子目录
- 黑盒日志常见目录：
  - `/sf/log/blackbox/`
  - `/sf/log/vn-blackbox/`

## 已收录服务映射

| 服务名 | 常见日志路径 | 说明 |
| --- | --- | --- |
| `upgrade-server` | `/sf/log/today/upgrade-server.log` | 升级框架服务日志 |
| `upgrade-worker` | `/sf/log/today/upgrade-worker.log` | 升级执行 worker 日志 |
| `upgrade` | `/sf/log/today/update.log` | 升级主流程日志 |

## 使用规则

1. 映射表用于缩小候选范围，不等于当前日志一定有问题。
2. 先结合服务名和时间窗口，再读取对应日志。
3. 若同一场景涉及黑盒日志，应额外检查：
   - `/sf/log/blackbox/`
   - `/sf/log/vn-blackbox/`
4. 若服务未收录，明确标注缺失并补充到该表，不要在回答中编造日志文件名。
