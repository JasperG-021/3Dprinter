import svgpathtools
import math
import json

def generate_probe_gcode(svg_file, probe_gcode_file, path_cache_file):
    # === 1. 坐标映射范围与参数配置 ===
    X_MIN, Y_MAX = 35.0, 147.0   # 图案偏移基准
    safe_z = 90.0                # 跨区域安全避障高度[cite: 1]
    local_hop_z = 5.0            # 同一条线相邻测点之间的微抬高度（测完抬起5mm去下一点）
    travel_speed = 3000          # XY 空移速度[cite: 1]
    
    probe_step = 3.0             # 测高采样步长：沿轨迹每隔 3mm 测一个点[cite: 5]

    paths, attributes = svgpathtools.svg2paths(svg_file) # 读取 SVG 路径[cite: 1]
    
    gcode = [
        "G21",
        "G90",
        "BED_MESH_CLEAR ; 清除任何残留的 Heightmap 补偿",
        f"G0 Z{safe_z} F1500 ; 抬升至安全高度"
    ]
    
    all_strokes = []  # 保存离散后的轨迹结构，供第二步生成画线 G-code 使用
    point_index = 0

    for path, attr in zip(paths, attributes):
        if 'stroke' not in attr:
            continue
            
        # 将单条连续路径按 probe_step (3mm) 离散化为测高控制点
        stroke_points = []
        total_len = path.length()
        num_pts = max(1, math.ceil(total_len / probe_step))
        
        for i in range(num_pts + 1):
            pt = path.point(i / num_pts)
            px = round(pt.real + X_MIN, 3)
            py = round(Y_MAX - pt.imag, 3)
            # 避免相邻完全重合的点重复探测
            if not stroke_points or (px != stroke_points[-1][0] or py != stroke_points[-1][1]):
                stroke_points.append([px, py])
                
        if not stroke_points:
            continue
            
        all_strokes.append(stroke_points)

        # 生成该笔画的探测 G-code
        for idx, (px, py) in enumerate(stroke_points):
            if idx == 0:
                # 笔画起点：从安全高度移过去，再降到可探测高度（如你清楚大致高度可先降到接近位置）
                gcode.append(f"G0 Z{safe_z} F1500")
                gcode.append(f"G0 X{px:.3f} Y{py:.3f} F{travel_speed}")
            else:
                # 同一笔画相邻点：只需在上一测点基础上相对抬高 local_hop_z (5mm) 即可平移，极省时间
                gcode.append("G91 ; 相对坐标模式")
                gcode.append(f"G0 Z{local_hop_z} F1500")
                gcode.append("G90 ; 回到绝对坐标模式")
                gcode.append(f"G0 X{px:.3f} Y{py:.3f} F{travel_speed}")
                
            gcode.append(f"M118 POINT_ID={point_index} ; 标记当前点序号")
            gcode.append("PROBE ; 单点测高")
            point_index += 1

    gcode.append(f"G0 Z{safe_z} F1500 ; 探测结束，抬升回安全高度")
    gcode.append(f"G0 X10 Y170 F{travel_speed}")
    gcode.append("M2")

    # 保存探测 G-code
    with open(probe_gcode_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(gcode))
        
    # 保存轨迹点坐标缓存，供第二步对齐使用
    with open(path_cache_file, 'w', encoding='utf-8') as f:
        json.dump(all_strokes, f)

    print(f"✅ 探测文件已生成：{probe_gcode_file}，共需探测 {point_index} 个轨迹点。")

if __name__ == '__main__':
    generate_probe_gcode('/workspaces/3Dprinter/resources/for_test.svg', '/workspaces/3Dprinter/codes/new_things_test/1_probe_path.gcode', '/workspaces/3Dprinter/codes/new_things_test/path_cache.json')