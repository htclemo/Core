from PIL import Image
im = Image.open('core_the_project.png')
# Crop leftmost part
for x in [0,50,100,150,200,250]:
    crop = im.crop((x,0,x+400,400))
    crop.save(f'C:/Users/Lemo/AppData/Local/Temp/opencode/v{x}.png')
    print(x)
