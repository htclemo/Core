from PIL import Image
im = Image.open('core_the_project.png').convert('RGBA')
w,h = im.size
# Find regions that are NOT dark background
# Dark background seems to be around (0,0,0) to (30,30,30)
for y in range(0,h,50):
    for x in range(0,w,50):
        p = im.getpixel((x,y))
        # if it's bright/colorful, not dark bg
        if sum(p[:3]) > 100 and p[3] > 0:
            print(f'bright at {x},{y}: {p}')
