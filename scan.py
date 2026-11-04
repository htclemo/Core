from PIL import Image
im = Image.open('core_the_project.png').convert('RGBA')
w,h = im.size
# Look for regions with lots of non-transparent/colorful pixels
# Sample every 50 pixels
for y in range(0,h,100):
    for x in range(0,w,100):
        pixel = im.getpixel((x,y))
        if pixel[3] > 0 and pixel[0] < 50 and pixel[1] < 50 and pixel[2] < 50:
            print('dark at', x,y, pixel)
        elif pixel[3] > 0 and sum(pixel[:3]) > 600:
            print('bright at', x,y, pixel)
