#!/usr/bin/env python
# -*- coding: utf-8 -*-

import scipy.io as sio
import os.path as op
from scipy.io.matlab.mio5_params import mat_struct
import h5py
import xarray as xr
import numpy as np

from lib.custom_dateutils import DateConverter_Mat2Py

def ReadMatfile(p_mfile):
    'Parse .mat file to nested python dictionaries'

    def RecursiveMatExplorer(mstruct_data):
        # Recursive function to extrat mat_struct nested contents

        if isinstance(mstruct_data, mat_struct):
            # mstruct_data is a matlab structure object, go deeper
            d_rc = {}
            for fn in mstruct_data._fieldnames:
                d_rc[fn] = RecursiveMatExplorer(getattr(mstruct_data, fn))
            return d_rc

        else:
            # mstruct_data is a numpy.ndarray, return value
            return mstruct_data

    # base matlab data will be in a dict
    mdata = sio.loadmat(p_mfile, squeeze_me=True, struct_as_record=False)
    mdata_keys = [x for x in mdata.keys() if x not in
                  ['__header__','__version__','__globals__']]

    # use recursive function
    dout = {}
    for k in mdata_keys:
        dout[k] = RecursiveMatExplorer(mdata[k])
    return dout

def ReadGowMat(p_mfile):
    'Read data from gow.mat file. Return xarray.Dataset'

    d_matf = ReadMatfile(p_mfile)

    # parse matlab datenum to datetime
    time = DateConverter_Mat2Py(d_matf['time'])

    # separate keys
    ks_coords = ['time']
    ks_attrs = ['lat','lon','bat','forcing','mesh']

    # generate dataset
    xds_out = xr.Dataset(
        {
        },
        coords = {
            'time': time
        },
        attrs = {
        }
    )
    # fill dataset
    for k in d_matf.keys():
        if k in ks_attrs:
            xds_out.attrs[k] = d_matf[k]
        elif k not in ['time']:
            xds_out[k] =(('time',), d_matf[k])

    return xds_out

def ReadAstroTideMat(p_mfile):
    'Read data from MAR_1820000.mat file. Return xarray.Dataset'

    d_matf = ReadMatfile(p_mfile)['MAR']

    # parse matlab datenum to datetime
    time = DateConverter_Mat2Py(d_matf['time'])

    # separate keys
    ks_coords = ['time']
    ks_attrs = []

    # generate dataset
    xds_out = xr.Dataset(
        {
        },
        coords = {
            'time': time
        },
        attrs = {
        }
    )
    # fill dataset
    for k in d_matf.keys():
        if k in ks_attrs:
            xds_out.attrs[k] = d_matf[k]
        elif k not in ['time']:
            xds_out[k] =(('time',), d_matf[k])

    return xds_out

def ReadMareografoMat(p_mfile):
    'Read data from Mareografo_KWA.mat file. Return xarray.Dataset'

    d_matf = ReadMatfile(p_mfile)

    # parse matlab datenum to datetime
    time = DateConverter_Mat2Py(d_matf['DATES'])

    # separate keys
    ks_coords = ['time']
    ks_attrs = []

    # generate dataset
    xds_out = xr.Dataset(
        {
        },
        coords = {
            'time': time
        },
        attrs = {
        }
    )
    # fill dataset
    for k in d_matf.keys():
        if k in ks_attrs:
            xds_out.attrs[k] = d_matf[k]
        elif k not in ['DATES']:
            xds_out[k] =(('time',), d_matf[k])

    return xds_out

def ReadCoastMat(p_mfile):
    '''
    Read coast polygons from Costa.mat file.
    Return list of NX2 np.array [x,y]
    '''

    d_matf = ReadMatfile(p_mfile)
    l_pol = []
    for ms in d_matf['costa']:
        l_pol.append(np.array([ms.x, ms.y]).T)
    return l_pol

def ReadEstelaMat(p_mfile):
    '''
    Read estela data from .mat file.
    Return xarray.Dataset
    '''

    threshold = 0

    with h5py.File(p_mfile, 'r') as mf:
        if 'obj' in mf.keys():
            mf = mf['obj']

        # mesh
        mesh_lon = mf['TP']['fullX_centred'][:]
        mesh_lat = mf['full']['Y'][:]
        coast = mf['coastcntr']

        mesh_lon[mesh_lon<0]=mesh_lon[mesh_lon<0] + 360
        longitude = mesh_lon[0,:]
        latitude = mesh_lat[:,0]

        # fields
        d_D = {}
        d_F = {}
        d_Fthreas = {}
        fds = mf['C']['traveldays_interp'].keys()
        for fd in fds:
            d_D[fd] = mf['C']['traveldays_interp'][fd][:]
            d_F[fd] = mf['C']['FEmedia_interp'][fd][:]
            d_Fthreas[fd] = d_F[fd] / np.nanmax(d_F[fd])

            # use threshold
            d_D[fd][d_Fthreas[fd]<threshold/100] = np.nan
            d_F[fd][d_Fthreas[fd]<threshold/100] = np.nan
            d_Fthreas[fd][d_Fthreas[fd]<threshold/100] = np.nan


    # return xarray.Dataset
    xdset = xr.Dataset(
        {
        },
        coords = {
            'longitude': longitude,
            'latitude': latitude,
        },
        attrs = {
            #'first_day':np.floor(np.nanmax(d_D['y1993to2012']))+1
        }
    )

    for k in d_D.keys():
        xdset.update({
            'D_{0}'.format(k):(('latitude','longitude'), d_D[fd]),
            'F_{0}'.format(k):(('latitude','longitude'), d_F[fd]),
            'Fthreas_{0}'.format(k):(('latitude','longitude'), d_Fthreas[fd])
        })

    return xdset

def ReadNakajoMats(p_mfiles):
    '''
    Read Nakajo simulated hurricanes data from .mat files folder.
    Return xarray.Dataset
    '''

    n_sim = 10
    max_ts_end = 0
    n_storms = 0
    var_names = [
        'yts', 'ylon_TC' , 'ylat_TC', 'yDIR', 'ySPEED','yCPRES','del_reason'
    ]

    # generate var holder dict
    d_vars = {}
    for vn in var_names:
        d_vars[vn] = np.array([])

    # find number and time length of synthetic storms
    for i in range(n_sim):

        # read sim file
        p_matf = op.join(p_mfiles, 'YCAL{0}.mat'.format(i+1))
        d_matf = ReadMatfile(p_matf)

        # count storms
        n_storms += len(d_matf[var_names[0]])

        # append data to var holder
        for vn in var_names:
            d_vars[vn] = np.concatenate((d_vars[vn], d_matf[vn]))

    # add to xarray dataset
    xds_out = xr.Dataset(
        {
            'yts':(('storm',), d_vars['yts']),
            'ylon_TC':(('storm',), d_vars['ylon_TC']),
            'ylat_TC':(('storm',), d_vars['ylat_TC']),
            'yDIR':(('storm',), d_vars['yDIR']),
            'ySPEED':(('storm',), d_vars['ySPEED']),
            'yCPRES':(('storm',), d_vars['yCPRES']),
            'del_reason':(('storm',), d_vars['del_reason']),
        },
        coords = {
            'storm':range(n_storms)
        }
    )
    return xds_out

