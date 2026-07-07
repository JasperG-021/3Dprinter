import svgpathtools
import sys

def svg_to_safe_curved_gcode(svg_file_path, gcode_file_path):
    # 读取SVG
    paths, attributes = svgpathtools.svg2paths(svg_file_path)
    gcode_lines = []

    # 定义边界
    X_MIN, X_MAX = 36.0, 129.0
    Y_MIN, Y_MAX = 50.0, 143.0

    # 初始化打印机
    gcode_lines.append("G21;")  #毫米单位
    gcode_lines.append("G90;")  #绝对坐标
    gcode_lines.append("G0 Z10.0 F3000;") #抬笔

    travel_speed = 3000         # 空移速度 (mm/min)
    draw_speed = 1200           # 画线速度 (mm/min)
    pen_down_z = 3.0            # 落笔接触面的 Z 轴高度
    pen_up_z = 10.0             # 提笔悬空的 Z 轴高度

    #1 遍历 SVG 中的每一条独立路径
    for path in paths:
        is_path_start = True

        # 遍历路径中的每一个线段 
        for segment in path:
            num_segments = 20 if not isinstance(segment, svgpathtools.Line) else 1
            for i in range(num_segments + 1):
                t = i / num_segments
                point = segment.point(t)
            # 把Figma画好的SVG范围(0~93)映射到打印机的安全区间。
            printer_x = point.real + X_MIN
            # 由于Figma与3D打印机的Y轴是反的，所有需要翻转Y轴
            # 143 - SVG_Y
            printer_y = Y_MAX - point.imag

            # 检查坐标是否越界
            if not (X_MIN <= printer_x <= X_MAX) or not (Y_MIN <= printer_y <= Y_MAX):
                print(f"❌ 检测到坐标越界: X={printer_x:.2f}, Y={printer_y:.2f}")
                print(f"允许范围: X({X_MIN}~{X_MAX}), Y({Y_MIN}~{Y_MAX})")
                sys.exit(1)
            
            # 写入坐标
            if is_path_start:
                gcode_lines.append(f"G0 X{printer_x:.3f} Y{printer_y:.3f} Z{pen_up_z} F{travel_speed}")
                gcode_lines.append(f"G1 Z{pen_down_z} F500")
                is_path_start = False
            else:
                gcode_lines.append(f"G1 X{printer_x:.3f} Y{printer_y:.3f} Z{pen_down_z} F{draw_speed}")
                    
        # 结束当前路径
        gcode_lines.append(f"G0 Z{pen_up_z} F3000;") #结束此段，抬笔

    gcode_lines.append("M2;") #程序结束

    # 保存文件
    with open(gcode_file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(gcode_lines))
    print("✅")