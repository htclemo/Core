from PIL import Image
im = Image.open('core_the_project.png')
# Maybe the logo is the one in the top area? Or maybe I need to look at the actual image
# Let me just save the whole image and look at it differently
# Or maybe the logo is small - let me look at 0-300,0-300 again but see actual pixels
crop = im.crop((0,0,300,300))
# Save as is
crop.save('C:/Users/Lemo/AppData/Local/Temp/opencode/tl300.png')
# Get unique colors
from collections import Counter
c = Counter(crop.convert('RGB').getdata())
for k,v in c.most_common(15):
    print(k, v)
