from PIL import Image
im = Image.open('core_the_project.png')
w,h = im.size
for size in [256, 200, 128]:
    for y in range(0,h-size,20):
        for x in range(0,w-size,20):
            crop = im.crop((x,y,x+size,y+size))
            nonblack = 0
            for py in range(size):
                for px in range(size):
                    p = crop.getpixel((px,py))
                    if sum(p[:3]) > 50:
                        nonblack += 1
            if nonblack > size*size*0.3:
                crop.save(f'C:/Users/Lemo/AppData/Local/Temp/opencode/cand_{size}_{x}_{y}.png')
                print(f'candidate {size}x{size} at {x},{y} nonblack={nonblack}')
