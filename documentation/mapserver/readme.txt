https://github.com/geo-data/mapserver-docker
#Download mrsid from kartverket

# Translate to geotiff
gdal_translate -co COMPRESS=JPEG -co TILED=YES /maps/33_N250.sid 33_N250.tif

# Build vrt
gdalbuildvrt mosaic.vrt 33_N250.tif

# Optional retile, but I'm not sure if this is very useful.
# gdal_retile.py -v -r bilinear -levels 4 -ps 2048 2048 -co "TILED=YES" -co "COMPRESS=JPEG" -targetDir /maps mosaic.vrt

# Generate xyz.  There is a parallel version of this, but I do not have it installed
gdal2tiles.py mosaic.vrt /maps/tiled