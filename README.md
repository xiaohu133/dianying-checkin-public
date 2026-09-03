# 🎬 癫影 (dian115.com) 多账号自动签到中心 (DianYing Auto Checkin)

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Web_UI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

专门针对 **癫影 (dian115.com)** 社区设计的**现代化全自动每日签到与多账号积分管理系统**。原生内置浏览器底层挑战穿透、本地 ECDSA SECP256R1 密钥动态派生与时间戳/Nonce 签名、账号密码自动静默续期（永不过期）、Telegram 实时结果合并推送，以及现代化深色玻璃质感 Web 控制台。

---

## ✨ 核心特性

- 🛡️ **ECDSA SECP256R1 本地动态签名与静默续期（像 API 一样永不过期）**：
  - 原生内置浏览器底层挑战校验协议（Browser Challenge）与 Cloudflare 指纹穿透；
  - 本地动态生成 EC SECP256R1 密钥对并完成时间戳/Nonce 签名；
  - 支持配置【邮箱 + 密码】，Token 即将到期或失效时后台自动静默重登刷新，**彻底告别手动复制 Cookie 的繁琐维护**！
- 👥 **多账号聚合一站式管理**：
  - 每个账号拥有独立的身份沙箱与签名凭据，互不干扰；
  - 支持在 Web 端可视化添加、编辑、单独触发或一键全部签到；
  - 各账号支持独立设定不同的签到模式（如账号 A 开启运气签到，账号 B 开启普通签到）。
- 🎲 **双签到模式自由切换**：
  - **🎲 运气签到模式**：积分浮动随机，最高可获取高额暴击奖励（推荐）；
  - **📅 普通稳健模式**：稳步累积固定签到积分。
- 🤖 **Telegram 机器人合并卡片通知**：
  - 每日定时执行后，自动将所有账号的签到状态、本次奖励、剩余积分与连续签到天数**汇总为一张精美卡片**推送到 Telegram，避免多条消息刷屏。
- ⏰ **多账号独立定时时间支持**：
  - 支持为每个账号自定义不同的每日签到时间（如账号 A 设为 `00:05`，账号 B 设为 `08:30`）；
  - 亦可留空直接继承全局默认时间，灵活自由。
- ⏰ **内置自动化定时引擎**：
  - 默认每晚 `00:05` 准时自动唤醒签到，全天候守护；
  - 自动持久化保存最近 100 次签到流水记录与变动趋势。
- 🖥️ **轻量现代 Web 控制台**：
  - 基于 Vue 3 + Tailwind CSS 构建，极简深色玻璃拟态质感；
  - 实时查看各账号的头像、昵称、剩余积分、VIP 状态与到期倒计时。

---

## 🚀 飞牛 NAS (fnOS) Docker Compose 极速安装指南

系统完美适配飞牛 NAS (fnOS)、群晖 Synology、极空间、绿联等 NAS 系统及标准 Linux 服务器。以下提供飞牛 NAS 上的两种部署方式：

### 方式一：通过飞牛 NAS Web 桌面端部署（新手推荐）

1. 打开飞牛 NAS 桌面管理界面，进入 **「Docker 应用」**；
2. 在左侧菜单点击 **「Compose」**，然后点击右上角 **「新增项目」**；
3. **基本信息配置**：
   - **项目名称**：填写 `dianying-checkin`
   - **存放路径**：选择您的 Docker 存储目录，例如 `/vol2/docker/dianying-checkin`
4. **编辑配置**：在配置代码区粘贴下方的 `compose.yaml` 内容：

```yaml
services:
  dianying-checkin:
    build: .
    image: dianying-checkin:latest
    container_name: dianying-checkin
    restart: always
    ports:
      # Web UI 访问端口（宿主机 8098 映射至容器内部 8080）
      - "8098:8080"
    environment:
      - TZ=Asia/Shanghai
    volumes:
      # 数据持久化目录（存放账号配置与历史数据）
      - ./data:/app/data
```

5. 将项目文件（`dian_client.py`、`main.py`、`Dockerfile` 等）放置于该项目目录下；
6. 点击 **「完成构建并启动」**，飞牛 NAS 将自动构建镜像并启动容器；
7. 启动成功后，浏览器打开 **`http://<您的飞牛NAS内网IP>:8098`** 即可进入 Web 管理界面！

---

### 方式二：通过 SSH 终端极速一键部署（极客推荐）

1. 使用 SSH 客户端登录您的飞牛 NAS 终端；
2. 创建项目目录并进入：
   ```bash
   mkdir -p /vol2/docker/dianying-checkin && cd /vol2/docker/dianying-checkin
   ```
3. 克隆或下载本项目代码：
   ```bash
   git clone https://github.com/your_username/dianying-checkin.git .
   ```
4. 执行一键构建与启动：
   ```bash
   docker compose up -d --build
   ```
5. 查看运行状态：
   ```bash
   docker compose ps
   ```

---

## 📖 首次使用与配置指引

启动容器后，通过浏览器访问：`http://<NAS_IP>:8098`

### 1. 添加您的癫影账号
1. 点击控制台顶部的 **【➕ 添加账号】**；
2. 输入 **账号备注名**（例如：主账号 / 小号）；
3. 输入您的 **注册邮箱** 与 **登录密码**；
4. 选择签到模式（默认推荐 🎲 运气签到模式）；
5. 点击 **【保存账号】**。系统将自动连接癫影完成登录验证、拉取当前可用积分，并开启全自动静默续期守护！

> 💡 **提示**：配置了邮箱和密码后，系统会自动在后台管理与刷新 Cookie，无需手动打开 F12 复制 Cookie。

### 2. 配置 Telegram 机器人通知 (可选)
在控制台下方的「系统配置」区域：
- **Bot Token**：在 Telegram 找 [@BotFather](https://t.me/BotFather) 创建机器人获取的 Token；
- **Chat ID**：您的 Telegram 用户 ID 或频道 ID（可向 [@userinfobot](https://t.me/userinfobot) 发送消息查看）；
- 点击 **【测试 Telegram 推送】**，收到测试卡片即代表配置成功！

---

## 🛠️ 项目目录结构

```
dianying-checkin/
├── dian_client.py     # 癫影核心协议客户端 (ECDSA签名/自动续期/签到)
├── main.py            # FastAPI 服务端 + Vue 3 现代化 Web 控制台
├── Dockerfile         # 容器镜像构建文件
├── compose.yaml       # Docker Compose 编排文件
├── requirements.txt   # Python 依赖清单
├── .gitignore         # Git 忽略文件
├── LICENSE            # MIT 开源协议
└── README.md          # 详细说明文档
```

---

## ❓ 常见问题 (FAQ)

**Q: 会因为异地登录或频繁请求导致风控吗？**
A: 不会。系统内置完整的浏览器真实特征模拟（Chrome User-Agent 与 Sec-CH-UA 标头），每次网络会话均携带标准的 Browser Proof 与 ECDSA 数字签名，并且每日仅在指定时间（如 00:05）唤醒执行一次签到，其余时间处于休眠监听状态。

**Q: 如何修改每日自动签到时间？**
A: 直接在 Web 控制台的「每日自动签到时间」中输入 24 小时制的时间（如 `08:30` 或 `00:05`），保存后即刻生效，无需重启容器。

---

## 📄 开源协议 (License)

本项目基于 [MIT License](LICENSE) 协议开源分发。
