from PIL import Image
im = Image.open('core_the_project.png').convert('RGBA')
print(im.size)
