import datetime
from svg_to_gcode_v1 import svg_to_safe_curved_gcode

file_date = str(datetime.datetime.today()).split()[0].replace('-', '')
svg_file = "resources/Frame_1.svg"
gcode_file = "gcode_result/test_"+file_date+".gcode"
# print(gcode_file)
svg_to_safe_curved_gcode(svg_file, gcode_file)