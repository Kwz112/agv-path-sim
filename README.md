# AGV 路径仿真 · AGV Path Simulator

在浏览器里导入车间图纸（DXF / DWG / 图片），绘制 AGV 路径，检查障碍物碰撞、最小转弯半径和多车交汇风险，并导出报告和 PNG。

> **English:** A local, browser-based tool for planning AGV routes on factory floor plans. Import a DXF/DWG drawing or an image, draw paths, and check obstacle collisions, minimum turning radius and multi-vehicle conflicts. Runs entirely on `127.0.0.1`; the UI is in Chinese.

> ⚠️ **安全声明**：本工具不控制真实车辆。检测基于几何采样和简化时间窗，结果不能代替现场安全评估和实车验证。未发现风险不代表实际安全。

## 功能

- 导入 DXF（浏览器内解析）或 DWG（需本机安装 ODA File Converter），也可以用图片做底图手动描绘
- 按图层自动区分墙体、路径和可忽略的内容（本地关键词规则，可选接入 AI）
- 根据车体尺寸和安全余量做扫掠体碰撞检测
- 检查最小回转半径
- 按速度和发车时间分析多车交汇与共线逼近
- 内置示例场景，导出报告、PNG 和 JSON 数据

## 运行环境

- Windows 10/11（DWG 转换只支持 Windows；DXF 和图片导入在其他系统上也能用，但没有测试过）
- Python 3.12
- 现代浏览器（Chrome / Edge / Firefox）

## 安装与启动

在项目目录的 PowerShell 中执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

然后双击 `start.bat`，浏览器会自动打开 http://127.0.0.1:8765/ 。关闭控制台窗口或按 Ctrl+C 停止。

只有首次安装依赖时需要联网。本地仿真和 DXF 导入都不需要联网，服务也只监听本机。

## 使用限制

- 自动保存使用浏览器的 localStorage，不保存 DXF 实体和底图。导出的 JSON 也不含底图，**目前不支持重新导入**，不能当作完整的工程备份，请保留原始图纸。
- DWG 导入需要自行安装 [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter)，并遵守它的许可：ODA 规定非会员只能用于非商业用途，详见[官方说明](https://www.opendesign.com/faq/question/what-are-oda-viewer-and-oda-file-converter)。本项目不包含 ODA。转换器不在默认位置时，可以用环境变量 `ODA_FILE_CONVERTER` 指定路径。也可以先在 CAD 里把图纸另存为 DXF。
- 真实 DWG、复杂图纸和在线 AI 功能尚未充分测试。

## 可选：AI 辅助

AI 默认关闭。关闭时，图层分类使用本地关键词规则。开启后可以使用 AI 图层分类、交管方案建议和底图视觉提示。需要一个兼容 OpenAI `/chat/completions` 的服务。

在同一个 PowerShell 会话里设置环境变量后启动：

```powershell
$env:AGV_AI_ENABLED = 'true'
$env:AGV_LLM_BASE_URL = 'https://your-provider.example/v1'
$env:AGV_LLM_API_KEY = 'your-key'
$env:AGV_LLM_MODEL = 'your-model'
$env:AGV_LLM_VISION_MODEL = 'your-vision-model'  # 可选
.\start.bat
```

- 为了保护 API Key，`AGV_LLM_BASE_URL` 必须使用 `https://`。只有本机模型服务（`localhost` / `127.0.0.1`）可以用 `http://`。
- 开启后，图层名称、分析数据或底图图片会发送给你配置的模型服务。
- 不要把真实密钥写进代码或提交到 Git。

## 项目结构

```
backend/    FastAPI 服务：DWG 转换、DXF 几何提取、可选的 AI 接口
frontend/   单页应用（agv-sim.html）、样式、交互组件和 dxf-parser
launch.py   启动本机服务并打开浏览器
start.bat   Windows 启动脚本
```

## 许可证

[MIT](LICENSE)。第三方组件说明见 [THIRD_PARTY.md](THIRD_PARTY.md)。
