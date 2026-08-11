import datetime
from codes.svg_to_gcode import create_gcode

file_date = str(datetime.datetime.today()).split()[0].replace('-', '')
svg_file = "resources/for_test.svg"
gcode_file = "gcode_result/test_"+file_date+".gcode"
# print(gcode_file)
create_gcode(svg_file, gcode_file)