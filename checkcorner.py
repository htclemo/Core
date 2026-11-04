from PIL import Image
im = Image.open('core_the_project.png')
w,h = im.size
# Just look at corners and edges more
# Top-left
crop = im.crop((0,0,200,200))
crop.save('C:/Users/Lemo/AppData/Local/Temp/opencode/corner_tl.png')
# Check if it's just black
pixels = list(crop.convert('RGB').getdata())
black = sum(1 for p in pixels if sum(p) < 50)
print('tl black:', black, 'total:', len(pixels))
