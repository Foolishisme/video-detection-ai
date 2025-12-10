# 视频监控仪表板前端

基于 React + Material-UI v5 的专业暗色模式视频监控仪表板。

## 技术栈

- **React 18+** - UI 框架
- **TypeScript** - 类型安全
- **Material-UI v5** - UI 组件库
- **Emotion** - CSS-in-JS 样式引擎
- **Vite** - 构建工具

## 功能特性

- ✅ 动态网格布局（根据视频源数量自动调整：1x1, 2x2, 3x3）
- ✅ 实时视频流显示（MJPEG）
- ✅ AI 告警高亮（红色边框闪烁动画）
- ✅ 告警次数显示（每个视频窗口左上角）
- ✅ 全屏危险弹窗（5秒自动关闭）
- ✅ 小窗口警告（提醒类告警，10秒自动消失）
- ✅ 响应式设计（支持移动端、平板、桌面端）
- ✅ 暗色主题（专业监控界面风格）

## 开发

### 安装依赖

```bash
npm install
```

### 配置 API 基础 URL

**开发环境（推荐使用代理）：**

开发环境下，Vite 已配置代理，前端会自动将 `/api/*` 请求转发到后端服务器（`http://127.0.0.1:8123`）。
无需额外配置，直接启动即可。

**如果需要自定义后端地址：**

创建 `.env.development` 文件（可选）：

```env
# 开发环境：通常留空，使用 Vite 代理
# 如果后端运行在不同地址，可以配置完整URL
# 例如: http://192.168.1.100:8123
VITE_API_BASE_URL=
```

**生产环境：**

创建 `.env.production` 文件：

```env
# 生产环境：配置完整的后端API地址
VITE_API_BASE_URL=http://your-server.com:8123
```

### 启动开发服务器

```bash
npm run dev
```

前端将在 `http://localhost:5173` 启动。

**外部访问：**

开发服务器默认绑定到 `0.0.0.0`，支持外部访问：
- 本地访问：`http://localhost:5173`
- 局域网访问：`http://<your-ip>:5173`
- 通过代理访问：根据代理配置访问

### 构建生产版本

```bash
npm run build
```

构建产物将输出到 `dist/` 目录。

## API 集成

前端需要连接到后端 FastAPI 服务。确保后端服务正在运行，并且：

1. **CORS 已配置**：后端需要允许前端域名的跨域请求
2. **API 端点可用**：
   - `GET /api/sources` - 获取视频源列表
   - `GET /api/video_feed/{source_id}` - MJPEG 视频流
   - `GET /api/status/{source_id}` - 获取视频源状态
   - `GET /api/alerts` - 获取告警列表

## 项目结构

```
frontend/
├── src/
│   ├── api/
│   │   └── api.ts              # API 调用封装
│   ├── components/
│   │   ├── Dashboard.tsx       # 主仪表板组件
│   │   ├── VideoGrid.tsx       # 视频网格布局
│   │   ├── VideoFeed.tsx       # 单个视频流组件
│   │   ├── AlertCountBadge.tsx # 告警计数徽章
│   │   ├── WindowWarning.tsx   # 窗口警告组件
│   │   └── FullscreenAlertDialog.tsx # 全屏告警弹窗
│   ├── types/
│   │   └── index.ts            # TypeScript 类型定义
│   ├── theme.ts                # MUI 暗色主题配置
│   ├── App.tsx                 # 应用入口组件
│   └── main.tsx                # 应用启动文件
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## 部署

### 方式一：独立部署

将构建产物部署到静态文件服务器（如 Nginx、Apache）。

### 方式二：集成到后端

将构建产物复制到 `server/static/` 目录，替换现有的 HTML 文件。

```bash
npm run build
cp -r dist/* ../server/static/
```

## 注意事项

- 确保后端服务已启动并配置了 CORS
- 视频流使用 MJPEG 格式，需要浏览器支持
- 告警轮询间隔：告警次数每 2 秒更新，新告警每 1 秒检查
- 告警边框闪烁动画持续 3 秒后自动关闭
