from PIL import Image
im = Image.open('core_the_project.png')
# Maybe the logo is in a specific position - look at the actual image structure
# Try cropping from different angles
# Sometimes logos are on the left with text on right
crop = im.crop((0,0,800,1024))
crop.save('C:/Users/Lemo/AppData/Local/Temp/opencode/left800.png')
# Middle
crop = im.crop((400,0,900,1024))
crop.save('C:/Users/Lemo/AppData/Local/Temp/opencode/mid500.png')
print('done')
