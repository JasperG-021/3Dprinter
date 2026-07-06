import datetime
import svgpathtools
import sys


def svg_to_safe_curved_gcode(svg_file_path, gcode_file_path):
    # 1. 读取 SVG
    paths, attributes = svgpathtools.svg2paths(svg_file_path)
    gcode_lines = []

    # 2. 定义打印机的硬安全边界
    X_MIN, X_MAX = 36.0, 129.0
    Y_MIN, Y_MAX = 50.0, 143.0


    # G-code 初始化
    gcode_lines.append("G21;") #毫米单位
    gcode_lines.append("G90;") #绝对坐标
    gcode_lines.append("G0 Z10.0 F3000;") #抬笔

    travel_speed = 3000
    draw_speed = 1200
    pen_down_z = 3.0
    pen_up_z = 10.0

    # 3. 遍历 SVG 中的每一条独立路径（同时读取它的属性 attr）
    for path, attr in zip(paths, attributes):

        # 💡【核心过滤规则】：马克笔只能画线（stroke）。
        # 如果这个图形没有 stroke 属性，或者 stroke 是 none，说明它是 Figma 的背景框或填充怪，直接跳过！
        if 'stroke' not in attr or attr['stroke'] == 'none':
            continue

        is_path_start = True
        for path in paths:
            is_path_start = True

            for segment in path:
                num_segments = 20 if not isinstance(segment, svgpathtools.Line) else 1

                for i in range(num_segments + 1):
                    t = i / num_segments
                    point = segment.point(t)

                    # 💥【核心算法】：把 Figma 的 (0~93) 映射到打印机的安全区间，并翻转Y轴
                    printer_x = point.real + X_MIN
                    printer_y = Y_MAX - point.imag  # 143 - SVG_Y

                    # 🛡️【安全锁】：检查坐标是否越界
                    if not (X_MIN <= printer_x <= X_MAX) or not (Y_MIN <= printer_y <= Y_MAX):
                        print(f"❌ 危险！检测到坐标越界: X={printer_x:.2f}, Y={printer_y:.2f}")
                        print(f"允许范围: X({X_MIN}~{X_MAX}), Y({Y_MIN}~{Y_MAX})")
                        print("程序已紧急终止，未生成 G-code。请检查 Figma 画布里的线条是否超出了 Frame！")
                        sys.exit(1)  # 强行退出程序

                    # 写入坐标
                    if is_path_start:
                        gcode_lines.append(f"G0 X{printer_x:.3f} Y{printer_y:.3f} Z{pen_up_z} F{travel_speed}")
                        gcode_lines.append(f"G1 Z{pen_down_z} F500")
                        is_path_start = False
                    else:
                        gcode_lines.append(f"G1 X{printer_x:.3f} Y{printer_y:.3f} Z{pen_down_z} F{draw_speed}")

            gcode_lines.append(f"G0 Z{pen_up_z} F3000 ; 抬笔")

        gcode_lines.append("M2 ; 结束")

    # 保存文件
    with open(gcode_file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(gcode_lines))
    print(f"✅ 安全检查通过！G-code 已成功限制在安全区并输出至: {gcode_file_path}")

# --- 测试运行 ---
file_date = str(datetime.datetime.today()).split()[0].replace('-', '')
svg_file = "/Users/jasperg/Documents/Codes/Python/3Dprinter/resources/test_20260706.svg"
gcode_file = "/Users/jasperg/Documents/Codes/Python/3Dprinter/gcode_result/test_"+file_date+".gcode"
# print(gcode_file)
svg_to_safe_curved_gcode(svg_file, gcode_file)