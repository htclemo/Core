from PIL import Image
im = Image.open('core_the_project.png')
# Crop top-left area where dense is
crop = im.crop((0,0,400,400))
crop.save('C:/Users/Lemo/AppData/Local/Temp/opencode/topleft.png')
crop = im.crop((0,0,512,512))
crop.save('C:/Users/Lemo/AppData/Local/Temp/opencode/topleft512.png')
# Try other corners
crop = im.crop((1136,0,1536,400))
crop.save('C:/Users/Lemo/AppData/Local/Temp/opencode/topright.png')
print('done')
