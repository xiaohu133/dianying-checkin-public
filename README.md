# 🎬 癫影 (dian115.com) & 🪺 影巢 (re0.me) 多账号自动签到中心 (DianYing & YingChao Auto Checkin)

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Web_UI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

专门针对 **癫影 (dian115.com)** 与 **影巢 (re0.me)** 社区设计的**现代化双平台多账号全自动每日签到与积分管理系统**。内置双平台逆向签名引擎（癫影本地 ECDSA SECP256R1 密钥派生 + 影巢 Rust WebAssembly/PoW 握手与请求签名验证）、多账号独立身份沙箱、Telegram 实时卡片合并推送，以及现代化深色玻璃质感 Web 控制台。

---

## ✨ 核心特性

- 🌐 **双平台深度集成与聚合管理**：
  - 🎬 **癫影 (`m.dian115.com`)**：支持邮箱+密码自动登录、本地动态生成 EC SECP256R1 密钥对签名，全自动静默续期守护；
  - 🪺 **影巢 (`re0.me`)**：原生内置官方 `hdh_security_bg.wasm` 算力引擎，自动计算 16-bit Proof-of-Work (PoW)、X25519 密钥交换握手与请求全量防篡改签名。
- 👥 **多账号聚合一站式管理**：
  - 每个账号拥有独立的平台标识、会话凭据与签名握手沙箱，互不干扰；
  - Web 端可视化添加、编辑、单独触发或一键批量签到；
  - 支持为每个账号独立选择签到策略与每日签到时间。
- 🎲 **专属双签到模式**：
  - **癫影**：🎲 运气签到模式（浮动暴击随机奖励） / 📅 普通稳健模式（固定积分）；
  - **影巢**：📅 每日稳健签到（固定奖励） / 🎲 赌狗签到模式（随机倍率奖励）。
- ⏰ **灵活的多账号独立定时**：
  - 支持为每个账号设定专属每日签到时间（如账号 A `00:05`，账号 B `08:30`）；
  - 未单独设定的账号自动继承全局默认时间。
- 🤖 **Telegram 实时卡片推送**：
  - 明确标识 🎬 癫影 / 🪺 影巢 平台图标与账号备注；
  - 定时批量执行时自动合并为一张精致卡片，推送当前可用积分、签到收益与连续签到天数。
- 🖥️ **现代化深色玻璃质感 Web 控制台**：
  - 基于 Vue 3 + Tailwind CSS 构建，支持快捷切换平台、实时状态刷新与一键单测。

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

### 1. 添加 🎬 癫影账号
1. 点击控制台顶部的 **【➕ 添加账号】**；
2. 平台类型选择 **🎬 癫影**；
3. 输入 **账号备注名**、**注册邮箱** 与 **登录密码**；
4. 选择签到模式（推荐 🎲 运气签到模式）；
5. 点击 **【保存账号】**。系统将自动在后台模拟安全登录验证、拉取积分并开启自动静默续期守护。

### 2. 添加 🪺 影巢账号
1. 电脑浏览器打开 [https://re0.me/](https://re0.me/) 并登录账号；
2. 按 `F12` 打开开发者工具，点击 **应用程序 (Application)** -> **Cookies** -> 找到 `https://re0.me`；
3. 复制名称为 **`token`** 的值（一串以 `eyJ` 开头的文本）；
4. 回到签到控制台，点击 **【➕ 添加账号】**，平台选择 **🪺 影巢**；
5. 粘贴 Token，选择签到模式（📅 每日签到 或 🎲 赌狗模式），点击 **【保存账号】** 即可完成！

### 3. 配置 Telegram 机器人通知 (可选)
在控制台下方的「系统配置」区域：
- **Bot Token**：在 Telegram 找 [@BotFather](https://t.me/BotFather) 创建机器人获取的 Token；
- **Chat ID**：您的 Telegram 用户 ID 或频道 ID（可向 [@userinfobot](https://t.me/userinfobot) 发送消息查看）；
- 点击 **【测试 Telegram 推送】**，收到测试卡片即代表配置成功！

---

## ❓ 常见问题 (FAQ)

**Q: 影巢的 Token 会过期吗？**
A: 影巢官方 Cookie `token` 有效期较长。系统内置了请求重试与失效检测机制，若 Token 失效时会自动记录并在 Telegram 发送提醒通知。

**Q: 如何修改访问端口？**
A: 将 `compose.yaml` 中 `ports` 下的 `"8098:8080"` 左侧的 `8098` 改成任何您想要的未占用端口（如 `"9098:8080"`），然后保存重启容器即可。

**Q: 如何让多个账号在不同时间错峰签到？**
A: 点击账号卡片上的「编辑」，在「独立每日签到时间」中填入 24 小时制的时间（如 `08:30`）。若留空，则默认跟随底部的全局时间（`00:05`）。

---

## 📄 开源协议 (License)

本项目基于 [MIT License](LICENSE) 协议开源分发。
