import re
import math
import sys

def generate_draw_gcode_from_log(probe_log_file, draw_gcode_file):
    # === 工艺参数配置 ===
    safe_z = 90.0            # 全局进退场避障高度[cite: 2]
    pen_up_offset = 3.0      # 抬笔时，相对当前陶瓷表面抬高 3mm[cite: 2]
    pen_down_offset = 2.0   # 落笔画线时，相对测得的表面下压 2mm（建议先改成 +2.0 空跑测试！）
    
    travel_speed = 3000      # 空移速度 (mm/min)[cite: 2]
    plunge_speed = 400       # 落笔速度 (mm/min)[cite: 2]
    draw_speed = 400         # 画线速度 F=400 (mm/min)
    
    fine_step = 1.0          # 画线细分步长：在两个测高点之间每 1mm 插值一个 3D 点[cite: 2]

    # 1. 读取你的 probe_log.txt
    with open(probe_log_file, 'r', encoding='utf-8') as f:
        log_text = f.read()

    # 2. 精准提取 "Result: at X,Y estimate contact at z=Z" 的最终平均值[cite: 1]
    pattern = r'Result: at ([0-9.\-]+),([0-9.\-]+) estimate contact at z=([0-9.\-]+)'
    matches = re.findall(pattern, log_text)

    if not matches:
        print("❌ 未能在日志中找到 Result 数据，请检查文件内容！")
        sys.exit(1)

    pts_3d = [(float(x), float(y), float(z)) for x, y, z in matches]
    print(f"✅ 成功从日志中提取到 {len(pts_3d)} 个轨迹点的 3D 坐标：")
    for idx, (x, y, z) in enumerate(pts_3d):
        print(f"  点 {idx:2d}: X={x:7.3f}, Y={y:7.3f}, Z={z:9.6f}")

    # 3. 如果有多个独立笔画，可根据相邻点距离自动分段（距离 > 10mm 视为换笔画）
    strokes = []
    current_stroke = [pts_3d[0]]
    for i in range(1, len(pts_3d)):
        prev_x, prev_y, _ = pts_3d[i - 1]
        curr_x, curr_y, _ = pts_3d[i]
        if math.hypot(curr_x - prev_x, curr_y - prev_y) > 10.0:
            strokes.append(current_stroke)
            current_stroke = [pts_3d[i]]
        else:
            current_stroke.append(pts_3d[i])
    strokes.append(current_stroke)

    # 4. 生成 3D 曲面画线 G-code
    gcode = [
        "G21",
        "G90",
        "BED_MESH_CLEAR ; 清除任何残留网格补偿，完全依靠实测 3D 坐标走刀",
        f"G0 Z{safe_z:.3f} F1500 ; 抬升至安全避障高度"
    ]

    for stroke in strokes:
        start_x, start_y, start_z = stroke[0]
        # 移动到起点上方
        gcode.append(f"G0 X{start_x:.3f} Y{start_y:.3f} F{travel_speed}")
        gcode.append(f"G0 Z{start_z + pen_up_offset:.3f} F1500 ; 降至起点上方 3mm")
        
        # 落笔
        gcode.append(f"G1 Z{start_z + pen_down_offset:.3f} F{plunge_speed}")

        # 沿轨迹线性插值加密走刀
        for i in range(len(stroke) - 1):
            x0, y0, z0 = stroke[i]
            x1, y1, z1 = stroke[i + 1]
            
            seg_dist = math.hypot(x1 - x0, y1 - y0)
            steps = max(1, math.ceil(seg_dist / fine_step))
            
            for s in range(1, steps + 1):
                t = s / steps
                ix = x0 + (x1 - x0) * t
                iy = y0 + (y1 - y0) * t
                iz = (z0 + (z1 - z0) * t) + pen_down_offset
                gcode.append(f"G1 X{ix:.3f} Y{iy:.3f} Z{iz:.3f} F{draw_speed}")

        # 当前笔画结束，抬笔
        end_z = stroke[-1][2]
        gcode.append(f"G0 Z{end_z + pen_up_offset:.3f} F1500")
        gcode.append(f"G0 Z{safe_z:.3f} F1500")

    gcode.append(f"G0 X10 Y170 F{travel_speed} ; 退回停机位")
    gcode.append("M2")

    with open(draw_gcode_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(gcode))

    print(f"\n🎉 3D 画线文件已生成：{draw_gcode_file}")

if __name__ == '__main__':
    generate_draw_gcode_from_log('/workspaces/3Dprinter/codes/new_things_test/probe_log.txt', '/workspaces/3Dprinter/codes/new_things_test/2_draw_path.gcode')