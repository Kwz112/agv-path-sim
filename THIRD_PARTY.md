# 第三方组件说明

本项目自身代码采用 [MIT](LICENSE) 许可。以下第三方组件按各自的许可证使用。

## 随仓库分发

- **dxf-parser 1.1.2**：MIT，https://github.com/gdsestimating/dxf-parser
  - 文件：`frontend/dxf-parser-1.1.2.js`，来源 https://cdn.jsdelivr.net/npm/dxf-parser@1.1.2/dist/dxf-parser.js
  - 许可：`frontend/LICENSE-dxf-parser.txt`
  - 该构建内含 **loglevel**（MIT），许可见 `frontend/LICENSE-loglevel.txt`

## 安装时获取（不随仓库分发）

`requirements.txt` 中列出的 Python 依赖（及其传递依赖）由使用者通过 pip 安装，版本锁定见 `requirements-lock.txt`。这些依赖均为宽松许可证（MIT、BSD、Apache-2.0、PSF、MPL-2.0）。如果你打包分发完整的运行环境，需要随包附上它们的许可和版权声明。

## 外部工具（不包含）

- **ODA File Converter**：仅在导入 DWG 时使用，由使用者自行安装，并遵守 ODA 许可。官方说明：https://www.opendesign.com/faq/question/what-are-oda-viewer-and-oda-file-converter
