from PIL import Image
im = Image.open('core_the_project.png')
# Maybe the logo is smaller and centered?
# Or maybe I need to look at it differently - could be the 'CORE' text as logo
# Try to find text/logo by looking for connected bright areas
# Crop around bright spots
# Bright at 850,750 is (23,250,171) - teal/green
crop = im.crop((600,500,1100,900))
crop.save('C:/Users/Lemo/AppData/Local/Temp/opencode/teal_area.png')
print('done')
