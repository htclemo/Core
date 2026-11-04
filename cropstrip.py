from PIL import Image
im = Image.open('core_the_project.png')
# Look at left side more - there might be a logo around 0-200 x
# Crop a vertical strip
crop = im.crop((0,200,400,800))
crop.save('C:/Users/Lemo/AppData/Local/Temp/opencode/leftmid.png')
# Look at specific areas
crop = im.crop((0,400,300,700))
crop.save('C:/Users/Lemo/AppData/Local/Temp/opencode/left400.png')
print('done')
