from PIL import Image
im = Image.open('core_the_project.png')
w,h = im.size
# Look for any small region that's not mostly dark
for y in range(0,h,100):
    for x in range(0,w,100):
        crop = im.crop((x,y,min(x+200,w),min(y+200,h)))
        # count bright pixels
        bright = 0
        for py in range(0,200,10):
            for px in range(0,200,10):
                if x+px < w and y+py < h:
                    p = crop.getpixel((px,py))
                    if sum(p[:3]) > 150:
                        bright += 1
        if bright > 10:
            print(f'bright region at {x},{y}: {bright}')
            crop.save(f'C:/Users/Lemo/AppData/Local/Temp/opencode/bright_{x}_{y}.png')
