# 🎬 癫影 (dian115.com) 多账号自动签到中心 (DianYing Auto Checkin)

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Web_UI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

专门针对 **癫影 (dian115.com)** 社区设计的**现代化全自动每日签到与多账号积分管理系统**。原生内置浏览器底层挑战穿透、本地 ECDSA SECP256R1 密钥动态派生与时间戳/Nonce 签名、账号密码自动静默续期（像 API 一样永不过期）、Telegram 实时结果合并推送，以及现代化深色玻璃质感 Web 控制台。

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
- ⏰ **多账号独立定时时间支持**：
  - 支持为每个账号自定义不同的每日签到时间（如账号 A 设为 `00:05`，账号 B 设为 `08:30`）；
  - 亦可留空直接继承全局默认时间，灵活自由。
- 🎲 **双签到模式自由切换**：
  - **🎲 运气签到模式**：积分浮动随机，最高可获取高额暴击奖励（推荐）；
  - **📅 普通稳健模式**：稳步累积固定签到积分。
- 🤖 **Telegram 机器人实时通知**：
  - 手动单账号签到、批量一键签到及每日夜间定时签到均支持实时推送 Telegram 卡片通知；
  - 多账号定时执行时自动合并为一张汇总卡片，避免多条消息刷屏。
- 🖥️ **轻量现代 Web 控制台**：
  - 基于 Vue 3 + Tailwind CSS 构建，极简深色玻璃拟态质感；
  - 实时查看各账号的头像、昵称、剩余积分、VIP 状态与到期倒计时。

---

## 🚀 飞牛 NAS (fnOS) 极速部署指南（零门槛 · 纯镜像一键拉取）

> 💡 **无需下载任何源代码或项目文件！**
> 本项目已由 GitHub Actions 全自动打包发布公开多架构镜像（支持 AMD64 与 ARM64 设备）。在飞牛 NAS 部署只需粘贴下方 10 行代码即可！

### 方式一：通过飞牛 NAS Web 桌面端部署（新手强烈推荐 · 仅需 1 分钟）

1. 打开飞牛 NAS 桌面管理界面，进入 **「Docker 应用」**；
2. 在左侧菜单点击 **「Compose」**，然后点击右上角 **「新增项目」**；
3. **基本信息**：
   - **项目名称**：填写 `dianying-checkin`
   - **存放路径**：推荐选择您的 Docker 路径，例如 `/vol2/docker/dianying-checkin`
4. **编辑配置**：在代码输入区直接粘贴以下完整内容（**无需额外放任何文件**）：

```yaml
services:
  dianying-checkin:
    image: ghcr.io/xiaohu133/dianying-checkin-public:latest
    container_name: dianying-checkin
    restart: always
    ports:
      # 宿主机访问端口（可根据需要修改左侧 8098 为其他未占用端口）
      - "8098:8080"
    dns:
      # 配置可靠 DNS，彻底解决绿联/极空间/部分群晖 Docker 桥接无法解析外网域名的通病
      - 223.5.5.5
      - 119.29.29.29
      - 8.8.8.8
    environment:
      - TZ=Asia/Shanghai
    volumes:
      # 数据持久化目录（存放账号与签到历史）
      - ./data:/app/data
```

5. 点击 **「完成构建并启动」**，飞牛 NAS 会全自动从云端拉取现成镜像并极速启动！
6. 启动后，浏览器直接打开：**`http://<您的飞牛NAS内网IP>:8098`** 进入管理控制台！

---

### 方式二：通过 SSH 终端一键部署（极客推荐）

1. SSH 登录您的飞牛 NAS；
2. 执行以下命令一键创建配置并启动：
   ```bash
   mkdir -p /vol2/docker/dianying-checkin && cd /vol2/docker/dianying-checkin

   cat <<'EOF' > compose.yaml
   services:
     dianying-checkin:
       image: ghcr.io/xiaohu133/dianying-checkin-public:latest
       container_name: dianying-checkin
       restart: always
       ports:
         - "8098:8080"
       dns:
         - 223.5.5.5
         - 119.29.29.29
         - 8.8.8.8
       environment:
         - TZ=Asia/Shanghai
       volumes:
         - ./data:/app/data
   EOF

   docker compose up -d
   ```

---

## 📖 首次使用与配置指引

启动容器后，通过浏览器访问：`http://<NAS_IP>:8098`

### 1. 添加您的癫影账号（无需手动抓取 Cookie！）
1. 点击控制台顶部的 **【➕ 添加账号】**；
2. 输入 **账号备注名**（例如：主账号 / 小号）；
3. 输入您的 **癫影注册邮箱** 与 **登录密码**；
4. 选择签到模式（默认推荐 🎲 运气签到模式）；
5. 点击 **【保存账号】**。系统将自动在后台模拟安全登录验证、拉取当前可用积分，并开启全自动静默续期守护！

> 💡 **提示**：配置邮箱密码后，系统会自动在后台管理与刷新 Token，无需手动打开 F12 抓包复制 Cookie。

### 2. 配置 Telegram 机器人通知 (可选)
在控制台下方的「系统配置」区域：
- **Bot Token**：在 Telegram 找 [@BotFather](https://t.me/BotFather) 创建机器人获取的 Token；
- **Chat ID**：您的 Telegram 用户 ID 或频道 ID（可向 [@userinfobot](https://t.me/userinfobot) 发送消息查看）；
- 点击 **【测试 Telegram 推送】**，收到测试卡片即代表配置成功！

---

## ❓ 常见问题 (FAQ)

**Q: 首次使用还需要手动抓取 Cookie 吗？**
A: **完全不需要！** 只要在添加账号时输入癫影注册邮箱和密码，系统内置的登录签名引擎会自动完成身份验证并生成所需会话凭据，并在即将失效时全自动静默重登刷新。

**Q: 如何修改访问端口？**
A: 将 `compose.yaml` 中 `ports` 下的 `"8098:8080"` 左侧的 `8098` 改成任何您想要的未占用端口（如 `"9098:8080"`），然后保存重启容器即可。

**Q: 如何让多个账号在不同时间错峰签到？**
A: 点击账号卡片上的「编辑」，在「独立每日签到时间」中填入 24 小时制的时间（如 `08:30`）。若留空，则默认跟随底部的全局时间（`00:05`）。

---

## 📄 开源协议 (License)

本项目基于 [MIT License](LICENSE) 协议开源分发。
