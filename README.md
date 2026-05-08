# 库街区自动签到

支持多账号的库街区（战双帕弥什 / 鸣潮 / 社区）每日自动签到，Bark / ServerChan3 推送结果。

## 特性

- 多账号并行签到，汇总后统一推送
- 每个账号可配置独立通知渠道
- API 瞬时故障自动重试（指数退避 5s / 10s / 20s）
- 同日防重复执行，避免惊群效应叠加
- 日志自动脱敏（token 等敏感信息打码）
- systemd 持久化运行，异常退出自动拉起

## 快速开始

### 1. 安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 填写配置

编辑 `config.yaml`：

```yaml
schedule:
  time: "07:13"           
  timezone: Asia/Shanghai

notification:             # 全局通知（可选）
  server3_send_key: "SCT..."  # Server酱3  https://sct.ftqq.com
  bark_device_key: "xxx"      # Bark iOS推送，自建服务可加 bark_server_url

accounts:
  - token: "你的库街区token"
    name: "大号"
  - token: "第二个账号的token"
    name: "小号"
    notification:              # 该账号单独的推送（可选，覆盖全局）
      server3_send_key: "SCT..."
      bark_device_key: "xxx"
```


### 3. 注册为系统服务

```bash
sudo cp auto-checkin.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now auto-checkin
```

## 通知效果

```
库街区自动签到任务
─────────────────
【大号】
战双签到成功
鸣潮签到成功
社区签到成功

【小号】
战双签到成功
鸣潮签到成功
社区签到成功
```

## 文件结构

| 文件 | 职责 |
|------|------|
| `run.py` | 调度入口：启动执行 + 每日定时 + 防重复守卫 |
| `auto_checkin.py` | 签到核心：调用库街区 API，含重试逻辑 |
| `settings.py` | 配置解析：`config.yaml` → `AppConfig` |
| `ext_notification.py` | 通知推送：Bark / ServerChan3 |
| `logging_utils.py` | 日志脱敏：自动隐藏 token 等敏感字段 |
| `config.yaml` | 用户配置 |
| `requirements.txt` | Python 依赖 |
| `SIGN_LOGIC.md` | 签到逻辑详解 |
| `DEPLOY.md` | 部署流程 |

## 常见日志解读

| 日志 | 含义 |
|------|------|
| `今日已完成签到，跳过重复执行` | 日期守卫拦截，当天已执行过 |
| `今日已签到，跳过` | API 返回"请勿重复签到"，正常行为 |
| `第2次重试成功` | 瞬时代码生效，第一次失败后重试成功 |
| `签到最终失败（已重试3次）` | 4 次全部失败，API 可能挂了 |
| `时区转换: 08:00 Asia/Shanghai -> 本地时间 XX:XX` | 启动时打印时区映射 |
| `签到汇总: 2/2 个账号成功` | 本轮结果统计 |

## 致谢

本项目改编自 [kurobbs_auto_checkin](https://github.com/leeezep/kurobbs_auto_checkin)，感谢原作者 [@leeezep](https://github.com/leeezep) 的开源贡献。


