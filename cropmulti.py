from PIL import Image
im = Image.open('core_the_project.png')
# Try different crops
# Maybe top portion
top = im.crop((0,0,1536,400))
top.save('C:/Users/Lemo/AppData/Local/Temp/opencode/top.png')
# Bottom
bottom = im.crop((0,600,1536,1024))
bottom.save('C:/Users/Lemo/AppData/Local/Temp/opencode/bottom.png')
# Left side full height
left = im.crop((0,0,600,1024))
left.save('C:/Users/Lemo/AppData/Local/Temp/opencode/left2.png')
# Right side
right = im.crop((900,0,1536,1024))
right.save('C:/Users/Lemo/AppData/Local/Temp/opencode/right.png')
print('done')
