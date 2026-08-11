
import svgpathtools
import sys


def create_gcode(svg_file_path, gcode_file_path):
    # 用来存储 G-code 的每一行
    gcode_lines = []

    # 定义边界
    X_MIN, X_MAX = 36.0, 129.0
    Y_MIN, Y_MAX = 50.0, 143.0

    # 初始化打印机
    gcode_lines.append("G21;") #毫米单位
    gcode_lines.append("G90;") #绝对坐标
    gcode_lines.append("G0 Z10.0 F3000;") #抬笔

    travel_speed = 3000     # 空移速度 (mm/min)
    draw_speed = 1200       # 画线速度 (mm/min)
    pen_down_z = 3.0        # 落笔高度
    pen_up_z = 10.0         # 抬笔高度

    # 读取SVG
    paths, attributes = svgpathtools.svg2paths(svg_file_path)
    # paths 存所有的几何线条
    # attributes 存这些线条的属性（颜色、宽度等）

    # print(paths)
    # print("----------")
    # print(attributes)

    # 使用 zip 同时遍历路径和属性
    for path, attr in zip(paths, attributes):
        # print("----------")
        # print(path)
        # print(attr)
        # print("----------")

        # 排除没有 stroke 属性的路径，通常这是背景，不需要绘制
        if 'stroke' not in attr:
            continue

        is_path_start = True

        for segment in path:    # 将每条路径分解为线段或曲线段
            # print(f"Segment: {segment}")
            num_segments = 20 if not isinstance(segment, svgpathtools.Line) else 1
            # 3D 打印机不会走贝塞尔曲线，只能走直线。
            # 如果是直线，直接取起点和终点（离散化分段数为 1）
            # 如果是曲线，强制把它均匀切成 20 个极小的微直线段，实现近似曲线

            for i in range(num_segments + 1):   # +1 是为了包含终点
                t = i / num_segments            # t 是参数化的线段位置，范围从 0 到 1
                point = segment.point(t)        # 获取线段上对应 t 的点，返回一个复数，实部是 x 坐标，虚部是 y 坐标
                printer_x = point.real + X_MIN
                printer_y = Y_MAX - point.imag  # 143 - SVG_Y

                # 检查坐标是否越界
                if not (X_MIN <= printer_x <= X_MAX) or not (Y_MIN <= printer_y <= Y_MAX):
                    print(f"❌ X={printer_x:.2f}, Y={printer_y:.2f}")
                    print(f"允许范围: X({X_MIN}~{X_MAX}), Y({Y_MIN}~{Y_MAX})")
                    sys.exit(1) # 终止程序，返回错误码 1

                # 写入坐标
                # :.3f 保留 3 位小数
                if is_path_start:   # 如果是路径的起点，先抬笔移动到起点，再落笔开始绘制
                    gcode_lines.append(f"G0 X{printer_x:.3f} Y{printer_y:.3f} Z{pen_up_z} F{travel_speed}")
                    gcode_lines.append(f"G1 Z{pen_down_z} F500")
                    is_path_start = False
                else:
                    gcode_lines.append(f"G1 X{printer_x:.3f} Y{printer_y:.3f} Z{pen_down_z} F{draw_speed}") # 绘制线条

    gcode_lines.append(f"G0 Z{pen_up_z} F{travel_speed};")                      # 结束抬笔
    gcode_lines.append(f"G0 X10 Y170 Z{pen_up_z} F{travel_speed};")     # 回到安全位置
    gcode_lines.append("M2;")                                                   # 结束

    # 保存文件
    with open(gcode_file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(gcode_lines))
    print("✅")