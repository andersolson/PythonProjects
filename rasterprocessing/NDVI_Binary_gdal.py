#---------------------------------------------------------------------------
# NDVI_Binary_gdal.py
#
# Author: Anders Olson
# Usage:  Requires gdal and python 3, run as stand-alone script.
#
# Description: Calculated a binary raster using a threshold value
#              from NDVI raster of NAIP 4-band imagery. Input is directory
#              to NAIP imagery downloaded from AWS. Output is a Binary image
#              for each tile from AWS
#
# ---------------------------------------------------------------------------

import os, sys
import numpy as np
from osgeo import gdal
from datetime import datetime as dt
import subprocess
import logging
import pathlib
from joblib import Parallel, delayed

##~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~##
#================================#
# Define functions
#================================#
##~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~##

'''
Summary:
Function that creates a path object for all desired file endings in a directory

Parameters:
fileEnding -- string for desired file ending e.g. '.tif'
directory  -- string location of the parent directory to search recursively

Returns:
fileLst  -- python list of files within the directory that match file ending
'''
def findFilePaths(fileEnding, directory):
    # Create a path object for the directory
    data_dir = pathlib.Path(directory)
    #print(data_dir)

    # Recursive search within directory for file endings
    myFiles = list(data_dir.rglob(fileEnding))
    #print(myFiles)
    return myFiles

'''
Summary:
Function that creates a list of ndvi file path names that need to have binary calculated

Parameters:
inLst    -- python list of wgs file path names
inPath   -- path location of wgs files to append to new list

Returns:
outLst  -- python list of all missing file path names
'''
def findNDVIPaths(lstInput):
    # Create a list of ndvi pathnames derived from wgs path name
    outLst = []
    for i in lstInput:
        # Isolate the basename of the file
        iName = i.stem

        # Create a new pathname from the stem
        ndviRas = r'W:\naip\2022\ca\cl_standard\ndvi\{0}_NDVI.tif'.format(iName)

        # Append ndvi pathname to a list and wgs pathname to a list
        outLst.append(ndviRas)
    #print(f'Found {len(outLst)} NDVI files.')

    return outLst

'''
Summary:
Search a directory and subdirectories iteratively for files that match a file ending. Write the pathnames of
matching files to a list.

Parameters:
fileEnding -- string format of the desired file ending/file extension. e.g. tif
directory  -- a directory location to search through iteratively
inLST      -- list variable receive the path locations of files

Returns:
inLST      -- a list with all file locations of files that match file ending
'''
def myFileLocations (fileEnding, directory, inLST):
    #Loop the directory and subdirectories for all input file endings and store them in a list
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(fileEnding):
                inLST.append(os.path.join(root, file))

'''
Summary:
Function that checks if a file paths from list already exists and returns a list of file paths that do not exist.

Parameters:
lstInput    -- python list of file path names

Returns:
missingLst  -- python list of all missing file path names
'''
def findMissing(lstInput):
    missingLst = []

    # Loop through list for pathnames
    for i in lstInput:
        # Check if image file already exists
        if not os.path.isfile(i):
            #print("\tImage is missing:\n\t{0}".format(i))
            missingLst.append(i)
        # else:
        #     print("\tFile already exists:\n\t{0}".format(i))

    print(f'Found {len(missingLst)} rasters to process.')

    return missingLst

'''
Summary:
Function that creates a list of wgs file path names that have not completed and need to have ndvi calculated

Parameters:
inLst    -- python list of NDVI missing file path names
inPath   -- path location of wgs files to append to new list

Returns:
outLst  -- python list of all missing file path names
'''
def missingWGS(inLst, inPath):
    outLst = []

    # Loop through input list of missing ndvi image files and store the original wgs image in a list
    for file in inLst:
        # Get the filename from the path and remove the 'NDVI' name ending
        fName = file.split('\\')
        name = (fName[-1].split('.', 1)[0])
        nameX = name[:-5]
        wgsPath = f'{inPath}\\{nameX}.tif'
        #print(wgsPath)
        outLst.append(wgsPath)

    print(f'{len(outLst)} WGS files ready to process.')

    return outLst

'''
Summary:
This function is called in the ndviCalc(imageIn, outDir) function. This function converts the numpy array with NDVI
values into a raster image

Parameters:
dataArray   -- an array of virtual raster with NDVI values
datasetPath -- file pathname of the output NDVI raster 
refDataset  -- a reference raster image for pulling cols, rows, sr, and geotransform information to create 
               the final output NDVI raster 

Returns:
datasetPath -- file pathname of the output NDVI raster 
'''
def saveRaster(dataArray,datasetPath,refDataset):
    cols = refDataset.RasterXSize
    rows = refDataset.RasterYSize
    projection   = refDataset.GetProjection()
    geotransform = refDataset.GetGeoTransform()

    #print(f"{cols}x{rows} :: {projection}")

    rasterSet = gdal.GetDriverByName('GTiff').Create(datasetPath,cols,rows,1,gdal.GDT_Float32)
    rasterSet.SetProjection(projection)
    rasterSet.SetGeoTransform(geotransform)
    rasterSet.GetRasterBand(1).WriteArray(dataArray)
    #rasterSet.GetRasterBand(1).SetNoDataValue(-9999)
    rasterSet = None

'''
Summary:
Calculates NDVI as an array using gdal virtual raster and numpy to create the array. Then saves the array as a raster.

Parameters:
imageIn   -- file pathname to input raster for NDVI calculation
outDir    -- directory location for output of all NDVI rasters

Returns:
ndvi_file -- output NDVI array, file pathname of the output
'''
def ndviCalc(imageIn, outDir):
    print(f'Calculating NDVI: {imageIn}')

    #Get the filename from the path
    fName = imageIn.split('\\')
    name  = (fName[-1].split('.', 1)[0])
    #print(name)

    vrtRed = f'{outDir}\\RED.vrt'
    vrtNIR = f'{outDir}\\NIR.vrt'

    # Create output options for BuildVRT: outputSRS, only bands Red and NIR bands default resampling is
    # nearest neighbor, the input has 0 defined as no data from the reprojection to wgs so vrt needs 0 too
    # redOptions = gdal.BuildVRTOptions(outputSRS='EPSG:4326', bandList=[1], srcNodata=0, VRTNodata=-9999)
    # nirOptions = gdal.BuildVRTOptions(outputSRS='EPSG:4326', bandList=[4], srcNodata=0, VRTNodata=-9999)
    redOptions = gdal.BuildVRTOptions(outputSRS='EPSG:4326', bandList=[1], srcNodata=0, VRTNodata=0)
    nirOptions = gdal.BuildVRTOptions(outputSRS='EPSG:4326', bandList=[4], srcNodata=0, VRTNodata=0)

    # Create a virtual raster of all selected tiles for county
    gdal.BuildVRT(vrtRed, imageIn, options=redOptions)
    gdal.BuildVRT(vrtNIR, imageIn, options=nirOptions)

    # Open VRT for Red and NIR raster bands
    redBand = gdal.Open(vrtRed)
    nirBand = gdal.Open(vrtNIR)

    # Read bands as matrix arrays in numpy
    red_Data = redBand.GetRasterBand(1).ReadAsArray().astype(np.float32)
    nir_Data = nirBand.GetRasterBand(1).ReadAsArray().astype(np.float32)

    # Suppress the warning division by zero 0/0 'invalid value encountered in true_divide'
    np.seterr(invalid='ignore')

    # Calculate NDVI values using array input for numpy, ignore areas where there will be division by zero
    #ndviBand = np.divide(nir_Data - red_Data, nir_Data + red_Data, where=(nir_Data - red_Data) != 0)
    ndviBand = np.divide(nir_Data - red_Data, nir_Data + red_Data)

    # Classify ndvi value 0 as 0
    #ndviBand[ndviBand == 0] = 0

    # Name the output NDVI image
    ndvi_file = f'{outDir}\{name}_NDVI.tif'
    #print(ndvi_file)

    # Save a ndvi raster tiff
    saveRaster(ndviBand, ndvi_file, redBand)

'''
Summary:
Function that converts the Geotiff binary from Float32 to 2-bit byte

Parameters:
inRas  -- filepath-name of reclassified Binary NDVI image
outRas -- filepath-name of the output binary raster image 

Returns:
outRas  -- filepath-name of the output binary raster image 
'''
def trans2Bit(inRas, outRas):

    # Creation options
    cOptions = ['NBITS=2']

    # Transformation options for converting temp raster into binary raster
    tOptions = gdal.TranslateOptions(format="GTiff", outputType="gdalconst.GDT_Byte", creationOptions=cOptions)

    # Create a binary raster with 2bit and
    gdal.Translate(outRas, inRas, options=tOptions)

'''
Summary:
Function that converts 'NaN' values to desired no data value

Parameters:
inRas  -- filepath-name of NDVI image
outRas -- filepath-name of the output NDVI image 

Returns:
outRas  -- filepath-name of the output binary raster image 
'''
def reclassNaN(inRas, outRas):

    # Calculate Binary and save raster as 2-bit with Byte type and no data = 3
    subprocess.call([sys.executable, r"C:\Users\andolson\AppData\Local\ESRI\conda\envs\ArcGDAL\Scripts\gdal_calc.py",
                     '-A', inRas, '--outfile', outRas, '--format=GTiff', '--co=COMPRESS=LZW', '--overwrite',
                     '--calc', r'nan_to_num(A, nan=3)', '--NoDataValue=3'])

'''
Summary:
Calculates Binary from NDVI by reclassifying pixels following this logic - 
if NDVI pixel value is >= 0.2 classify as 1, if NDVI pixel value is < 0.2 classify as zero

Parameters:
imageIn -- filepath location of NDVI image to be reclassified as binary
outDir  -- path directory of all the output binary rasters 

Returns:
binaryF -- file pathname of the output binary raster file
'''
def binaryCalc(imageIn, outDir):

    # Get the filename from the path and remove the 'NDVI' name ending
    fName = imageIn.split('\\')
    name = (fName[-1].split('.', 1)[0])
    nameX = name[:-5]

    # Name of the output binary file
    binaryF = f'{outDir}\{nameX}_Binary.tif'

    # Name of the output reclass Nan image
    nanImage = f'{outDir}\ReclassNan.tif'

    # Reclass Nan values as 3 for no data
    reclassNaN(inRas=imageIn, outRas=nanImage)

    # Calculate Binary and save raster as 2-bit with Byte type and no data = 3
    subprocess.call([sys.executable, r"C:\Users\andolson\AppData\Local\ESRI\conda\envs\ArcGDAL\Scripts\gdal_calc.py",
                     '-A', nanImage, '--outfile', binaryF, '--type=Byte', '--format=GTiff', '--co=COMPRESS=LZW',
                     '--co=NBITS=2', '--overwrite', '--calc', r'(A >= .2)*1 + (A < .2)*0',
                     '--NoDataValue=3'])

##~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~##
#================================#
# Define Local Variables
#================================#
##~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~##

# Start a timer
startTime = dt.now()

# Stop GDAL printing both warnings and errors to STDERR
gdal.PushErrorHandler('CPLQuietErrorHandler')

# Create a txt log
#logTxt = r'D:\Projects\WORKING\log_Binary_{}.txt'.format(startTime.strftime("%d-%m-%Y"))
logTxt = r'D:\Projects\WORKING\imagery\gdal\notes\log_Binary_{}.txt'.format(startTime.strftime("%d-%m-%Y"))

# Open log txt file for writing output messages
writeTo = open(logTxt,'w')

# Directory location for all source NAIP imagery.
# e.g.: wgsDir = r'W:\naip\2022\ca\source\tiles'
srcTiles = r'W:\naip\2022\ca\source\tiles'

# Directory location for all reprojected NAIP imagery (WGS84). Output from Batch_Projection_arcpy.py script.
# e.g.: wgsDir = r'W:\NAIP\CA\WFMS_2023_12\wgs_tile'
wgsDir   = r'W:\naip\2022\ca\standard\wgs_tile'

# Output directory for all ndvi images
# e.g.: ndviDir = r'W:\NAIP\CA\WFMS_2023_12\ndvi'
ndviDir  = r'W:\naip\2022\ca\standard\ndvi'

# Output directory for all binary tiff images
# e.g.: binDir = r'W:\NAIP\CA\WFMS_2023_12\binary'
binDir   = r'W:\naip\2022\ca\standard\binary'

##~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~##
#================================#
# Run code
#================================#
##~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~##

# Notify user and write to log
print("Start time: {0}".format(startTime))
writeTo.write("Start time: {0}\n".format(startTime))

# Find all filenames for wgs84 tif imagery and store in list
# e.g. 'W:\\NAIP_cl\\CA\\WFMS_2022_12\\wgs_tile\\m_4112064_nw_10_060_20200711.tif'
wgsImages = findFilePaths('*.tif', wgsDir)
#print(len(wgsImages))

# Create list of all ndvi path names derived from wgs pathname and store in a list
ndviPaths = findNDVIPaths(wgsImages)
#print(len(ndviPaths))

# Check if the ndvi image files already exists before running ndvi calculation and store to a list
missingFiles = findMissing(ndviPaths)
#print(len(missingFiles))

# Create a list of all wgs images that need to be run
wgsProcessLst = missingWGS(missingFiles,wgsDir)
#print(wgsProcessLst)
#print(len(wgsProcessLst))

# Report step message 1
print("1 of 2 - Calculate Raster NDVI...")
writeTo.write("1 of 2 - Calculate Raster NDVI...\n")

try:
    # Calculate NDVI image and save
    #result = Parallel(n_jobs=20)(delayed(ndviCalc)(tifPath,ndviDir) for tifPath in wgsProcessLst)
    Parallel(n_jobs=20, backend='threading')
    for tifPath in wgsProcessLst:
        # print(f'Calculating NDVI: {tifPath}')
        writeTo.write(f'Calculating NDVI: {tifPath}\n')
        ndviCalc(tifPath, ndviDir)
except Exception:
    logging.error('ERROR in NDVI calculation!')
    writeTo.write("ERROR in NDVI calculation!\n")
    exc_type, exc_value, exc_tb = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_tb)


# # Find all filenames for NDVI tif imagery and save to list
# # e.g. 'W:\\NAIP_cl\\CA\\WFMS_2022_12\\wgs_tile\\m_4112064_nw_10_060_20200711.tif'
# binImages = []
# myFileLocations('.tif', ndviDir, binImages)
#
# # Report step message 2
# print("2 of 2 - Calculate Binary from NDVI...")
# writeTo.write("2 of 2 - Calculate Binary from NDVI...\n")
#
# try:
#     # Calculate Binary image and save
#     for tifPath in binImages:
#         print(f'Calculating Binary: {tifPath}')
#         writeTo.write(f'Calculating Binary: {tifPath}\n')
#         binaryCalc(tifPath, binDir)
# except Exception:
#     logging.error('ERROR in binary calculation!')
#     writeTo.write("ERROR in binary calculation!\n")
#     exc_type, exc_value, exc_tb = sys.exc_info()
#     traceback.print_exception(exc_type, exc_value, exc_tb)


print("Complete! Total runtime: {0}".format(dt.now()-startTime))
writeTo.write("Complete! Total runtime: {0}".format(dt.now()-startTime))
writeTo.close()
