#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Trasforma gli hdf5 della precipitazione istantanea del composito radar
su dominio italiano in grib2 (lat/lon regolare o griglia ruotata di
cosmo).
"""

import os, numpy as np
import argparse
import h5py
import pyproj
from osgeo import gdal, osr
from datetime import datetime, timedelta

from eccodes import (
    codes_grib_new_from_samples,
    codes_grib_new_from_file,
    codes_get_double,
    codes_get_long,
    codes_set_key_vals,
    codes_set_values,
    codes_write,
    codes_release,
)

import warnings
warnings.filterwarnings("ignore")

# Valori missing costanti
#rmiss_grib = 9999. #-0.1 #9999.
imiss = 255

component_flag = 0  # int CONSTANT

def get_args():
    parser = argparse.ArgumentParser(
        description="Programma per la conversione dei file di precipitazione istantanea da hdf5 a grib2.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter )

    parser.add_argument( "-i", "--input_file", dest="inputfile",
                         required=True, help="File di input, required" )
    parser.add_argument( "-g", "--lhn_grid", dest="griglia",
                         required=True, help="Griglia di output [icon, cosmo], required" )
    parser.add_argument( "-t", "--grib_template", dest="gribtemplate",
                         required=False, help="Template grib per l'output, optional" )
    parser.add_argument( "-o", "--output_file", dest="outputfile",
                         required=False, help="File di output, optional" )
    parser.add_argument( "-d", "--output_dir", dest="outputdir",
                         required=False, help="Directory di output, optional" )
    parser.add_argument( "-q", "--quality", dest="q_thr", type=float,
                         required=False, help="Quality threshold for data mask, optional" )
    parser.add_argument( "-m", "--missing", dest="rmiss", type=float, default=-0.1, 
                         required=False, help="Missing value for grib, default = -0.1" )

    args = parser.parse_args()

    return args

def adj_lon(lon):
    # aggiusta la lon da grib2 a Greenwich-centrica
    return lon - 360. if lon > 180. else lon

def get_objects(name, obj):
    # Funzione per leggere le lat/lon dall'hdf del DPC
    if 'where' in name:
        return obj
        
def radar_hdf52grib(filein, griglia, rmiss_grib, gribtemplate=None, fileout=None, dirout=None, q_thr=None):
    if griglia == "icon":
        if gribtemplate is not None:
            gaid_template = codes_grib_new_from_file(open(gribtemplate, "r"))
            gp = codes_get_double(gaid_template, "generatingProcessIdentifier")
            centre = codes_get_long(gaid_template, "centre")
        else:
            gaid_template = codes_grib_new_from_samples("regular_ll_sfc_grib2")
            gp = 1 # boh?
            centre = 80
    elif griglia == "cosmo":
        if gribtemplate is not None:
            gaid_template = codes_grib_new_from_file(open(gribtemplate, "r"))
            bounds = (adj_lon(codes_get_double(gaid_template, "longitudeOfFirstGridPointInDegrees")),
                      codes_get_double(gaid_template, "latitudeOfFirstGridPointInDegrees"),
                      adj_lon(codes_get_double(gaid_template, "longitudeOfLastGridPointInDegrees")),
                      codes_get_double(gaid_template, "latitudeOfLastGridPointInDegrees"))
            width = codes_get_long(gaid_template, "Ni")
            height = codes_get_long(gaid_template, "Nj")
            latsp = codes_get_double(gaid_template, "latitudeOfSouthernPoleInDegrees")
            lonsp = codes_get_double(gaid_template, "longitudeOfSouthernPoleInDegrees")
            gp = codes_get_double(gaid_template, "generatingProcessIdentifier")
            centre = codes_get_long(gaid_template, "centre")
        else: # cosmo 2I
            gaid_template = codes_grib_new_from_samples("rotated_ll_sfc_grib2")
            bounds = (-3.8, -8.5, 7.7, 5.5)
            width = 576
            height = 701
            latsp = -47.
            lonsp = 10.
            gp = 10
            centre = 80

    try:
        datafile = os.path.basename(filein).replace("SRI_", "").split(".", 1)[0].split("-")

        if q_thr is not None:
            # Leggo gain e offset per conversione dato raw di qualità
            f = h5py.File(filein,'r')
            qattr = {}
            group = f["dataset1/data1/quality1/what"]
            for key, value in group.attrs.items():
                qattr[key] = value
            gain = qattr.get("gain")
            offset = qattr.get("offset")
            print(gain, offset)
            f.close()

            qual_ds = gdal.Open(f'HDF5:"{filein}"://dataset1/data1/quality1/data')

        # Estraggo il dataset completo dal file hdf
        ds = gdal.Open(f'HDF5:"{filein}"://dataset1/data1/data')
        data_arr = ds.GetVirtualMemArray()
        print(data_arr.min(), data_arr.max())
        # Estrazione dei parametri della proiezione
        prj=ds.GetProjection()
        ds_converter = osr.SpatialReference() # makes an empty spatial ref object
        ds_converter.ImportFromWkt(prj) # populates the spatial ref object with our WKT SRS
        ds_forPyProj = ds_converter.ExportToProj4()  
        #print( "Input proj = ",ds_forPyProj )
        print(type(rmiss_grib), rmiss_grib)

        if griglia == "icon":
            # Genero le opzioni di input/output della proiezione
            # (in questo caso lat/lon regolare)
            radarDPC_warp_options = {
                'dstSRS': 'EPSG:4326',  # EPSG di destinazione
                'srcSRS': ds_forPyProj, # EPSG di partenza
                'format': 'VRT',
                'width': data_arr.shape[1],
                'height': data_arr.shape[0],
                'copyMetadata': True,
                'srcNodata': -9999.,
                'outputType': gdal.GDT_Float64,
                'dstNodata': rmiss_grib,
                'resampleAlg': 'near',
            }
            qualityDPC_warp_options = {
                'dstSRS': 'EPSG:4326',  # EPSG di destinazione
                'srcSRS': ds_forPyProj, # EPSG di partenza
                'format': 'VRT',
                'width': data_arr.shape[1],
                'height': data_arr.shape[0],
                'copyMetadata': True,
                'srcNodata': 0,
                'dstNodata': 0,
                'resampleAlg': 'near',
            }
        elif griglia == "cosmo":
            # Genero le opzioni di input/output della proiezione
            # per proiettare il radar del DPC sulla griglia COSMO.
            # Imposto i parametri per la pipelne di warping
            radarDPC_warp_options = {
                'dstSRS': 'EPSG:4326', # EPSG di destinazione
                'coordinateOperation': ("+proj=pipeline" # proj pipeline fatta da vari step 
                                        " +step +inv +proj=tmerc +lat_0=42.0 +lon_0=12.5 +ellps=WGS84 +units=m"  # 1) inverto la proiezione Trasverse marcator metrica del radar DPC e passo a lon/lat
                                        f" +step +proj=ob_tran +o_proj=latlon +o_lon_p=0 +o_lat_p={-latsp} +lon_0={lonsp}"  # 2) applico traformazione obliqua per traslare sulle coordinate equatoriali della griglia COSMO
                                        " +step +proj=unitconvert +xy_in=rad +xy_out=deg"  # 3) converto radianti in gradi
                                        " +step +proj=axisswap +order=2,1"),  # 4) scambio lon/lat -> lat/lon
    # 5) forzo la mappa risultante ad avere gli stessi limiti geografici e la stessa risoluzione della griglia COSMO (di conseguenza verrà effettuato un resampling)
                'outputBounds': bounds,
                'width': width,
                'height': height,
                'format': 'VRT',
                'copyMetadata': True,
                'srcNodata': -9999.,
                'outputType': gdal.GDT_Float64,
                'dstNodata': rmiss_grib,
                'resampleAlg': 'bilinear',
            }

        data = gdal.Warp( '', ds,
                          options = gdal.WarpOptions(**radarDPC_warp_options) )


        # Estraggo le informazioni geografiche dal dataset riproiettato
        geotransform = data.GetGeoTransform()
        lonFirst = geotransform[0]
        latLast = geotransform[3]
        mesh_dx = geotransform[1]
        mesh_dy = geotransform[5]
       
        rastr = data.ReadAsArray()
        #print(rastr.shape[0],rastr.shape[1])

        if q_thr is not None:
            qual_data = gdal.Warp( '', qual_ds,
                                   options = gdal.WarpOptions(**qualityDPC_warp_options) )
            qual_rastr = qual_data.ReadAsArray()*gain + offset
            print(qual_rastr.min(), qual_rastr.max()) 
            mask = ( qual_rastr < q_thr )

        prate = rastr.copy()
        # Dove il dato non è missing lo trasformo in kg m-2 s-1
        # come codificato in grib
        #mask = ( rastr != rmiss_grib )
        #prate[ mask ] = prate[ mask ] / 3600.

        if q_thr is not None:
            prate[ mask ] = rmiss_grib
            print(prate.min(), prate.max())
        # Calcolo gli estremi mancanti
        lonLast = lonFirst + (rastr.shape[1] * mesh_dx )
        latFirst = latLast + (rastr.shape[0] * mesh_dy )
        #print( lonFirst, lonLast )
        #print( latFirst, latLast )
        
        """
        =======================================================================
        SCRITTURA DEL GRIB
        =======================================================================
        """
        
        if fileout is None:
            if q_thr is not None:
                fileout = "radar_SRI_{}{}{}{}{}_q{}.grib2".format( datafile[2], datafile[1],
                                                                   datafile[0], datafile[3],
                                                                   datafile[4], int(q_thr) )
            else:
                fileout = "radar_SRI_{}{}{}{}{}.grib2".format( datafile[2], datafile[1],
                                                               datafile[0], datafile[3],
                                                               datafile[4] )
        print("Output file = {}".format(fileout))

        if dirout is None:
            fout = open(fileout, "wb")
        else:
            fout = open(os.path.join(dirout, fileout), "wb")

        # Definizione della griglia e del formato degli incrementi
        if griglia == "icon":
            iincr = abs(mesh_dx)
            jincr = abs(mesh_dy)
            # RAD_PRECIP - Radar Precipitation
            pc = 15  # parameterCategory
            pn = 195 # parameterNumber
            discipline = 0 # discipline
        elif griglia == "cosmo":
            iincr = float( "{:.2f}".format( abs(mesh_dx) ) )
            jincr = float( "{:.2f}".format( abs(mesh_dy) ) )
            # TP - Total Precipitation
            pc = 15 # 1 # parameterCategory
            pn = 195 # 8 # parameterNumber
            discipline = 0 # discipline

        key_map_grib = {
            "generatingProcessIdentifier": gp,
            "centre": centre,
            "missingValue": rmiss_grib,
            "packingType": "grid_simple",
            "bitmapPresent": 1,
            "resolutionAndComponentFlags": 0,
            "topLevel": 0,         # l1
            "bottomLevel": imiss,  # l2
            "iDirectionIncrement": "MISSING",
            "jDirectionIncrement": "MISSING",
            "iDirectionIncrementInDegrees": iincr,
            "jDirectionIncrementInDegrees": jincr,
            "significanceOfReferenceTime": 3,     # VIRGI
            "productionStatusOfProcessedData": 0, # VIRGI
            "typeOfProcessedData": 0, # [Analysis products]
            #"forecastTime": 0,
            # Istante di emissione del dato
            "year": datafile[2],
            "month": datafile[1],
            "day": datafile[0],
            "hour": datafile[3],
            "minute": datafile[4],
            "parameterCategory": pc,
            "parameterNumber": pn,
            "discipline": discipline, 
            "shapeOfTheEarth": 1, 
            "scaleFactorOfRadiusOfSphericalEarth": 2, 
            "scaledValueOfRadiusOfSphericalEarth": 637099700, 
            "productDefinitionTemplateNumber": 0,
            "typeOfFirstFixedSurface": 1,
            "scaleFactorOfFirstFixedSurface": 0,
            "scaledValueOfFirstFixedSurface": 0,
        }
       
        codes_set_key_vals(gaid_template, key_map_grib)

        if griglia == "icon":
            codes_set_key_vals(
                gaid_template,
                {
                    "typeOfGrid": "regular_ll",
                    "Ni": rastr.shape[1],  # nx
                    "Nj": rastr.shape[0],  # ny
                    "longitudeOfFirstGridPointInDegrees": lonFirst, # xmin (loFirst)
                    "longitudeOfLastGridPointInDegrees": lonLast, # xmax (loLast)
                    "latitudeOfFirstGridPointInDegrees": latFirst, # ymin (laFirst)
                    "latitudeOfLastGridPointInDegrees": latLast, # ymax (laLast)
                    "scanningMode": 64,
                    "uvRelativeToGrid": component_flag,
                },
            )
        elif griglia == "cosmo":
            codes_set_key_vals(
                gaid_template,
                {
                    "typeOfGrid": "rotated_ll",
                    "Ni": rastr.shape[1],  # nx
                    "Nj": rastr.shape[0],  # ny
                    #"jScansPositively": 1, # 0
                    "longitudeOfFirstGridPointInDegrees": lonFirst, # xmin (loFirst)
                    "longitudeOfLastGridPointInDegrees": lonLast, # xmax (loLast)
                    "latitudeOfFirstGridPointInDegrees": latFirst, # ymin (laFirst)
                    "latitudeOfLastGridPointInDegrees": latLast, # ymax (laLast)
                    "scanningMode": 64,
                    "uvRelativeToGrid": component_flag,
                    "latitudeOfSouthernPoleInDegrees": latsp,
                    "longitudeOfSouthernPoleInDegrees": lonsp,
                    "angleOfRotationInDegrees": 0,
                },
            )
            
        # Scrivo il precipitation rate in kg m-2 s-1
        pr_mm = np.flip(prate, 0)

        codes_set_values(gaid_template, pr_mm.flatten())

        codes_write(gaid_template, fout)
        codes_release(gaid_template)
        fout.close()

    except OSError:
        print("Cannot open {}".format(filein))
        print("Probabile file mancante.")


def main():
    args = get_args()

    inputfile = args.inputfile
    griglia = args.griglia
    rmiss_grib = args.rmiss

    radar_hdf52grib( inputfile, griglia, rmiss_grib, args.gribtemplate, args.outputfile, args.outputdir, args.q_thr )


if __name__ == "__main__":
    main()

    quit()
