from PIL import Image
im = Image.open('core_the_project.png')
w,h = im.size
for y in [0,100,200,300,400,500,600,700,800]:
    for x in [0,200,400,600,800,1000,1200]:
        crop = im.crop((x,y,min(x+150,w),min(y+150,h)))
        colors = crop.convert('RGB').getcolors(maxcolors=1000)
        if colors and len(colors) < 500:
            crop.save(f'C:/Users/Lemo/AppData/Local/Temp/opencode/small_{x}_{y}.png')
            print(f'saved small_{x}_{y} colors={len(colors)}')
