import math

x_min = 40.0             # 热床左下角 X 坐标 (mm)
y_min = 40.0             # 热床左下角 Y 坐标 (mm)
x_max = 133.0            # 热床右上角 X 坐标 (mm)
y_max = 135.0            # 热床右上角 Y 坐标 (mm)

output_file="bifilar_heater_test_concave.gcode"

safe_z=90.0          # 进退场避障安全高度 (mm)
def generate_bifilar_spiral_gcode(
    center_x=(x_min + x_max) / 2.0,       # 线圈中心在热床上的 X 坐标 (mm)
    center_y=(y_min + y_max) / 2.0,       # 线圈中心在热床上的 Y 坐标 (mm)
    spacing_d=2.0,        # 相邻两根线的中心间距 d (mm) = 笔宽 + 安全间隙
    turns=3.5,            # 入程旋转圈数 N (至少 0.75；回程少半圈)
    step_length=1.0,      # 离散步长 (mm)：每 1mm 生成一个 G1 点，适配曲面与匀速
    lead_length=8.0,      # 最外圈正负极引出脚的长度 (mm)，方便夹鳄鱼夹
    # --- 打印机高度与速度参数 ---
    pen_up_z=5.0,         # 局部提笔高度 (mm)
    pen_down_z=-0.5,       # 落笔高度 (mm) -> ⚠️ 首次测试设为 +2.0 悬空观察，实画改为 0.0 或 -2.0
    travel_speed=3000,    # 空移速度 (mm/min)
    plunge_speed=400,     # 落笔速度 (mm/min)
    draw_speed=400,       # 画线速度 (mm/min)
    load_mesh=False,      # 是否在开头自动载入 Klipper 的 default heightmap
    center_arc_radius=1,  # 中心 S 弯的半圆半径 (mm)
):
    # 回程约少半圈，两端位于同一侧，沿径向方向平行引出。
    if not all(math.isfinite(v) and v > 0 for v in (spacing_d, step_length)):
        raise ValueError("spacing_d 和 step_length 必须为有限正数")
    if not math.isfinite(turns) or turns < 0.75:
        raise ValueError("turns 必须为有限数且至少为 0.75 圈，以容纳中心过渡与半圈回程差")
    if not math.isfinite(lead_length) or lead_length < 0:
        raise ValueError("lead_length 必须为有限非负数")

    # S 弯由两个半圆组成，连接点位于圆心左右 2R 处。
    # 同时将两条螺旋向外移，为放大的 S 弯留出空间。
    r_turn = 2.0 * center_arc_radius
    b = spacing_d / math.pi
    theta_max = turns * 2.0 * math.pi

    def radius_and_slope(theta):
        # 用三次过渡在中心保持圆弧切线，并额外留出 0.1d 的径向余量。
        # 避免旧过渡在首个半圈少增长半径，挤压 S 弯与外侧螺旋的间距。
        transition = math.pi / 2.0
        extra = 0.1 * spacing_d
        if theta < transition:
            t = theta / transition
            rise = b * transition + extra
            r = r_turn + rise * (3*t*t - 2*t*t*t) + b * transition * (t*t*t - t*t)
            slope = rise / transition * (6*t - 6*t*t) + b * (3*t*t - 2*t)
            return r, slope
        return r_turn + b * theta + extra, b

    def spiral_points(end_theta, phase):
        points = []
        theta = 0.0
        while True:
            r, _ = radius_and_slope(theta)
            angle = theta + phase
            points.append((center_x + r * math.cos(angle),
                           center_y + r * math.sin(angle)))
            if theta >= end_theta:
                return points
            # 限制角步长，避免粗步长跳过中心的圆滑过渡。
            next_r, _ = radius_and_slope(min(end_theta, theta + 0.1))
            theta = min(end_theta, theta + min(
                0.1, step_length / math.hypot(next_r, 2.0 * b)))

    # 回程端点略超出入程端点的角度，进入外圈端点之后的空隙。
    # 令横向偏移 r*sin(delta)=d，避免径向引线重叠或穿过外圈。
    delta_low, delta_high = 0.0, math.pi / 2.0
    for _ in range(60):
        delta = (delta_low + delta_high) / 2.0
        end_r, _ = radius_and_slope(theta_max - math.pi + delta)
        if end_r * math.sin(delta) < spacing_d:
            delta_low = delta
        else:
            delta_high = delta
    out_theta_max = theta_max - math.pi + (delta_low + delta_high) / 2.0
    in_points = list(reversed(spiral_points(theta_max, 0.0)))
    out_points = spiral_points(out_theta_max, math.pi)

    # 引线方向取圆心指向入程外端的方向，不再沿螺旋切线延伸。
    lead_angle = theta_max
    lead_dx, lead_dy = math.cos(lead_angle), math.sin(lead_angle)
    lead_steps = max(1, int(math.ceil(lead_length / step_length)))
    path_points = []
    if lead_length > 0:
        for i in range(lead_steps, 0, -1):
            distance = lead_length * i / lead_steps
            path_points.append((in_points[0][0] + lead_dx * distance,
                                in_points[0][1] + lead_dy * distance))
    path_points.extend(in_points)

    # 两个反向半圆构成 S 弯：(+r, 0) -> (0, 0) -> (-r, 0)。
    # 起终点切线均向下，匹配盘入和盘出方向；中点切线向上。
    arc_radius = center_arc_radius
    arc_steps = max(16, int(math.ceil(math.pi * arc_radius / (step_length * 0.5))))
    for i in range(1, arc_steps + 1):
        phi = -math.pi * i / arc_steps
        path_points.append((center_x + arc_radius + arc_radius * math.cos(phi),
                            center_y + arc_radius * math.sin(phi)))
    for i in range(1, arc_steps + 1):
        phi = math.pi * i / arc_steps
        path_points.append((center_x - arc_radius + arc_radius * math.cos(phi),
                            center_y + arc_radius * math.sin(phi)))
    path_points.extend(out_points[1:])

    if lead_length > 0:
        for i in range(1, lead_steps + 1):
            distance = lead_length * i / lead_steps
            path_points.append((out_points[-1][0] + lead_dx * distance,
                                out_points[-1][1] + lead_dy * distance))

    # 4. 统计图案几何尺寸与总走线长度 (用于估算电阻)
    total_trace_length = sum(
        math.hypot(path_points[i][0] - path_points[i-1][0], path_points[i][1] - path_points[i-1][1])
        for i in range(1, len(path_points))
    )
    max_radius, _ = radius_and_slope(theta_max)
    xs = [p[0] for p in path_points]
    ys = [p[1] for p in path_points]

    print("=" * 50)
    print(f"🌀 双螺旋折返加热线圈生成完毕！")
    print(f"  - 中心坐标: ({center_x}, {center_y}) mm")
    print(f"  - 线中心距 (d): {spacing_d} mm")
    print(f"  - 中心 S 弯: 半圆半径 {arc_radius:.2f} mm，宽 {4 * arc_radius:.2f} mm，高 {2 * arc_radius:.2f} mm")
    print(f"  - 螺旋外径 (直径): {max_radius * 2:.1f} mm")
    print(f"  - 实际 XY 坐标范围: X[{min(xs):.1f} ~ {max(xs):.1f}], Y[{min(ys):.1f} ~ {max(ys):.1f}]")
    print(f"  - 导电迹线总长度 (L): {total_trace_length:.1f} mm ({total_trace_length/10:.1f} cm)")
    print(f"  - 离散坐标点总数: {len(path_points)} 个")
    print("=" * 50)

    # 5. 输出 G-code 文件
    gcode = [
        "; === Bifilar Spiral Heater G-code ===",
        f"; Center=({center_x},{center_y}), Spacing={spacing_d}mm, Turns={turns}",
        f"; Center S Arc Radius = {arc_radius:.3f} mm",
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

if __name__ == "__main__":
    generate_bifilar_spiral_gcode()