from PIL import Image
im = Image.open('core_the_project.png')
# Maybe the logo is in the center? Or maybe it's the whole image cropped differently
# Let me look at the actual image dimensions and try to find a square logo
# Common logo positions - top-left
# Or maybe it's in bottom area
crop = im.crop((100,800,400,1100))
crop.save('C:/Users/Lemo/AppData/Local/Temp/opencode/botleft.png')
# Right side
crop = im.crop((1100,700,1500,1100))
crop.save('C:/Users/Lemo/AppData/Local/Temp/opencode/botright.png')
print('done')
