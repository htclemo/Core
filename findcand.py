from PIL import Image
im = Image.open('core_the_project.png')
# The bright area at bottom right might be logos? Or maybe the whole image is just the logo I need
# But user says 'inside this image are many images' - could it be a collage
# Let me look at the full image differently - maybe the actual logo is small and centered
# Or maybe I need to find a perfect square logo
# Try to find a square region with high contrast
for size in [256, 200, 128]:
    for y in range(0,h-size,20):
        for x in range(0,w-size,20):
            crop = im.crop((x,y,x+size,y+size))
            # count non-black pixels
            nonblack = 0
            for py in range(size):
                for px in range(size):
                    p = crop.getpixel((px,py))
                    if sum(p[:3]) > 50:
                        nonblack += 1
            if nonblack > size*size*0.3:  # more than 30% non-black
                crop.save(f'C:/Users/Lemo/AppData/Local/Temp/opencode/cand_{size}_{x}_{y}.png')
                print(f'candidate {size}x{size} at {x},{y} nonblack={nonblack}')
