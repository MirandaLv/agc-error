#
# error.py
# original authors: Miranda Elliott, Alex Kappel
# purpose: compare autocoder accuracy with human geocoded data for overall dataset to given level of geographic detail
#
# user guide:
# - main file (actual locations) must be named "actual.csv" in root of country folder
# - comparison files (autogeocoded location) must exist in "alt" folder in root of country folder
# - all location coordinate csvs must have columns titled "latitude" and "longitude" (case sensitive)
# - shapefiles must be located in "shapefiles" folder in root of country folder
# - shapefile names must include adm# (eg: MWI_adm1.shp)
# - previous adm level shapefiles must be present (ie: adm1.shp must be included if you include adm2.shp)

import sys, os, time, copy
import csv, json
import shapefile
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Point, shape, box


# takes country name as input
# must match name of folder used for country
country = sys.argv[1]

base = os.path.dirname(os.path.realpath(__file__))
cbase = base +'/'+ country


# ---------------------------------------------
# Compute spatial counts

# returns dict with:
# dictionary with shapes as keys and the number of locations within them as values
# total count of points within shapes
# total count of points
def locsPerAdm(locFile, shapes):

    Tloc = time.time()

    if locFile.name.endswith(".csv"):
        delim = ','
    elif locFile.name.endswith(".tsv"):
        delim = '\t'
    else:
        sys.exit("Invalid File Extension")

    locs = csv.DictReader(locFile, delimiter=delim)

    countDict = {}
    rowIn = 0

    for shp in shapes:

        shp_obj = shape(shp)

        minx, miny, maxx, maxy = shp_obj.bounds
        bounding_box = box(minx, miny, maxx, maxy)

        if shp not in countDict:
            countDict[shp] = 0

        rowNum = 0

        for row in locs:

            rowNum += 1

            try:
                lon = float(row['longitude'])
                lat = float(row['latitude'])

            except ValueError:
                # print 'WARNING: (row ' + str(rowNum + 2) + ') does not have correct format (or existant) coordinates'
                lon = ''
                lat = ''

            if lon != '' and lat != '':

                curPoint = Point(lon, lat)

                if bounding_box.contains(curPoint):
                    if curPoint.within(shp_obj):
                        countDict[shp] += 1
                        rowIn += 1

        locFile.seek(0)


    Tloc = int(time.time() - Tloc)
    print '\t\tRuntime Loc: ' + str(Tloc//60) +'m '+ str(int(Tloc%60)) +'s'

    # locFile.seek(0)
    return countDict, rowIn, rowNum


# ---------------------------------------------
#  Compute error statistics

# returns quantity error
# quantity error = abs value of num geocoded locs - num autocoded locs
def calcQError(actualDict, predDict, shapes):
    itersum = 0
    for shp in shapes:
        itersum += (actualDict[shp] - predDict[shp])
    qError = abs(itersum)
    return qError

# returns allocation error
# allocation error = total error - quantity error
# total error = sum of abs value of num geocoded locs - num autocoded locs for each division at current adm level
def calcAError(actualDict, predDict, shapes, qError):
    tError = 0
    for shp in shapes:
        tError += abs(actualDict[shp] - predDict[shp])
    aError = tError - qError
    return aError


# ---------------------------------------------
# Main

if __name__ == '__main__':
    
    T = time.time()

    file_out = cbase + '/results/results_' + str(int(T)) + '.json'
    output = {
        "info":{
            "country": country,
            "time": int(T)
        },
        "files":{},
        "projects":{},
        "error":{},
        "runtime":{ 
            "sub":{},
            "total":0
        }
    }

    # human geocoded data
    output['files']['source'] = cbase + '/actual.csv'
    actualFile = open(output['files']['source'], 'r')
 

    # find all available shapefiles in "shapefiles" folder
    shp_folder = cbase + '/shapefiles'
    shp_list = [os.path.join(dirpath, f) for dirpath, dirnames, files in os.walk(shp_folder) for f in files if f.endswith('.shp')]
    shp_list.sort()

    # get comparison / autogeocoded data from "alt" folder
    data_folder = cbase + '/alt'
    data_list = [os.path.join(dirpath, f) for dirpath, dirnames, files in os.walk(data_folder) for f in files if f.endswith('.csv') or f.endswith('.tsv')]

    adm_lvl = 0

    # iterate over all available shapefiles
    for shp_file in shp_list:

        if adm_lvl != 3:

            Tadm = time.time()

            print 'Processing ADM level ' + str(adm_lvl) + '...'

            shp_handle = shapefile.Reader(shp_file)
            shapes = shp_handle.shapes()

            print '\tRunning actual'
            actualDict, actualIn, actualTotal  = locsPerAdm(actualFile, shapes)

            output['runtime']['sub']['adm'+str(adm_lvl)] = {}


            # iterate over comparison / autogeocoded data
            for data_file in data_list:

                name = "file_" + str(data_list.index(data_file))
                output['files'][name] = data_file
                print '\tRunning '+ name +' : '+ data_file[data_file.rfind('/')+1:-4]

                predFile = open(data_file, 'r')
                
                predDict, predIn, predTotal = locsPerAdm(predFile, shapes)

                predFile.close()


                if adm_lvl == 0:
                    output['projects']['source'] = {"country":actualIn, "total":actualTotal}
                    output['projects'][name] = {"country":predIn, "total":predTotal}

                    print '\tTotal geocoded locations (of total) inside ADM0:',actualIn,'/',actualTotal
                    print '\tTotal autocoded locations (of total) inside ADM0:',predIn,'/',predTotal


                # compute statistics
                qError = calcQError(actualDict, predDict, shapes)
                print '\tQuantity Error: ', qError

                aError = calcAError(actualDict, predDict, shapes, qError)
                print '\tAllocation Error: ', aError

                if not name in output['error']:
                    output['error'][name] = {}

                # output['error'][name]['adm'+str(adm_lvl)] = {"quantity":qError, "allocation":aError, "project":aError/2}
                prev_aError = 0
                if adm_lvl != 0:
                    prev_aError = output['error'][name]['adm'+str(adm_lvl-1)]['total_allocation']

                output['error'][name]['adm'+str(adm_lvl)] = {
                                                                "quantity":qError,
                                                                "total_allocation":aError,
                                                                "additional_allocation":aError-prev_aError,
                                                                "total_project":aError/2,
                                                                "additional_project":(aError-prev_aError)/2
                                                            }            
                                                 

            Tadm = int(time.time() - Tadm)
            output['runtime']['sub']['adm'+str(adm_lvl)][name] = Tadm
            print '\tRuntime - ADM'+str(adm_lvl)+': ' + str(Tadm//60) +'m '+ str(int(Tadm%60)) +'s'

            adm_lvl += 1

    # end shp_list loop


    T = int(time.time() - T)
    output['runtime']['total'] = T
    print 'Total Runtime: ' + str(T//60) +'m '+ str(int(T%60)) +'s'


    # check that results folder exists
    if not os.path.isdir(cbase+"/results"):
        os.mkdir(cbase+"/results")

    # open json for writing
    with open(file_out, 'w') as json_handle:
        # dump json back into file
        json.dump(output, json_handle, sort_keys = True, indent = 4, ensure_ascii=False)


    # build stacked bar chart

    plotColors = ("k","r","g","b","y","m","c")

    # number of comparison datasets
    N = len(data_list)

    # the x locations for the groups
    ind = np.arange(N)

    # the width of the bars: can also be len(x) sequence
    width = 0.35

    plotData = [0] * adm_lvl
    plotObject = [0] * adm_lvl
    plotCat = [0] * adm_lvl

    # create plot for each comparison dataset
    for i in range(0, adm_lvl):

        plotData[i] = [0] * N

        for j in range(0, N):
            
            if i == 0:
                plotCat[j] = 'A'+str(j)

                plotData[i][j] = output['error']['file_'+str(j)]['adm'+str(i)]['quantity']
            else:
                plotData[i][j] = output['error']['file_'+str(j)]['adm'+str(i)]['additional_allocation']

        # build bar
        if i == 0:
            plotObject[i] = plt.bar(ind, plotData[i], width, color=plotColors[i], edgecolor='k',linewidth=1)
        else:
            plotObject[i] = plt.bar(ind, plotData[i], width, color=plotColors[i], bottom=plotData[i-1], edgecolor='k',linewidth=1)

    xvals = ind+width/2.

    plt.title('Autogeocoder Error')
    plt.ylabel('Error (project count)')
    plt.xticks(xvals, plotCat )
    plt.xlim([min(xvals) - 0.5, max(xvals) + 0.5])

    # ymax=2000
    # plt.yticks(np.arange(0,ymax,ymax/10))

    # plt.legend( (p1[0], p2[0]), ('Men', 'Women') )

    plt.show()
