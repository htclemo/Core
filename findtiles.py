from PIL import Image
im = Image.open('core_the_project.png')
w,h = im.size
# Try to find any 256x256 that has some color variation and isn't just dark
for y in range(0, h-256, 128):
    for x in range(0, w-256, 128):
        crop = im.crop((x,y,x+256,y+256))
        # count unique colors
        colors = set(crop.convert('RGB').getdata())
        # count bright pixels
        bright = 0
        for p in crop.convert('RGB').getdata():
            if sum(p) > 200:
                bright += 1
        if bright > 100 or len(colors) > 1000:
            crop.save(f'C:/Users/Lemo/AppData/Local/Temp/opencode/tile_{x}_{y}.png')
            print(f'saved tile_{x}_{y} colors={len(colors)} bright={bright}')
