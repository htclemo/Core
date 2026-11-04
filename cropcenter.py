from PIL import Image
im = Image.open('core_the_project.png')
# Try to find by aspect ratio - square logo likely
# Sample center area
center = im.crop((400,200,1100,800))
center.save('C:/Users/Lemo/AppData/Local/Temp/opencode/center.png')
print('center saved')
