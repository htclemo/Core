from PIL import Image
im = Image.open('core_the_project.png').convert('RGBA')
gray = im.convert('L')
w,h = gray.size
min_x=w;max_x=0;min_y=h;max_y=0
for y in range(h):
    for x in range(w):
        v = gray.getpixel((x,y))
        if v < 200:
            if x<min_x:min_x=x
            if x>max_x:max_x=x
            if y<min_y:min_y=y
            if y>max_y:max_y=y
print(min_x,min_y,max_x,max_y)
