# -*- coding: utf-8 -*-
"""AGV 路径仿真工具后端：AI 图层分类 / 交管方案建议 / 底图视觉提示。"""
from __future__ import annotations

import base64
import io
import os
import shutil
import tempfile

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..services import llm, dwg_convert, dxf_extract

router = APIRouter(prefix="/agv", tags=["agv"])


# ---------------- 图层名智能分类（纯文本，便宜模型即可） ----------------

class LayerInfo(BaseModel):
    name: str
    count: int = 0
    kinds: str = ""


class ClassifyReq(BaseModel):
    layers: list[LayerInfo]


_WALL_KW = ("wall", "墙", "柱", "建筑", "结构", "column", "设备", "货架", "rack",
            "固定", "围栏", "栏杆", "rail", "fence")
_PATH_KW = ("path", "route", "路径", "路线", "车道", "磁条", "磁导航", "二维码",
            "agv", "轨迹", "通道", "行驶", "导航", "slam", "lane")
_IGNORE_KW = ("标注", "文字", "text", "dim", "尺寸", "标注", "灯具", "喷淋", "水电",
              "风管", "电缆", "table", "标题", "图框", "轴线", "轴网", "hatch", "填充")


def _rule_classify(name: str) -> str:
    n = (name or "").lower()
    if any(k in n for k in _PATH_KW):
        return "path"
    if any(k in n for k in _WALL_KW):
        return "wall"
    if any(k in n for k in _IGNORE_KW):
        return "ignore"
    return "unknown"


@router.post("/classify-layers")
async def classify_layers(req: ClassifyReq):
    """根据图层名/实体数量/类型，建议 墙体(wall)/路径(path)/忽略(ignore)。
    LLM 不可用时回退到关键词规则。"""
    fallback = {"wall": [], "path": [], "ignore": [], "unknown": [],
                "source": "rules", "raw": None}
    for ly in req.layers:
        fallback[_rule_classify(ly.name)].append(ly.name)

    if not llm.LLM_ENABLED:
        return fallback

    lines = "\n".join(
        f"- 图层名: {ly.name} | 实体数: {ly.count} | 类型: {ly.kinds or '混合'}"
        for ly in req.layers[:120]
    )
    prompt = f"""你是工厂布局CAD图纸分析专家。下面是一张车间/仓库布局图的图层清单。
请把每个图层归类为：
- wall：固定障碍物（建筑墙体、柱子、设备、货架、围栏等AGV不能穿越的对象）
- path：AGV行驶路径/车道/磁条/二维码导航线路
- ignore：与AGV通行无关的图层（尺寸标注、文字、轴线、水暖电、图框、填充等）
- unknown：无法判断

规则：
1. 必须对每个图层都给出分类，图层名原样返回，不要遗漏或改名。
2. 按常识判断：图层名同时包含墙和路径关键词时，结合实体类型判断；实体为CIRCLE/LWPOLYLINE且图层名含货架/设备判wall。
3. 只返回JSON，格式：{{"wall":[],"path":[],"ignore":[],"unknown":[]}}

图层清单：
{lines}"""
    data = await llm.chat_json(prompt, model=None, max_tokens=2000)
    if not data or not isinstance(data, dict):
        return fallback
    # 清洗：只保留请求中真实存在的图层名
    valid = {ly.name for ly in req.layers}
    out = {"wall": [], "path": [], "ignore": [], "unknown": [],
           "source": "llm", "raw": data}
    for key in ("wall", "path", "ignore", "unknown"):
        vals = data.get(key) or []
        if isinstance(vals, str):
            vals = [vals]
        out[key] = [v for v in vals if isinstance(v, str) and v in valid]
    classified = set(out["wall"]) | set(out["path"]) | set(out["ignore"])
    out["unknown"] = list({*(out["unknown"]),
                           *(ly.name for ly in req.layers if ly.name not in classified)})
    return out


# ---------------- 交管方案 AI 建议 ----------------

class AdviceReq(BaseModel):
    vehicle: dict
    paths: list[dict]
    conflicts: list[dict]
    zones: list[dict]


@router.post("/traffic-advice")
async def traffic_advice(req: AdviceReq):
    """根据几何冲突+时间窗分析结果，给出交管方案建议。"""
    if not llm.LLM_ENABLED:
        return {"enabled": False, "text": ""}
    import json
    payload = json.dumps({
        "vehicle": req.vehicle,
        "paths": [{k: p.get(k) for k in ("name", "length", "speed", "delay",
                                         "reverse", "direction")} for p in req.paths],
        "conflicts": req.conflicts[:40],
        "zones": req.zones[:20],
    }, ensure_ascii=False)
    prompt = f"""你是AGV多车调度（交管）方案专家。以下是某车间AGV路径仿真的冲突分析JSON：
{payload}

其中conflicts含type(cross交叉/parallel共线逼近)、active(true=按设定速度与发车间隔会同时到达，false=仅几何交汇时间错开)、dt(两车到达时间差秒)。
请输出简洁的中文交管建议（Markdown，300字以内）：
1. 先给总体结论（共几个必须交管的冲突区、最高风险点）；
2. 对active冲突按风险排序，逐个给交管方式建议（路口红绿灯/区域互斥令牌/路径改线/错峰发车/物理隔离），说明理由；
3. 对parallel（共线/贴行）冲突给会车/超车策略；
4. 如果有dt接近阈值的，提示调度需留安全余量。
不要复述原始数据，只给工程上可执行的建议。"""
    text = await llm.chat(prompt, temperature=0.2, max_tokens=900)
    return {"enabled": bool(text), "text": text or ""}


# ---------------- DWG 导入：本机 ODA File Converter 转换 + 服务端几何提取 ----------------

@router.post("/convert-dwg")
def convert_dwg(file: UploadFile = File(...)):
    """上传 DWG → ODA 转 DXF → ezdxf 提取几何（块参照取包围盒）→ 精简 JSON。
    同步路由（FastAPI 自动丢线程池），大图纸约需 30~120 秒。"""
    name = file.filename or "upload.dwg"
    if not name.lower().endswith(".dwg"):
        return JSONResponse({"ok": False, "error": "仅支持 .dwg 文件；DXF 可直接导入。"},
                            status_code=400)
    fd, tmp = tempfile.mkstemp(suffix=".dwg", prefix="agv_up_")
    work_dir = None
    try:
        size = 0
        with os.fdopen(fd, "wb") as f:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > 300 * 1024 * 1024:
                    return JSONResponse({"ok": False, "error": "DWG 超过 300MB，请先清理冗余内容。"}, status_code=400)
                f.write(chunk)
        if not size:
            return JSONResponse({"ok": False, "error": "文件为空。"}, status_code=400)
        try:
            dxf_path, work_dir = dwg_convert.convert_file(tmp)
        except dwg_convert.ConverterMissing as e:
            return JSONResponse(
                {"ok": False, "missing": True, "converter": dwg_convert.find_oda(),
                 "error": str(e)}, status_code=503)
        except dwg_convert.ConverterError as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=422)
        try:
            result = dxf_extract.extract_entities(dxf_path)
        except Exception as e:
            return JSONResponse({"ok": False,
                                 "error": f"DXF 几何提取失败：{e}"}, status_code=422)
    finally:
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)
        try:
            os.remove(tmp)
        except OSError:
            pass

    return {
        "ok": True,
        "units": result["units"],
        "entities": result["entities"],
        "counts": result["counts"],
        "sourceName": os.path.splitext(os.path.basename(name))[0],
    }


# ---------------- 底图（PNG/JPG截图）视觉提示 ----------------

@router.post("/vision-hint")
async def vision_hint(file: UploadFile = File(...),
                      note: str = Form(default="")):
    """对非DXF底图（截图/照片）给出图层描绘提示。坐标级识别不可靠，
    仅返回定性提示，指导用户手绘/拾色描绘，不直接落坐标。"""
    if not llm.LLM_VISION_MODEL:
        return {"enabled": False, "text": "未配置视觉模型（LLM_VISION_MODEL）"}
    raw = await file.read()
    if len(raw) > 8 * 1024 * 1024:
        return {"enabled": False, "text": "图片超过8MB"}
    prompt = ("这是一张用于AGV路径仿真的工厂/车间图纸（可能是CAD截图、平面图或照片）。"
              "请用简短中文(200字内)回答：1)图中哪些视觉元素可能是AGV路径/车道"
              "（说明颜色、线型、位置）；2)哪些是墙体/固定障碍物（颜色/填充特征）；"
              "3)是否有比例尺或尺寸标注可用于标定；4)人工描绘时的注意事项。"
              f" {note}")
    text = await llm.vision(raw, prompt)
    return {"enabled": bool(text), "text": text or "识别失败，请直接手绘描绘。"}
