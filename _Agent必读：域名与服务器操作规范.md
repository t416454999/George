

> 任何 Agent 在接到涉及 `xingge.me`、`jgyq.me` 或其子域名的部署、修改、排查等操作前，**必须先完整阅读本文档**，确认所有规则后再执行操作。

---

## 一、服务器基础信息

| 项目 | 值 |
|------|-----|
| IP | `8.148.13.121` |
| 类型 | 阿里云轻量应用服务器（武汉） |
| 系统 | Ubuntu 22.04 |
| SSH 密钥 | `F:\公司主页\公司主页密钥.pem` |
| 用户 | `root` |
| 备案号 | 鄂ICP备2026029561号 |
| 实例 ID | `i-n4a3th24v9bch0rwcnrf` |

---

## 二、🔴 绝对禁止

### 2.1 禁止写明文密钥到任何应用目录

- 密钥只能写在 `env_file` 引用或 `environment` 环境变量中
- **不要**在 `/opt/` 或 `/opt/*/` 下创建 `.env` 文件
- 统一使用 `/opt/.env.prod`（权限 600，仅 root 可读）
- 如需修改密钥 → 编辑 `/opt/.env.prod`，然后 `docker compose up -d` 重启容器

### 2.2 禁止直接修改 systemd 管理下的进程

- 服务已全部 Docker 化（2026-07-10 迁移）
- **不要**直接启动/停止 `/opt/server.js` 或 `uvicorn` 进程
- systemd 单元（`xingge`, `xingge-parse`, `xingge-parse-dev`, `xingge-dev`）已被 mask
- 统一使用：`cd /opt && docker compose <up/down/restart/ps/logs>`

### 2.3 禁止开放不必要的端口

- UFW 规则：仅允许 22/tcp, 80/tcp, 443/tcp
- 应用端口（3000, 3001, 3003, 3004）只绑定 127.0.0.1，不对外暴露
- **不要**更改端口绑定到 0.0.0.0
- **不要**关闭 UFW 或清空 iptables

---

## 三、服务架构

### 3.1 容器化服务

| 容器 | 绑定端口 | 资源限制 | 说明 |
|------|---------|---------|------|
| `xingge-frontend` | 127.0.0.1:3000 | 0.5 CPU / 256M | 人格测试 H5（生产） |
| `xingge-parse` | 127.0.0.1:3001 | 0.5 CPU / 512M | 解析后端（生产） |
| `xingge-dev-frontend` | 127.0.0.1:3004 | 0.25 CPU / 128M | 开发前端 |
| `xingge-dev-parse` | 127.0.0.1:3003 | 0.25 CPU / 256M | 开发后端 |

容器网络：所有容器在 `xingge-net` bridge 网络下，可通过容器名互相访问（如 `parse:3001`）。

### 3.2 Nginx 站点代理

| 域名 | 代理目标 | HTTPS |
|------|---------|-------|
| xingge.me → `/var/www/xingge-home/index.html` | 静态文件 | ✅ |
| test.xingge.me → `127.0.0.1:3000` | 生产前端 | ✅ |
| test.xingge.me/generate → `127.0.0.1:3001` | 生产解析后端 | ✅ |
| test.xingge.me/dev/ → `127.0.0.1:3004` | 开发环境 | ✅ |
| beta.xingge.me → `127.0.0.1:3004` | 开发版 | ✅（新配） |
| hot.xingge.me → `/opt/hotcontent/app` | 静态 + API :3001 | ✅ |
| boke.jgyq.me → `/var/www/boke` | 静态 | ✅ |
| api.xingge.me | ❌ 已关停（return 444） | — |

### 3.3 Docker Compose 文件

- 位置：`/opt/docker-compose.yml`（权限 600）
- 操作命令：`cd /opt && docker compose <up/down/restart/ps/logs/build>`
- 构建镜像：`docker compose build <service>`

---

## 四、安全基线（不得破坏）

已部署的安全措施，任何操作后必须确认以下各项不受影响：

| 措施 | 位置/命令 | 验证方式 |
|------|----------|---------|
| 全局限流 | `/etc/nginx/nginx.conf` | `nginx -t` |
| fail2ban 自动封禁 | 4 个 jail（详见下方） | `fail2ban-client status` |
| 防火墙 | UFW active | `ufw status` |
| 健康检查 | cron 每 5 分钟 | `cat /var/log/server-health.log` |
| SSL 自动续期 | certbot + systemd timer | `certbot certificates` |
| server_tokens off | nginx.conf | `curl -sI \| grep server` |
| 博客隐藏文件保护 | `/etc/nginx/sites-enabled/boke` | `curl -I https://boke.jgyq.me/.git/HEAD` 必须为 403/404 |
| 博客安全响应头 | `/etc/nginx/sites-enabled/boke` | 检查 HSTS、nosniff、SAMEORIGIN、Referrer-Policy |
| 博客分层缓存 | `/etc/nginx/sites-enabled/boke` | HTML 60s、JSON 300s、CSS/JS/图片 30d |

### Fail2ban 规则（2026-07-12 更新）

| Jail | 目标 | maxretry | bantime | 日志位置 |
|------|------|----------|---------|---------|
| nginx-badbots | HTTP 4xx/5xx 错误 | **20**（← 从 2 调高，防误封） | 24h | `/var/log/nginx/access.log` |
| nginx-limit-req | Nginx 限流触发 | 3 | 1h | `/var/log/nginx/error.log` |
| nginx-404 | 扫描 404 路径 | 10/5m | 1h | `/var/log/nginx/access.log` |
| sshd | SSH 爆破 | 5/10m | 24h | `/var/log/auth.log` |

### ⚠️ 已知防护盲区

以下攻击类型当前**没有防护**，如需加防护参考 `日志/服务器故障日志-20260712.md`：

| 攻击类型 | 现状 | 推荐方案 |
|----------|------|---------|
| 分布式多 IP 攻击 | ❌ 无防护 | Cloudflare CDN（免费） |
| DDoS 流量攻击 | ❌ 无防护 | Cloudflare CDN / 阿里云高防 |
| 应用层漏洞（SQL注入/XSS） | ⚠️ 博客前端已统一转义和校验外链，仍无统一 WAF | Cloudflare WAF / 阿里云 WAF |
| 无自动备份 | ❌ 无备份 | 阿里云快照（免费1个/周） |

### 限流规则

| 限流 zone | 速率 | 用途 |
|-----------|------|------|
| general | 60r/min | 普通页面 |
| generate | 5r/min | `/generate` 接口 |
| dev | 30r/min | `/dev/` 开发环境 |
| submit | 10r/min | 提交答案 |

---

## 五、敏感信息管理

| 项目 | 位置 | 权限 |
|------|------|------|
| 生产密钥 | `/opt/.env.prod` | 600（root only） |
| 旧 .env 备份 | `/root/secrets-backup/` | 600（root only） |
| Compose 配置 | `/opt/docker-compose.yml` | 600（root only） |

**规则**：
- 任何时候不要将密钥写入代码文件、日志、或提交到 git
- 新服务需要密钥 → 加入 `/opt/.env.prod`，无需改动 compose 文件
- 备份密钥需放在 `/root/secrets-backup/`，不要放应用目录
- 博客 cron 也必须先安全加载 `/opt/.env.prod`；禁止在 crontab 中内联密钥

### 2026-07-14 博客安全变更记录

- `boke.jgyq.me` 已禁止访问所有隐藏文件，保留 `/.well-known/`；`/.git/HEAD` 已从 200 修复为 404。
- HTML 缓存 60 秒、JSON 5 分钟、CSS/JS/WebP 等静态资源缓存 30 天。
- 已增加 HSTS、`X-Content-Type-Options: nosniff`、`X-Frame-Options: SAMEORIGIN`、Referrer-Policy 和 Permissions-Policy。
- 严格 CSP 暂未启用，原因是博客仍有外部图片/数据源；启用前必须先完成来源清单和兼容验证。
- 博客定时任务的 `TIANAPI_KEY` 已从 crontab 迁入 `/opt/.env.prod`，文件权限 600。
- Nginx 备份：`/root/nginx-backups/20260714-171228`。
- cron/密钥迁移备份：`/root/secrets-backup/cron-migration-20260714-171310`。

---

## 六、SSH 连接方式

```bash
ssh -i "F:\公司主页\公司主页密钥.pem" root@8.148.13.121
```

---

## 七、变更流程

任何时候修改服务器配置，遵循以下顺序：

1. 读取本文档，理解当前架构和安全限制
2. 先做只读诊断（查看当前状态），再动刀
3. 每次修改前备份被改文件
4. 每次修改后验证：`nginx -t`（如改 Nginx）→ 服务健康检查 → 域名可达性
5. 变更完成后更新本文档中对应的章节
6. 绝不单步跳过安全验证

---

## 八、回滚

如需回滚到容器化前（systemd 管理）：

```bash
# 停止容器
cd /opt && docker compose down

# 恢复 systemd 服务
systemctl unmask xingge xingge-parse xingge-parse-dev xingge-dev
systemctl start xingge xingge-parse xingge-parse-dev xingge-dev

# 恢复 .env
cp /root/secrets-backup/.env.parse /opt/xingge-parse/.env
cp /root/secrets-backup/.env.prod-frontend /opt/.env

# 恢复 Nginx 配置：移除 nginx.conf 和 site config 中的 limit_req 行
```

---

## 九、本文件维护

- 任何导致架构或安全变化的操作，必须在本文档中同步更新
- 本文档位置：`F:\obsidian\qiaozhizhi\域名\_Agent必读：域名与服务器操作规范.md`
- 服务端对应：`/root/AGENT_MUST_READ.md`（定期同步即可）
