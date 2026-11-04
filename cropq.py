from PIL import Image
im = Image.open('core_the_project.png')
# Try to find the main logo by looking for high contrast circular/square regions
# Save quadrants
w,h = im.size
for i,(sx,sy,ex,ey) in enumerate([(0,0,w//2,h//2),(w//2,0,w,h//2),(0,h//2,w//2,h),(w//2,h//2,w,h)]):
    crop = im.crop((sx,sy,ex,ey))
    crop.save(f'C:/Users/Lemo/AppData/Local/Temp/opencode/q{i}.png')
    print(i, sx,sy,ex,ey, crop.size)
