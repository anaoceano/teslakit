#!/usr/bin/env python
# -*- coding: utf-8 -*-

# basic import
import os.path as op
import sys
sys.path.insert(0, op.join(op.dirname(__file__),'..'))

import numpy as np
import xarray as xr

# tk libs
from lib.data_fetcher.CSIRO import Download_Gridded_Coords, \
Download_Spec_Stations
from lib.plotting.CSIRO import WorldMap_Stations, \
WorldGlobe_Stations, WorldGlobeZoom_Stations, \
WorldMap_GriddedCoords


# data storage
p_data = op.join(op.dirname(__file__), '..', 'data')
p_test = op.join(p_data, 'tests', 'test_CSIRO')

p_nc_stations = op.join(p_test, 'csiro_down_stations.nc')
p_nc_allgrids = op.join(p_test, 'csiro_down_allgrids')

p_savefigs = op.join(p_test, 'export_figs')


# --------------------------------------
# Download and plot stations
#xds_spec_stations = Download_Spec_Stations(p_nc_stations)
xds_spec_stations = xr.open_dataset(p_nc_stations)

# plot spec stations world map
bk = 'simple' # 'simple', 'shaderelief', 'etopo', 'bluemarble'

# world map
name_export = 'WorldMap_Stations_{0}.png'.format(bk)
p_export = op.join(p_savefigs, name_export)
#WorldMap_Stations(
#    xds_spec_stations, bk,
#    p_export=p_export)


# area
name_export = 'Area_Stations_{0}.png'.format(bk)
p_export = op.join(p_savefigs, name_export)
WorldMap_Stations(
    xds_spec_stations, bk,
    lon_1 = 160, lat_1 = 4,
    lon_2 = 173, lat_2 = 15,
    d_parallel = 1., d_meridian=1.,
    p_export=p_export)


# plot spec stations world globe
bk = 'simple' # 'simple', 'shaderelief', 'etopo', 'bluemarble'
name_export = 'WorldGlobe_Stations_{0}.png'.format(bk)
p_export = op.join(p_savefigs, name_export)
lon_center = 130
lat_center = 0
#WorldGlobe_Stations(
#    xds_spec_stations, bk,
#    lon_center, lat_center,
#    p_export=p_export)


# --------------------------------------
# Download and plot grids
#Download_Gridded_Coords(p_nc_allgrids)

grid_f = 'pac_10m.nc'
xds_gridded = xr.open_dataset(op.join(p_nc_allgrids,grid_f))

# TODO: PLOT GRIDS
bk = 'bluemarble' # 'simple', 'shaderelief', 'etopo', 'bluemarble'
#name_export = 'WorldMap_grided_{0}{1}.png'.format(grid_f,bk)
name_export = 'AreaMap_gridded_{0}{1}.png'.format(grid_f,bk)
p_export = op.join(p_savefigs, name_export)
WorldMap_GriddedCoords(
    xds_gridded, bk,
    lon_1 = 160, lat_1 = 4,
    lon_2 = 173, lat_2 = 15,
    p_export=p_export)

