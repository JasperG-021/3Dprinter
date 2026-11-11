"""生成一笔画蛇形（弓字形）G-code，直线之间用相切半圆连接。"""

import math

x_min = 35.0
y_min = 49.0
x_max = 123.0
y_max = 139.0


def generate_serpentine_gcode(
    output_file="serpentine_heater_test.gcode",
    center_x=(x_min + x_max) / 2.0,  # 不含引线的蛇形主体中心 X (mm)
    center_y=(y_min + y_max) / 2.0,  # 不含引线的蛇形主体中心 Y (mm)
    spacing_d=2.0,       # 相邻平行直线的中心间距 (mm)
    trace_width=50.0,    # 每行直线段长度 (mm)，两侧半圆额外各占 d/2
    rows=12,            # 平行直线数量；偶数时两端在同侧，奇数时在相对两侧
    step_length=1.0,    # 最大采样步长 (mm)，圆弧额外加密
    lead_length=8.0,    # 首尾各自向主体外侧延伸的引线长度 (mm)
    safe_z=50.0,        # 全局避障高度 (mm)
    pen_up_z=5.0,       # 局部提笔高度 (mm)
    pen_down_z=-0.5,    # 落笔高度 (mm)，实画时按实际笔尖高度调整
    travel_speed=3000,  # 空移速度 (mm/min)
    plunge_speed=400,   # 落笔速度 (mm/min)
    draw_speed=400,     # 画线速度 (mm/min)
    load_mesh=False,    # 是否载入 Klipper 的 default heightmap
    rotation_deg=0.0,   # 绕主体中心逆时针旋转角度；90 度为竖向折返
):
    """写出 G-code 并返回 XY 路径点；主体高度为 (rows-1)*spacing_d。"""
    for name, value in (("spacing_d", spacing_d), ("trace_width", trace_width),
                        ("step_length", step_length), ("travel_speed", travel_speed),
                        ("plunge_speed", plunge_speed), ("draw_speed", draw_speed)):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} 必须为有限正数")
    if isinstance(rows, bool) or not isinstance(rows, int) or rows < 2:
        raise ValueError("rows 必须为至少 2 的整数")
    if not math.isfinite(lead_length) or lead_length < 0:
        raise ValueError("lead_length 必须为有限非负数")
    if not all(math.isfinite(v) for v in
               (center_x, center_y, rotation_deg, safe_z, pen_up_z, pen_down_z)):
        raise ValueError("坐标、角度和高度必须为有限数")
    if not safe_z >= pen_up_z > pen_down_z:
        raise ValueError("高度必须满足 safe_z >= pen_up_z > pen_down_z")

    half_width = trace_width / 2.0
    half_height = (rows - 1) * spacing_d / 2.0
    arc_radius = spacing_d / 2.0
    local_points = [(-half_width - lead_length, -half_height)]

    def add_line(end):
        start = local_points[-1]
        distance = math.dist(start, end)
        if distance == 0:
            return
        steps = max(1, math.ceil(distance / step_length))
        for i in range(1, steps + 1):
            t = i / steps
            local_points.append((start[0] + (end[0] - start[0]) * t,
                                 start[1] + (end[1] - start[1]) * t))

    add_line((-half_width, -half_height))
    arc_steps = max(16, math.ceil(math.pi * arc_radius / (step_length * 0.5)))
    for row in range(rows):
        y = -half_height + row * spacing_d
        direction = 1 if row % 2 == 0 else -1
        end_x = direction * half_width
        add_line((end_x, y))
        if row == rows - 1:
            add_line((end_x + direction * lead_length, y))
            break
        # 右端向右鼓出，左端向左鼓出；首尾切线均与直线一致。
        for i in range(1, arc_steps + 1):
            angle = math.pi * i / arc_steps
            local_points.append((end_x + direction * arc_radius * math.sin(angle),
                                 y + arc_radius * (1.0 - math.cos(angle))))

    angle = math.radians(rotation_deg)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    path_points = [(center_x + x*cos_a - y*sin_a,
                    center_y + x*sin_a + y*cos_a) for x, y in local_points]
    total_trace_length = sum(math.dist(a, b) for a, b in zip(path_points, path_points[1:]))
    xs, ys = zip(*path_points)
    print("=" * 50)
    print("蛇形折返加热图案生成完毕！")
    print(f"  - 中心坐标: ({center_x}, {center_y}) mm；旋转: {rotation_deg} 度")
    print(f"  - 直线段: {rows} 行，每行 {trace_width} mm；行间距: {spacing_d} mm")
    print(f"  - 折返半圆半径: {arc_radius} mm；主体高度: {2 * half_height} mm")
    print(f"  - 实际 XY 坐标范围: X[{min(xs):.1f} ~ {max(xs):.1f}], Y[{min(ys):.1f} ~ {max(ys):.1f}]")
    print(f"  - 导电迹线总长度 (L): {total_trace_length:.1f} mm ({total_trace_length/10:.1f} cm)")
    print(f"  - 离散坐标点总数: {len(path_points)} 个")
    print("=" * 50)

    # 5. 输出 G-code 文件
    gcode = [
        "; === Serpentine Heater G-code ===",
        f"; Center=({center_x},{center_y}), Spacing={spacing_d}mm, Rows={rows}",
        f"; Straight Width={trace_width}mm, Rotation={rotation_deg}deg",
        f"; Total Trace Length = {total_trace_length:.2f} mm",
        "G21 ; 毫米单位",
        "G90 ; 绝对坐标"
    ]
    if load_mesh:
        gcode.append("BED_MESH_PROFILE LOAD=default ; 载入曲面网格补偿")

    gcode.append(f"G0 Z{safe_z:.3f} F1500 ; 抬升至全局避障高度")

    # 移动到起点上方并落笔
    start_x, start_y = path_points[0]
    gcode.append(f"G0 X{start_x:.3f} Y{start_y:.3f} F{travel_speed}")
    gcode.append(f"G0 Z{pen_up_z:.3f} F1500")
    gcode.append(f"G1 Z{pen_down_z:.3f} F{plunge_speed} ; 落笔")

    # 一笔画连续走刀
    for x, y in path_points[1:]:
        gcode.append(f"G1 X{x:.3f} Y{y:.3f} Z{pen_down_z:.3f} F{draw_speed}")

    # 结束抬笔复位
    gcode.append(f"G0 Z{pen_up_z:.3f} F1500")
    gcode.append(f"G0 Z{safe_z:.3f} F1500")
    gcode.append(f"G0 X10 Y170 F{travel_speed} ; 退回停机位")
    gcode.append("M2")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(gcode))
    print(f"✅ G-code 文件已保存至: {output_file}")

    return path_points


if __name__ == "__main__":
    generate_serpentine_gcode()
