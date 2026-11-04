from PIL import Image
im = Image.open('core_the_project.png').convert('RGBA')
# Look for a square logo - probably in top-left or has specific characteristics
# Try to find by edge detection - get all pixels with alpha > 0
w,h = im.size
# Find the region with highest density of non-transparent pixels
best = (0,0,0,0,0)
for cy in range(0,h-200,50):
    for cx in range(0,w-200,50):
        count = 0
        for dy in range(200):
            for dx in range(200):
                if cx+dx < w and cy+dy < h:
                    p = im.getpixel((cx+dx,cy+dy))
                    if p[3] > 10:
                        count += 1
        if count > best[4]:
            best = (cx,cy,cx+200,cy+200,count)
print('best 200x200 at', best)
# Try different sizes
best = (0,0,0,0,0)
for size in [150,180,200,220,250,300]:
    for cy in range(0,h-size,30):
        for cx in range(0,w-size,30):
            count = 0
            for dy in range(0,size,5):
                for dx in range(0,size,5):
                    if cx+dx < w and cy+dy < h:
                        p = im.getpixel((cx+dx,cy+dy))
                        if p[3] > 10:
                            count += 1
            if count > best[4]:
                best = (cx,cy,cx+size,cy+size,count)
print('best by density:', best)
