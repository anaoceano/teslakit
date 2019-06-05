#!/usr/bin/env python
# -*- coding: utf-8 -*-

#common
import time
import sys
import os
import os.path as op
from datetime import datetime, timedelta
import threddsclient
import signal

# pip
import numpy as np
import netCDF4 as nc4
import xarray as xr


# TODO: FIND BUG AND FIX
wrn = '''
CSIRO data will be extracted and stored month by month.

--> if download is unstable or stops:
    -> inside folders "gridded.tmp" or "spec.tmp" find the monthly netCDF4 files
    -> kill python CSIRO data downloader process
    -> Check if last downloaded month is corrupted: manually remove it
    -> restart download (will resume from first missing month)

'''
print(wrn)

def signal_handler(signum, frame):
    raise Exception("Timed out!")

def Generate_URLs(switch_db='gridded', grid_code='pac_4m'):
    '''
    Generate URL list for downloading csiro gridded/spec data
    switch_db = gridded / spec
    grid_code = 'pac_4m', 'pac_10m', 'aus_4m', 'aus_10m', 'glob_24m'

    returns list of URLs with monthly CSIRO data
    '''

    # parameters
    url_catg = 'http://data-cbr.csiro.au/thredds/catalog/catch_all/CMAR_CAWCR-Wave_archive/'
    url_dodsC = 'http://data-cbr.csiro.au/thredds/dodsC/catch_all/CMAR_CAWCR-Wave_archive/'
    url_a = 'CAWCR_Wave_Hindcast_aggregate/'

    # mount URLs
    if switch_db == 'gridded':
        # get data available inside gridded catalog
        url_xml = '{0}{1}gridded/catalog.xml'.format(url_catg, url_a)
        cat = threddsclient.read_url(url_xml)
        down_ncs = sorted([f.name for f in cat.flat_datasets()])
        down_ncs = [x for x in down_ncs if grid_code in x]  # filter grid

        l_urls = ['{0}{1}gridded/{2}'.format(
            url_dodsC, url_a, nn) for nn in down_ncs]

    elif switch_db == 'spec':
        # get data available inside spec catalog
        url_xml = '{0}{1}spec/catalog.xml'.format(url_catg, url_a)
        cat = threddsclient.read_url(url_xml)
        down_ncs = sorted([f.name for f in cat.flat_datasets()])

        l_urls = ['{0}{1}spec/{2}'.format(
            url_dodsC, url_a, nn) for nn in down_ncs]

    return l_urls

def Download_Gridded_Area(p_ncfile, lonq, latq, grid_code='glob_24m'):
    '''
    Download CSIRO gridded data and stores it on netcdf format
    lonq, latq: longitude latitude query: single value or limits
    grid_code = 'aus_4m', 'aus_10m', 'glob_24m', 'pac_4m', 'pac_10m'

    returns xarray.Dataset
    xds_CSIRO_gridded:
        (time, latitude, longitude) var_name_1
        (time, latitude, longitude) var_name_2
        ...
        (time, latitude, longitude) var_name_N
    '''

    # def aux function
    def getrfile(u, p_nc):
        'download unstable gridded files'
        min_timeout = 30

        while not op.isfile(p_nc):
            try:
                # we limit time available for operation
                signal.signal(signal.SIGALRM, signal_handler)
                signal.alarm(min_timeout*60)   # min*60 seconds

                # read file from url
                with xr.open_dataset(u) as xds_u:
                    xds_temp = xds_u.isel(
                        longitude=slice(idx1,idx2+1),
                        latitude=slice(idy1,idy2+1))
                    # save temp file
                    xds_temp.to_netcdf(p_nc,'w')

            except Exception:
                # clean failed download and retry
                if op.isfile(p_nc):
                    os.remove(p_nc)
                print('timed out. retry... ',end=' ')
                sys.stdout.flush()
            except:
                # clean failed download and retry
                if op.isfile(p_nc):
                    os.remove(p_nc)
                print('failed. retry... ',end=' ')
                sys.stdout.flush()

            finally:
                signal.alarm(0)

    # long, lat query
    lonp1 = lonq[0]
    latp1 = latq[0]
    lonp2 = lonq[-1]
    latp2 = latq[-1]

    # Generate URL list 
    l_urls = Generate_URLs('gridded', grid_code)

    # find gridded-data-format split position, split lists
    pos_split =['201306' in x for x in l_urls].index(True)
    l_urls_a = l_urls[pos_split:]
    l_urls_b = l_urls[:pos_split]

    # get coordinates from first file
    with xr.open_dataset(l_urls[0]) as ff:
        idx1 = (np.abs(ff.longitude.values - lonp1)).argmin()
        idy1 = (np.abs(ff.latitude.values - latp1)).argmin()
        idx2 = (np.abs(ff.longitude.values - lonp2)).argmin()
        idy2 = (np.abs(ff.latitude.values - latp2)).argmin()

    # temp folder
    p_tmp = op.join(p_ncfile.replace('.nc','.tmp'))
    p_tmp_b = op.join(p_tmp, 'b201305')
    p_tmp_a = op.join(p_tmp, 'a201305')
    [os.makedirs(pp) for pp in [p_tmp, p_tmp_b, p_tmp_a] if not op.isdir(pp)]


    # download data from files
    print('downloading CSIRO gridded data... {0} files'.format(len(l_urls)))
    for u in l_urls_b:
        p_u_tmp = op.join(p_tmp_b, op.basename(u))

        print(op.basename(u), ' ... ', end='')
        sys.stdout.flush()
        getrfile(u, p_u_tmp)
        print('downloaded.')

    for u in l_urls_a:
        p_u_tmp = op.join(p_tmp_a, op.basename(u))

        print(op.basename(u), ' ... ', end='')
        sys.stdout.flush()
        getrfile(u, p_u_tmp)
        print('downloaded.')

    # join .nc files in one file
    xds_out_1 = Join_NCs(p_tmp_b, p_ncfile.replace('.nc', '_before_201305.nc'))
    xds_out_2 = Join_NCs(p_tmp_a, p_ncfile.replace('.nc', '_after_201305.nc'))

    return xds_out_1, xds_out_2

def Download_Spec_Point(p_ncfile, lon_p, lat_p):
    '''
    Download CSIRO spec data and stores it on netcdf format
    lon_p, lat_p: longitude latitude point query

    returns xarray.Dataset
    xds_CSIRO_spec:
        (time, frequency, direction) Efth
    '''

    # days chunk size
    ch_days = 11

    # Generate URL list 
    l_urls = Generate_URLs('spec')

    # get output time limits and efth attributes
    with xr.open_dataset(l_urls[0]) as ff:
        t1 = ff.time[0].values  # time ini
        efth_attrs = ff['Efth'].attrs  # var attrs
    with xr.open_dataset(l_urls[-1]) as lf:
        t2 = lf.time[-1].values  # time end

    # mount output time array
    out_time = np.arange(t1, t2, timedelta(hours=1))

    # get nearest station ID from first file
    with nc4.Dataset(l_urls[0], 'r') as ff:
        slons = ff['longitude'][0,:]
        slats = ff['latitude'][0,:]

        # TODO: DIST DIFERENTE PARA LON LATITUDE
        station_ix = (
            np.sqrt(np.square(slats-lat_p)+np.square(slons-lon_p))
        ).argmin()

        lon_station = slons[station_ix]
        lat_station = slats[station_ix]

        print('station ix: {0}. Longitude: {1}, Latitude: {2}'.format(
            station_ix, lon_station, lat_station
        ))

        # store frequency and direction
        frequency = ff['frequency'][:]
        direction = ff['direction'][:]

    # temp folder
    p_tmp = op.join(p_ncfile.replace('.nc','.tmp'))
    if not op.isdir(p_tmp):
        os.makedirs(p_tmp)

    # download data from files
    print('downloading CSIRO spec data... {0} files'.format(len(l_urls)))
    for u in l_urls:
        print(op.basename(u))

        # local downloaded file
        p_u_tmp = op.join(p_tmp, op.basename(u))
        if op.isfile(p_u_tmp):
            continue

        # read file from url
        # TODO: INTRODUCIR TRY/CATCH PARA BORRAR ARCHIVO INCOMPLETO
        with xr.open_dataset(u) as xds_u:
            u_time = xds_u.time.values[:]
            vn_efth = 'Efth' if 'Efth' in xds_u.variables else 'efth'

            # generate temp holder 
            xds_temp = xr.Dataset(
                {
                    'Efth':(
                        ('time','frequency','direction'),
                        np.nan * np.ones((
                            len(u_time),
                            len(frequency),
                            len(direction)
                     )),
                     efth_attrs
                    )
                },
                coords = {
                    'time': u_time,
                    'longitude': lon_station,
                    'latitude': lat_station,
                    'frequency': frequency,
                    'direction': direction,
                }
            )

            # fill temp (chunkn_days x 24h step)
            ndays = int((u_time[-1]-u_time[0])/np.timedelta64(1,'D'))
            ct = 0
            for di in range(0, ndays, ch_days):
                print(u_time[ct],' - ',ct,':', min(ct+ch_days*24, ndays*24))
                xds_temp['Efth'][ct:min(ct+ch_days*24,ndays*24),:,:] = \
                xds_u[vn_efth][ct:min(ct+ch_days*24, ndays*24),station_ix,:,:]
                ct+=ch_days*24

            # save temp file
            xds_temp.to_netcdf(p_u_tmp,'w')

    # join .nc files in one file
    xds_out = Join_NCs(p_tmp, p_ncfile)

    return xds_out

def Download_Spec_Area(p_ncfile, lonq, latq):
    '''
    Download CSIRO spec data and stores it on netcdf format
    uses stations inside area
    lonq, latq: longitude latitude query: single value or limits

    returns xarray.Dataset
    xds_CSIRO_spec:
        (time, station, frequency, direction) Efth
    '''

    # days chunk size
    ch_days = 11

    # long, lat query
    lonp1 = lonq[0]
    latp1 = latq[0]
    lonp2 = lonq[-1]
    latp2 = latq[-1]

    # Generate URL list 
    l_urls = Generate_URLs('spec')

    # get output time limits and efth attributes
    with xr.open_dataset(l_urls[0]) as ff:
        t1 = ff.time[0].values  # time ini
        efth_attrs = ff['Efth'].attrs  # var attrs

    with xr.open_dataset(l_urls[-1]) as lf:
        t2 = lf.time[-1].values  # time end

    # mount output time array
    out_time = np.arange(t1, t2, timedelta(hours=1))

    # find station IDs inside area
    with nc4.Dataset(l_urls[0], 'r') as ff:
        sid_raw = ff['station'][:]
        lon_raw = ff['longitude'][0,:]
        lat_raw = ff['latitude'][0,:]

        p_stas = np.where(
            (lon_raw >= lonp1) & (lon_raw <= lonp2) & \
            (lat_raw >= latp1) & (lat_raw <= latp2)
        )

        # stations selected
        lon_stas = lon_raw[p_stas]
        lat_stas = lat_raw[p_stas]
        sid_stas = sid_raw[p_stas]

        # print stations to download
        for s,lo,la in zip(sid_stas, lon_stas, lat_stas):
            print('station ix: {0}. Longitude: {1}, Latitude: {2}'.format(
                s, lo, la
            ))

        # store frequency and direction
        frequency = ff['frequency'][:]
        direction = ff['direction'][:]

    # temp folder
    p_tmp = op.join(p_ncfile.replace('.nc','.tmp'))
    if not op.isdir(p_tmp):
        os.makedirs(p_tmp)

    # download data from files
    print('downloading CSIRO spec data... {0} files'.format(len(l_urls)))
    for u in l_urls:
        print(op.basename(u))

        # local downloaded file
        p_u_tmp = op.join(p_tmp, op.basename(u))
        if op.isfile(p_u_tmp):
            continue

        # read file from url
        # TODO: INTRODUCIR TRY/CATCH PARA BORRAR ARCHIVO INCOMPLETO
        with xr.open_dataset(u) as xds_u:
            u_time = xds_u.time.values[:]
            vn_efth = 'Efth' if 'Efth' in xds_u.variables else 'efth'

            # generate temp holder 
            xds_temp = xr.Dataset(
                {
                    'Efth':(
                        ('time','station','frequency','direction'),
                        np.nan * np.ones((
                            len(u_time),
                            len(sid_stas),
                            len(frequency),
                            len(direction)
                     )),
                     efth_attrs
                    )
                },
                coords = {
                    'time': u_time,
                    'station': sid_stas,
                    'longitude': lon_stas,
                    'latitude': lat_stas,
                    'frequency': frequency,
                    'direction': direction,
                }
            )

            # fill temp (chunkn_days x 24h step)
            ndays = int((u_time[-1]-u_time[0])/np.timedelta64(1,'D'))
            ct = 0
            for di in range(0, ndays, ch_days):
                print(u_time[ct],' - ',ct,':', min(ct+ch_days*24, ndays*24))
                ct2 = min(ct+ch_days*24,ndays*24)
                xds_temp['Efth'][ct:ct2,:,:,:] = \
                xds_u.sel(station=sid_stas)[vn_efth][ct:ct2,:,:,:]
                ct+=ch_days*24

            # save temp file
            xds_temp.to_netcdf(p_u_tmp,'w')
    print('done.')

    # join .nc files in one file
    xds_out = Join_NCs(p_tmp, p_ncfile)

    return xds_out

def Join_NCs(p_ncs_folder, p_out_nc):
    '''
    Join .nc files downloaded from CSIRO
    p_ncs_folder: folder containing CSIRO downloaded netCDF4 files
    p_out_nc: path to output netcdf file
    '''

    chk = 12 # n files for packs 

    # clean previous packs
    l_packs_del = sorted(
        [op.join(p_ncs_folder,n) for n in os.listdir(p_ncs_folder) if
         n.startswith('xds_packed_')])
    for f in l_packs_del:
        os.remove(f)

    # get files to join
    l_ncs = sorted(
        [op.join(p_ncs_folder,n) for n in os.listdir(p_ncs_folder) if
         n.endswith('.nc')])
    print('joining {0} netCDF4 files...'.format(len(l_ncs)))

    # first join by chk size in .nc packs 
    c = 1
    while l_ncs:
        pack = l_ncs[:chk]
        l_ncs = l_ncs[chk:]

        xds_pack = xr.open_mfdataset(pack)
        p_pack = op.join(p_ncs_folder, 'xds_packed_{0:03d}.nc'.format(c))
        print('pack {0}'.format(op.basename(p_pack)))
        xds_pack.to_netcdf(p_pack,'w')
        xds_pack.close()
        c+=1

    # join pakcs
    l_packs = sorted(
        [op.join(p_ncs_folder,n) for n in os.listdir(p_ncs_folder) if
         n.startswith('xds_packed_')])
    xds_out = xr.open_mfdataset(l_packs)
    xds_out.to_netcdf(p_out_nc,'w')

    # clean packs
    for p in l_packs:
        os.remove(p)

    print('done')
    return xr.open_dataset(p_out_nc)


def Download_Spec_Stations(p_ncfile):
    '''
    Download CSIRO stations lat, long, name and
    store it on netcdf format.

    returns xarray.Dataset
    '''

    # Generate URL list 
    l_urls = Generate_URLs('spec')

    # get stations 
    print('downloading CSIRO spec stations...')
    with xr.open_dataset(l_urls[0]) as ff:

        # generate output dataset
        xds_out = xr.Dataset(
            {
                'longitude': (('station'), ff.longitude[0,:]),
                'latitude': (('station'), ff.latitude[0,:]),
                'station_name': (('station'), ff.station_name[:]),
            },
            coords = {
                'station' : ff.station,
            }
        )
    print('done.')

    # save to netcdf file
    xds_out.to_netcdf(p_ncfile, 'w')

    return xds_out

def Download_Gridded_Coords(p_ncfolder):
    '''
    Download CSIRO grids lat, lon and attrs
    grid_code:  'pac_4m', 'pac_10m', 'aus_4m', 'aus_10m', 'glob_24m'

    returns list of xarray.Dataset
    '''

    grid_codes = ['glob_24m', 'pac_4m', 'pac_10m', 'aus_4m', 'aus_10m']

    # download folder
    if not op.isdir(p_ncfolder):
        os.makedirs(p_ncfolder)

    # Generate URL list 
    l_xds_grids = []
    for gc in grid_codes:
        print('downloading gridded coordinates: {0} ... '.format(gc))
        l_urls = Generate_URLs('gridded', gc)
        with xr.open_dataset(l_urls[0]) as ff:

            # get mask
            hs1 = ff.hs.isel(time=0).values[:]
            mask = ~np.isnan(hs1)

            # generate output dataset
            xds_out = xr.Dataset(
                {
                    'mask': (('latitude', 'longitude'), mask),
                },
                coords = {
                    'longitude': ff.longitude,
                    'latitude': ff.latitude,
                },
                attrs = ff.attrs
            )
            l_xds_grids.append(xds_out)

            # save to netcdf file
            xds_out.to_netcdf(op.join(p_ncfolder,'{0}.nc'.format(gc)), 'w')

    print('done.')

    # Return grids
    return l_xds_grids

