install qgis
install OSGeo4W64

# In OSGeo4W shell

#Download mrsid from kartverket

# Translate to geotiff
gdal_translate -co COMPRESS=JPEG -co TILED=YES 33_N250.sid 33_N250.tif

# Build vrt
gdalbuildvrt mosaic.vrt 33_N250.tif

gdalbuildvrt.exe mosaic.vrt map.tif
c:\OSGeo4W64\apps\Python37\python.exe -z 5-13 c:\OSGeo4W64\apps\Python37\Scripts\gdal2tiles.py mosaic_bergen.vrt bergen

# Optional retile, but I'm not sure if this is very useful.
# gdal_retile.py -v -r bilinear -levels 4 -ps 2048 2048 -co "TILED=YES" -co "COMPRESS=JPEG" -targetDir /maps mosaic.vrt

# Generate xyz.  There is a parallel version of this, but I do not have it installed
gdal2tiles.py mosaic.vrt /maps/tiled

# Inside WSL
1. sudo apt install gdal-bin
2. gdalbuildvrt -addalpha tiles.vrt *.tiff
3. gdal2tiles.py tiles.vrt tiled