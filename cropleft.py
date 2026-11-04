from PIL import Image
im = Image.open('core_the_project.png')
# Look for the largest connected non-background region
# Try different crop strategies - the logo might be on left side
# Just crop left portion
left = im.crop((0,0,700,1024))
left.save('C:/Users/Lemo/AppData/Local/Temp/opencode/left.png')
print('left saved')
