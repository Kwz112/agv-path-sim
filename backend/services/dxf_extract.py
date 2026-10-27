# -*- coding: utf-8 -*-
"""从 DXF 提取前端几何引擎所需的精简实体。

- 直接实体：LINE / LWPOLYLINE / POLYLINE / CIRCLE / ARC / SPLINE / ELLIPSE / POINT
- 块参照 INSERT：不展开内部细节（设备块常有数万条小线段），只输出其世界坐标
  包围盒矩形 kind=INSERT_BBOX——对 AGV 碰撞检测而言，设备占地轮廓已足够。
- 跳过 TEXT / DIMENSION / HATCH / 代理实体等与几何碰撞无关的对象。
"""
from __future__ import annotations

import math
from typing import Any

from ezdxf import bbox
from ezdxf.path import make_path

_KEEP = ("LINE", "LWPOLYLINE", "POLYLINE", "CIRCLE", "ARC",
         "SPLINE", "ELLIPSE", "POINT")
_FLAT_DIST = 150.0  # 曲线离散最大间距（世界单位，平面图通常为 mm）


def _round_pts(pts: list[tuple[float, float]]) -> list[list[float]]:
    return [[round(x, 1), round(y, 1)] for x, y in pts]


def _pts_of(e) -> tuple[list[tuple[float, float]] | None, bool]:
    """实体 -> (稠密点列, 是否闭合)。失败返回 (None, False)。"""
    t = e.dxftype()
    try:
        if t == "LINE":
            return [(e.dxf.start.x, e.dxf.start.y),
                    (e.dxf.end.x, e.dxf.end.y)], False
        if t == "POINT":
            p = e.dxf.location
            return [(p.x, p.y), (p.x, p.y)], False
        if t == "SPLINE":
            pts = [(p[0], p[1]) for p in e.flattening(_FLAT_DIST)]
            return pts, False
        path = make_path(e, timeout=10)
        closed = bool(getattr(e, "closed", False)) or t in ("CIRCLE", "ELLIPSE")
        pts = [(v[0], v[1]) for v in path.flattening(_FLAT_DIST, 32)]
        if closed and pts and (not math.isclose(pts[0][0], pts[-1][0], abs_tol=1e-6)
                               or not math.isclose(pts[0][1], pts[-1][1], abs_tol=1e-6)):
            pts.append(pts[0])
        return pts, closed
    except Exception:
        return None, False


def extract_entities(dxf_path: str) -> dict[str, Any]:
    """读取 DXF，返回 {units, entities, counts}。"""
    try:
        import ezdxf
        doc = ezdxf.readfile(dxf_path)
    except Exception:
        from ezdxf import recover
        doc, _auditor = recover.readfile(dxf_path)

    msp = doc.modelspace()
    units = doc.header.get("$INSUNITS", 0)

    entities: list[dict[str, Any]] = []
    n_direct = n_bbox = n_insert_fail = n_skip_geom = 0

    for e in msp:
        t = e.dxftype()
        if t == "INSERT":
            try:
                ext = bbox.extents([e], fast=False)
            except Exception:
                ext = None
            if ext is not None and ext.has_data:
                mn, mx = ext.extmin, ext.extmax
                entities.append({
                    "layer": e.dxf.layer or "0",
                    "kind": "INSERT_BBOX",
                    "pts": _round_pts([
                        (mn.x, mn.y), (mx.x, mn.y),
                        (mx.x, mx.y), (mn.x, mx.y), (mn.x, mn.y),
                    ]),
                    "closed": True,
                })
                n_bbox += 1
            else:
                n_insert_fail += 1
            continue
        if t not in _KEEP:
            continue
        pts, closed = _pts_of(e)
        if not pts or len(pts) < 2:
            n_skip_geom += 1
            continue
        entities.append({
            "layer": e.dxf.layer or "0",
            "kind": t,
            "pts": _round_pts(pts),
            "closed": bool(closed),
        })
        n_direct += 1

    return {
        "units": int(units or 0),
        "entities": entities,
        "counts": {
            "direct": n_direct,
            "insertBBox": n_bbox,
            "insertFail": n_insert_fail,
            "badGeometry": n_skip_geom,
        },
    }
