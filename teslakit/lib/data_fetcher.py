#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import numpy as np
import os.path as op
import netCDF4 as nc4
import xarray as xr
from datetime import datetime, timedelta


def Download_MJO(p_ncfile, init_year=None, log=False):
    '''
    Download MJO data and stores it on netcdf format
    init_year: optional, data before init_year will be discarded ('yyyy-mm-dd')
    log: optional, show log

    returns xarray.Dataset
    xds_MJO:
        (time, ) mjo
        (time, ) phase
        (time, ) rmm1
        (time, ) rmm2
    '''

    # default parameter
    url_mjo = 'http://www.bom.gov.au/climate/mjo/graphics/rmm.74toRealtime.txt'

    # download data and mount time array
    ddata = np.genfromtxt(
        url_mjo,
        skip_header=2,
        usecols=(0,1,2,3,4,5,6),
        dtype = None,
        names = ('year','month','day','RMM1','RMM2','phase','amplitude'),
    )

    # mount dattime array
    dtimes = [datetime(d['year'], d['month'], d['day']) for d in ddata]

    # parse data to xarray.Dataset
    ds_mjo = xr.Dataset(
        {
            'mjo'   :(('time',), ddata['amplitude']),
            'phase' :(('time',), ddata['phase']),
            'rmm1'  :(('time',), ddata['RMM1']),
            'rmm2'  :(('time',), ddata['RMM2']),
        },
        {'time' : dtimes}
    )

    # cut dataset if asked
    if init_year:
        ds_mjo = ds_mjo.loc[dict(time=slice(init_year, None))]

    # save at netcdf file
    ds_mjo.to_netcdf(p_ncfile,'w')

    if log:
        print '\nMJO historical data downloaded to \n{0}\nMJO time: {1} - {2}\n'.format(
            p_ncfile, ds_mjo.time.values[0],ds_mjo.time.values[-1])

    return ds_mjo

def Generate_CSIRO_urls(switch_db='gridded', grid_code='pac_4m'):
    '''
    Generate URL list for downloading csiro gridded/spec data
    switch_db = gridded / spec
    grid_code = 'pac_4m', 'aus_4m', 'aus_10m', 'glob_24m', 'pac_4m', 'pac_10m'

    returns list of URLs with monthly CSIRO data
    '''

    # parameters
    url_base = 'http://data-cbr.csiro.au/thredds/dodsC/catch_all/CMAR_CAWCR-Wave_archive/'
    url_1 = 'CAWCR_Wave_Hindcast_1979-2010/'
    url_2 = 'CAWCR_Wave_Hindcast_Jan_2011_-_May_2013/'
    url_3 = 'CAWCR_Wave_Hindcast_Jun_2013_-_Jul_2014/'

    # generate .nc url list
    ym1 = ['{0}{1:02d}'.format(x, y) for x in range(1979,2010+1) for y in range(1,13)]
    ym2 = ['{0}{1:02d}'.format(x, y) for x in range(2011,2013+1) for y in range(1,13)]
    ym3 = ['{0}{1:02d}'.format(x, y) for x in range(2013,2014+1) for y in range(1,13)]

    ym2 = ym2[:ym2.index('201305')+1]
    ym3 = ym3[ym3.index('201306'):ym3.index('201407')+1]

    if switch_db == 'gridded':
        l_urls_1 = ['{0}{1}gridded/ww3.{2}.{3}.nc'.format(
            url_base, url_1, grid_code, ym) for ym in ym1]

        l_urls_2 = ['{0}{1}gridded/ww3.{2}.{3}.nc'.format(
            url_base, url_2, grid_code, ym) for ym in ym2]

        l_urls_3 = ['{0}{1}gridded/ww3.{2}.{3}.nc'.format(
            url_base, url_3, grid_code, ym) for ym in ym3]

    elif switch_db == 'spec':
        l_urls_1 = ['{0}{1}spec/ww3.{2}_spec.nc'.format(
            url_base, url_1, ym) for ym in ym1]

        l_urls_2 = ['{0}{1}spec/ww3.{2}_spec.nc'.format(
            url_base, url_2, ym) for ym in ym2]

        l_urls_3 = ['{0}{1}spec/ww3.{2}_spec.nc'.format(
            url_base, url_3, ym) for ym in ym3]

    l_urls = l_urls_1 + l_urls_2 + l_urls_3
    return l_urls

def Download_CSIRO_Grid(p_ncfile, lonq, latq, var_names):
    '''
    Download CSIRO gridded data and stores it on netcdf format
    lonq, latq: longitude latitude query: single value or limits
    var_names: variables to extract

    returns xarray.Dataset
    xds_CSIRO_gridded:
        (time, latitude, longitude) var_name_1
        (time, latitude, longitude) var_name_2
        ...
        (time, latitude, longitude) var_name_N
    '''

    # TODO: grid code as optional argument
    grid_code = 'pac_4m'  # 'aus_4m', 'aus_10m', 'glob_24m', 'pac_4m', 'pac_10m'

    # long, lat query
    lonp1 = lonq[0]
    latp1 = latq[0]
    lonp2 = lonq[-1]
    latp2 = latq[-1]

    # Generate URL list 
    l_urls = Generate_CSIRO_urls('gridded', grid_code)

    # get coordinates from first file
    with xr.open_dataset(l_urls[0]) as ff:
        idx1 = (np.abs(ff.longitude.values - lonp1)).argmin()
        idy1 = (np.abs(ff.latitude.values - latp1)).argmin()
        idx2 = (np.abs(ff.longitude.values - lonp2)).argmin()
        idy2 = (np.abs(ff.latitude.values - latp2)).argmin()
        t1 = ff.time[0].values  # time ini

        # store var attrs
        d_vatrs = {}
        for vn in var_names:
            d_vatrs[vn] = ff[vn].attrs

    # get time end from last file
    with xr.open_dataset(l_urls[-1]) as lf:
        t2 = lf.time[-1].values  # time end

    # mount time array
    base_time = np.arange(t1, t2, timedelta(hours=1))

    # get lon, lat slice
    base = ff.isel(
        longitude = slice(idx1,idx2+1),
        latitude = slice(idy1,idy2+1))

    # generate output holder 
    xds_out = xr.Dataset({},
        coords = {
            'time': base_time,
            'longitude': base.longitude.values,
            'latitude': base.latitude.values,
        }
    )

    # add vars to output holder
    for vn in var_names:
        xds_out[vn] = (
            ('time', 'latitude', 'longitude'),
            np.nan * np.ones((
                len(base_time),
                len(base.latitude.values),
                len(base.longitude.values)
            )),
           d_vatrs[vn]
        )


    # download data from files
    print 'downloading CSIRO gridded data...'
    for u in l_urls:
        print op.basename(u)

        # read file from url
        with xr.open_dataset(u) as xds_u:
            cut = xds_u.isel(
                longitude=slice(idx1,idx2+1),
                latitude=slice(idy1,idy2+1))

            cut_time = np.array(cut.time.values, dtype='datetime64[h]')
            ti0 = np.where(base_time==cut_time[0])[0][0]
            ti1 = np.where(base_time==cut_time[-1])[0][0]

            # fill output vars
            for vn in var_names:
                xds_out[vn][ti0:ti1+1,:,:] = cut[vn].values[:]

    print 'done.'

    # save to netcdf file
    xds_out.to_netcdf(p_ncfile, 'w')

    return xr.open_dataset(p_ncfile)

def Download_CSIRO_Spec(p_ncfile, lon_p, lat_p):
    '''
    Download CSIRO spec data and stores it on netcdf format
    lon_p, lat_p: longitude latitude point query

    returns xarray.Dataset
    xds_CSIRO_spec:
        (time, frequency, direction) Efth
    '''

    # Generate URL list 
    l_urls = Generate_CSIRO_urls('spec')
    l_urls = l_urls[:6]
    # TODO: QUITAR

    # get time limits
    with xr.open_dataset(l_urls[0]) as ff:
        t1 = ff.time[0].values  # time ini
        efth_attrs = ff['Efth'].attrs  # var attrs
    with xr.open_dataset(l_urls[-1]) as lf:
        t2 = lf.time[-1].values  # time ini

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

        print 'station ix: {0}. Longitude: {1}, Latitude: {2}'.format(
            station_ix, lon_station, lat_station
        )

        # store frequency and direction
        frequency = ff['frequency'][:]
        direction = ff['direction'][:]

    # mount time array
    base_time = np.arange(t1, t2, timedelta(hours=1))

    # generate output holder 
    xds_out = xr.Dataset({},
        coords = {
            'time': base_time,
            'longitude': lon_station,
            'latitude': lat_station,
            'frequency': frequency,
            'direction': direction,
        }
    )

    # add vars to output holder
    xds_out['Efth'] = (
        ('time', 'frequency', 'direction'),
        np.nan * np.ones((
            len(base_time),
            len(frequency),
            len(direction)
        )),
        efth_attrs
    )

    # download data from files
    print 'downloading CSIRO spec data... {0} files'.format(len(l_urls))
    for u in l_urls:
        print op.basename(u)

        # read file from url
        with nc4.Dataset(u, 'r') as ncf:

            # file time start index
            time_var = ncf.variables['time']
            dtime = nc4.num2date(time_var[:],time_var.units)
            cut_time = np.array(dtime, dtype='datetime64[h]')
            time_ix0 = np.where(base_time==cut_time[0])[0][0]

            # TODO: fill output (24h step)
            ndays = int((cut_time[-1]-cut_time[0])/np.timedelta64(1,'D'))
            ct = 0
            for di in range(ndays):
                print base_time[time_ix0+ct],' - ',time_ix0, ct,' - ', time_ix0+ct,':', time_ix0+ct+24, \
                ' --- ', ct,':', ct+24
                xds_out['Efth'][time_ix0+ct:time_ix0+ct+24,:,:] = \
                ncf['Efth'][ct:ct+24,station_ix,:,:]
                ct+=24

            ## fill output (1h)
            #for _, ct in enumerate(range(len(cut_time)-1)):
            #    xds_out['Efth'][time_ix0+ct,:,:] = \
            #    ncf['Efth'][ct,station_ix,:,:]
    print 'done.'

    # save to netcdf file
    xds_out.to_netcdf(p_ncfile, 'w')

    return xr.open_dataset(p_ncfile)

def Download_CSIRO_Spec_Stations(p_ncfile):
    '''
    Download CSIRO stations lat, long, name and
    store it on netcdf format.

    returns xarray.Dataset
    '''

    # Generate URL list 
    l_urls = Generate_CSIRO_urls('spec')

    # get stations 
    xds_out = None
    print 'downloading CSIRO spec stations...'
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
    print 'done.'

    # save to netcdf file
    xds_out.to_netcdf(p_ncfile, 'w')

    return xds_out

