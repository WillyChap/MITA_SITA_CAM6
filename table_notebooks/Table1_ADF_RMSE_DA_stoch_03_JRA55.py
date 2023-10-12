###### settings
vardo = 'Q'
levdo = 975
precip_obs='tp' ## specify 'precip' or 'tp' to switch datasets ... only important if vardo='PRECT'
derecho = False
### probably don't touch these.
freemod = 'f.e21.DAcompset.f09_d025_free_MJO_1982'
years_st = '1982'
years_en = '2010'
compare_model = 'f.e21.DAcompset.f09_d025_Seasonal_DA_stochai_UV_03_1982_r1'

do_JRA55 = False
## WOuld you like to skip using dask (ONly if pressure levels don't need to be interepereted)
skip_dask=False
#######


if derecho:
    scr_path = '/glade/cheyenne/scratch/wchapman/ADF/'
else:
    scr_path = '/glade/scratch/wchapman/ADF/'

import xarray as xr
import numpy as np
import pandas as pd
import glob
import scipy
import copy
import math
import time
import random


#plotting with Cartopy. 
import cartopy
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib import cm
from matplotlib import rc
#rc('font',**{'family':'sans-serif','sans-serif':['Helvetica']})
rc('font',**{'family':'serif','serif':['Times']})
rc('text', usetex=True)
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
from cartopy.mpl.ticker import LongitudeFormatter, LatitudeFormatter

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib import ticker


# import scipy
from datetime import datetime
import os
# import utils
import importlib


# import statsmodels.api as sm
# from windspharm.xarray import VectorWind
# from windspharm.standard import VectorWind
# from windspharm.examples import example_data_path
# from windspharm.tools import prep_data, recover_data, order_latdim
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score

from shapely.geometry.polygon import LinearRing
from dask.diagnostics import ProgressBar
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
import matplotlib.patches as mpatches
import math
import statsmodels.api as sm
from statsmodels.graphics import tsaplots
import geocat.comp as gcomp
import shutil
import metpy.calc as mpcalc


if 'client' in locals():
    client.shutdown()
    print('...shutdown client...')
else:
    print('client does not exist yet')


if not skip_dask:
    from distributed import Client
    from ncar_jobqueue import NCARCluster

    cluster = NCARCluster(project='P54048000',walltime='00:20:00')
    cluster.scale(40)
    client = Client(cluster)
    client

def chunker(seq, size):
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))


def wgt_rmse(fld1, fld2, wgt):
    """Calculated the area-weighted RMSE.
    Inputs are 2-d spatial fields, fld1 and fld2 with the same shape.
    They can be xarray DataArray or numpy arrays.
    Input wgt is the weight vector, expected to be 1-d, matching length of one dimension of the data.
    Returns a single float value.
    """
    assert len(fld1.shape) == 2,     "Input fields must have exactly two dimensions."
    assert fld1.shape == fld2.shape, "Input fields must have the same array shape."
    # in case these fields are in dask arrays, compute them now.
    if hasattr(fld1, "compute"):
        fld1 = fld1.compute()
    if hasattr(fld2, "compute"):
        fld2 = fld2.compute()
    if isinstance(fld1, xr.DataArray) and isinstance(fld2, xr.DataArray):
        return (np.sqrt(((fld1 - fld2)**2).weighted(wgt).mean())).values.item()
    else:
        check = [len(wgt) == s for s in fld1.shape]
        if ~np.any(check):
            raise IOError(f"Sorry, weight array has shape {wgt.shape} which is not compatible with data of shape {fld1.shape}")
        check = [len(wgt) != s for s in fld1.shape]
        dimsize = fld1.shape[np.argwhere(check).item()]  # want to get the dimension length for the dim that does not match the size of wgt
        warray = np.tile(wgt, (dimsize, 1)).transpose()   # May need more logic to ensure shape is correct.
        warray = warray / np.sum(warray) # normalize
        wmse = np.nansum(warray * (fld1 - fld2)**2)
        return np.sqrt( wmse ).item()

#######
#annual function
def weighted_temporal_mean(ds, var):
    """
    weight by days in each month
    """
    # Determine the month length
    month_length = ds.time.dt.days_in_month

    # Calculate the weights
    wgts = month_length.groupby("time.year") / month_length.groupby("time.year").sum()

    # Make sure the weights in each year add up to 1
    np.testing.assert_allclose(wgts.groupby("time.year").sum(xr.ALL_DIMS), 1.0)

    # Subset our dataset for our variable
    obs = ds[var]

    # Setup our masking for nan values
    cond = obs.isnull()
    ones = xr.where(cond, 0.0, 1.0)

    # Calculate the numerator
    obs_sum = (obs * wgts).resample(time="AS").sum(dim="time")

    # Calculate the denominator
    ones_out = (ones * wgts).resample(time="AS").sum(dim="time")

    # Return the weighted average
    return obs_sum / ones_out



# find ADF files. 
# ### make if statements for PRECT and TAUx / TAUy

if vardo == 'PRECT':
    #check for free model files 
    adf_dir = scr_path+freemod+'/ts/'
    fn_free1 = glob.glob(adf_dir+'*.'+'PRECC'+'*'+years_st+'*'+years_en+'*')
    fn_free2 = glob.glob(adf_dir+'*.'+'PRECL'+'*'+years_st+'*'+years_en+'*')
    
    if (len(fn_free1) == 0) |  (len(fn_free2) == 0): 
        fn_no = glob.glob(adf_dir+'/*.nc')
        for fnss in fn_no:
            print(fnss)
        raise Exception("variables PRECC and PRECL is not in the free model directory...run ADF")  
    else:
        print('free file found!!!')
        print(fn_free1[0])
        print(fn_free2[0])

    #check for compare model files 
    adf_dir = scr_path+compare_model+'/ts/'
    fn_comp1 = glob.glob(adf_dir+'*.'+'PRECC'+'*'+years_st+'*'+years_en+'*.nc')
    fn_comp2 = glob.glob(adf_dir+'*.'+'PRECL'+'*'+years_st+'*'+years_en+'*.nc') 
    if (len(fn_comp1) == 0) |  (len(fn_comp2) == 0): 
        fn_no = glob.glob(adf_dir+'/*.nc')
        for fnss in fn_no:
            print(fnss)
        raise Exception("variables PRECC and PRECL not in the compare model directory...run ADF")  
    else:
        print('compare file found!!!')
        print(fn_comp1[0])
        print(fn_comp2[0])
    
    #open variables: 
    DS_comp = xr.open_mfdataset([fn_comp1[0],fn_comp2[0]]).load()
    DS_comp['PRECT']=(DS_comp['PRECC']+DS_comp['PRECL'])*86400*1000
    DS_comp=DS_comp.drop_vars(['PRECC','PRECL'])
    
    DS_free = xr.open_mfdataset([fn_free1[0],fn_free2[0]]).load()
    DS_free['PRECT']=(DS_free['PRECC']+DS_free['PRECL'])*86400*1000
    DS_free=DS_free.drop_vars(['PRECC','PRECL'])

elif vardo == 'TAUX':
    
    #check for free model files 
    adf_dir = scr_path+freemod+'/ts/'
    fn_free1 = glob.glob(adf_dir+'*.'+'TAUX'+'*'+years_st+'*'+years_en+'*')
    fn_free2 = glob.glob(adf_dir+'*.'+'TAUGWX'+'*'+years_st+'*'+years_en+'*')
    
    if (len(fn_free1) == 0) |  (len(fn_free2) == 0): 
        fn_no = glob.glob(adf_dir+'/*.nc')
        for fnss in fn_no:
            print(fnss)
        raise Exception("variables TAUX and TAUGWX is not in the free model directory...run ADF")  
    else:
        print('free file found!!!')
        print(fn_free1[0])
        print(fn_free2[0])

    #check for compare model files 
    adf_dir = scr_path+compare_model+'/ts/'
    fn_comp1 = glob.glob(adf_dir+'*.'+'TAUX'+'*'+years_st+'*'+years_en+'*.nc')
    fn_comp2 = glob.glob(adf_dir+'*.'+'TAUGWX'+'*'+years_st+'*'+years_en+'*.nc') 
    if (len(fn_comp1) == 0) |  (len(fn_comp2) == 0): 
        fn_no = glob.glob(adf_dir+'/*.nc')
        for fnss in fn_no:
            print(fnss)
        raise Exception("variables TAUX and TAUGWX not in the compare model directory...run ADF")  
    else:
        print('compare file found!!!')
        print(fn_comp1[0])
        print(fn_comp2[0])
        
     
    DS_comp = xr.open_mfdataset([fn_comp1[0],fn_comp2[0]]).load()
    DS_comp['tau_nox'] = -(DS_comp['TAUX']-DS_comp['TAUGWX'])*100000
    DS_comp=DS_comp.drop_vars(['TAUX','TAUGWX'])
    DS_comp=DS_comp.rename({'tau_nox':vardo})
    
    DS_free = xr.open_mfdataset([fn_free1[0],fn_free2[0]]).load()
    DS_free['tau_nox'] = -(DS_free['TAUX']-DS_free['TAUGWX'])*100000
    DS_free=DS_free.drop_vars(['TAUX','TAUGWX'])
    DS_free=DS_free.rename({'tau_nox':vardo})

elif vardo == 'TAUY':
    raise Exception("TAUY has not been handled yet")  

elif vardo == 'Q':
    #check for free model files 
    adf_dir = scr_path+freemod+'/ts/'
    fn_free = glob.glob(adf_dir+'*.'+vardo+'.*'+years_st+'*'+years_en+'*')
    if len(fn_free) == 0: 
        fn_no = glob.glob(adf_dir+'/*.nc')
        for fnss in fn_no:
            print(fnss)
        raise Exception("variabile is not in the free model directory...run ADF")  
    else:
        print('free file found!!!')
        print(fn_free[0])

    #check for compare model files 
    adf_dir = scr_path+compare_model+'/ts/'
    fn_comp = glob.glob(adf_dir+'*.'+vardo+'.*'+years_st+'*'+years_en+'*.nc')
    if len(fn_comp) == 0: 
        fn_no = glob.glob(adf_dir+'/*.nc')
        for fnss in fn_no:
            print(fnss)
        raise Exception("variabile is not in the compare model directory...run ADF")  
    else:
        print('compare file found!!!')
        print(fn_comp[0])
    
    #open variables: 
    DS_comp = xr.open_dataset(fn_comp[0])
    DS_free = xr.open_dataset(fn_free[0])
    DS_comp[vardo] = xr.open_dataset(fn_comp[0])[vardo]*10000    
    DS_free[vardo] = xr.open_dataset(fn_free[0])[vardo]*10000

else:
    #check for free model files 
    adf_dir = scr_path+freemod+'/ts/'
    fn_free = glob.glob(adf_dir+'*.'+vardo+'.*'+years_st+'*'+years_en+'*')
    if len(fn_free) == 0: 
        fn_no = glob.glob(adf_dir+'/*.nc')
        for fnss in fn_no:
            print(fnss)
        raise Exception("variabile is not in the free model directory...run ADF")  
    else:
        print('free file found!!!')
        print(fn_free[0])

    #check for compare model files 
    adf_dir = scr_path+compare_model+'/ts/'
    fn_comp = glob.glob(adf_dir+'*.'+vardo+'.*'+years_st+'*'+years_en+'*.nc')
    if len(fn_comp) == 0: 
        fn_no = glob.glob(adf_dir+'/*.nc')
        for fnss in fn_no:
            print(fnss)
        raise Exception("variabile is not in the compare model directory...run ADF")  
    else:
        print('compare file found!!!')
        print(fn_comp[0])
    
    #open variables: 
    DS_comp = xr.open_dataset(fn_comp[0])
    DS_free = xr.open_dataset(fn_free[0])
    
    if vardo == 'VpQp':
        DS_comp = DS_comp*10000
        DS_free = DS_free*10000


#re-align time...
DS_comp['time'] = pd.date_range(start=years_st+'-01-01',end=years_en+'-12-01',freq='MS')
DS_free['time'] = pd.date_range(start=years_st+'-01-01',end=years_en+'-12-01',freq='MS')

lndfile_ = scr_path+compare_model+'/ts/*LANDFRAC*'+'.*'+years_st+'*'+years_en+'*.nc'
fn_lndfile=glob.glob(lndfile_)[0]

if len(fn_lndfile) == 0: 
    fn_no = glob.glob(adf_dir+'/*.nc')
    for fnss in fn_no:
        print(fnss)
    raise Exception("LANDFRAC is not in the compare model directory...run ADF")  
else:
    print('LANDFRAC compare file found!!!')
    print(fn_lndfile[0])
    DS_LandFrac = xr.open_dataset(fn_lndfile)
    DS_LandFrac_season = DS_LandFrac.groupby("time.season").sum(dim="time")
    Annual_landfrac = weighted_temporal_mean(DS_LandFrac,'LANDFRAC').mean('time')
    Annual_landfrac = Annual_landfrac.assign_coords(season='ANN')
    Annual_landfrac = Annual_landfrac.expand_dims('season')
    Annual_landfrac = Annual_landfrac.to_dataset(name='LANDFRAC')
    DS_LandFrac_season = xr.merge([Annual_landfrac,DS_LandFrac_season])


#grab_landfrac 
#FUNCTION:
#interpolate data
keys_list = list(DS_free.keys())
if 'hyam' in keys_list:
    surf_var = False
    DS_comp = DS_comp.chunk({'time':10, 'lat':192, 'lon':288})
    DS_free = DS_free.chunk({'time':10, 'lat':192, 'lon':288})
    print('First Regrid then seek user input')
    new_levs = np.array([3, 7, 20, 30, 50, 70, 100, 125, 150, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800, 850, 900, 925, 950, 975, 1000])*100 #mb
    DS_comp_int = gcomp.interpolation.interp_hybrid_to_pressure(DS_comp[vardo],DS_comp['PS'],DS_comp['hyam'],DS_comp['hybm'],100000.,new_levels=new_levs).persist()
    DS_comp_int =  DS_comp_int.rename({"plev": "lev"})
    DS_comp_int["lev"] =  DS_comp_int["lev"] / 100.0
    print('computing')
    DS_comp_int =  DS_comp_int.compute()
    print('interpolation of ',vardo,'..finished comp..')
    
    
    DS_free_int = gcomp.interpolation.interp_hybrid_to_pressure(DS_free[vardo],DS_free['PS'],DS_free['hyam'],DS_free['hybm'],100000.,new_levels=new_levs).persist()
    DS_free_int =  DS_free_int.rename({"plev": "lev"})
    DS_free_int["lev"] =  DS_free_int["lev"] / 100.0
    print('computing')
    DS_free_int =  DS_free_int.compute()
    print('interpolation of ',vardo,'..finished total..')
    print('enter level:')
    DS_free_int = DS_free_int.sel(lev=levdo)
    DS_comp_int = DS_comp_int.sel(lev=levdo)
elif np.isin(vardo,['VpVp','VpQp','EKE']):
    surf_var = False
    DS_free_int = DS_free.sel(lev=levdo).compute()
    DS_comp_int = DS_comp.sel(lev=levdo).compute()
    DS_free_int = DS_free_int[vardo]
    DS_comp_int = DS_comp_int[vardo]
else:
    surf_var = True
    levdo = 'surf'
    DS_free_int = DS_free.compute()
    DS_comp_int = DS_comp.compute()
    DS_free_int = DS_free_int[vardo]
    DS_comp_int = DS_comp_int[vardo]

#FUNCTION:
#get obs 


print('...getting obs...')

if do_JRA55:
    print('doing JRA55')
    ERAds1 = xr.open_dataset('/glade/work/wchapman/JRA55_Obs/JRA55.anl_p125.011_tmp.camgrid.1979-2010.nc').sel(time=slice(years_st+'-01-01',years_en+'-12-01'))
    ERAds2 = xr.open_dataset('/glade/work/wchapman/JRA55_Obs/JRA55.anl_p125.033_ugrd.camgrid.1979-2010.nc').sel(time=slice(years_st+'-01-01',years_en+'-12-01'))
    ERAds3 = xr.open_dataset('/glade/work/wchapman/JRA55_Obs/JRA55.anl_p125.051_spfh.camgrid.1979-2010.nc').sel(time=slice(years_st+'-01-01',years_en+'-12-01'))
    ERAds4 = xr.open_dataset('/glade/work/wchapman/JRA55_Obs/JRA55.anl_p125.034_vgrd.camgrid.1979-2010.nc').sel(time=slice(years_st+'-01-01',years_en+'-12-01'))
    ERAds5 = xr.open_dataset('/glade/work/wchapman/ERAi_Obs/GPCP.prec.camgrid.1979-2010.nc').sel(time=slice(years_st+'-01-01',years_en+'-12-01'))
    ERAds6 = xr.open_dataset('/glade/work/wchapman/JRA55_Obs/JRA55.anl_surf125.002_prmsl.camgrid.1979-2010.nc').sel(time=slice(years_st+'-01-01',years_en+'-12-01'))
    ERAds7 = xr.open_dataset('/glade/work/wchapman/JRA55_Obs/JRA55.anl_surf125.011_tmp.camgrid.1979-2010.nc').sel(time=slice(years_st+'-01-01',years_en+'-12-01'))

    ERAi = xr.merge([ERAds1,ERAds2,ERAds3,ERAds4,ERAds5,ERAds6,ERAds7])
    ERAi = ERAi.sel(time=slice(years_st+'-01-01',years_en+'-12-01'))

    mapping_var_dict = {'U':'u','V':'v','T':'t','Q':'q','Z3':'z','OMEGA':'w','TREFHT':'t2m','PSL':'msl','PRECT':precip_obs,'TAUX':'ewss', 'VpVp':'VpVp','VpQp':'VpQp','EKE':'EKE'}
    vardo_era = mapping_var_dict[vardo]

    if vardo_era == 'tp':
        ERAi = ERAi[vardo_era]*10000
    elif vardo_era == 'precip':
        ERAi = ERAi[vardo_era]
    elif vardo_era == 'ewss':
        ERAi = ERAi[vardo_era]
    elif vardo_era =='q':
        ERAi = ERAi[vardo_era]*10000
    elif np.isin(vardo_era,['VpVp','VpQp','EKE']):
        ERAi = ERAds6[vardo_era].sel(lev=levdo)
        if vardo_era =='VpQp':
            ERAi = ERAi*10000
    else: 
        ERAi = ERAi[vardo_era]

    if 'hyam' in keys_list:
        ERAi = (ERAi.sel(level=[3, 7, 20, 30, 50, 70, 100, 125, 150, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800, 850, 900, 925, 950, 975, 1000]))
        ERAi =  ERAi.rename({"level": "lev"})
        ERAi = ERAi.sel(lev=levdo)

    ERAi = ERAi.compute()
else:
    print('doing ERAi')
    ERAds1 = xr.open_dataset('/glade/work/wchapman/ERAi_Obs/ERAinterim.OTHERVARS.camgrid.1979-2010.nc').sel(time=slice(years_st+'-01-01',years_en+'-12-01'))
    ERAds2 = xr.open_dataset('/glade/work/wchapman/ERAi_Obs/ERAinterim.UV.camgrid.1979-2010.nc').sel(time=slice(years_st+'-01-01',years_en+'-12-01'))
    ERAds3 = xr.open_dataset('/glade/work/wchapman/ERAi_Obs/ERAinterim.fc12hr.sfc.camgrid.1979-2010.nc').sel(time=slice(years_st+'-01-01',years_en+'-12-01'))
    ERAds4 = xr.open_dataset('/glade/work/wchapman/JRA55_Obs/ei.moda.an.sfc.regn128sc.V3.camgrid.1979-2010.nc').sel(time=slice(years_st+'-01-01',years_en+'-12-01'))
    ERAds5 = xr.open_dataset('/glade/work/wchapman/ERAi_Obs/GPCP.prec.camgrid.1979-2010.nc').sel(time=slice(years_st+'-01-01',years_en+'-12-01'))
    ERAds6 = xr.open_dataset('/glade/work/wchapman/ERAi_Obs/ERAinterim.HF.camgrid.1979-2010.nc').sel(time=slice(years_st+'-01-01',years_en+'-12-01'))

    ERAi = xr.merge([ERAds1,ERAds2,ERAds3,ERAds4.drop_vars("z"),ERAds5])
    ERAi = ERAi.sel(time=slice(years_st+'-01-01',years_en+'-12-01'))

    mapping_var_dict = {'U':'u','V':'v','T':'t','Q':'q','Z3':'z','OMEGA':'w','TREFHT':'t2m','PSL':'msl','PRECT':precip_obs,'TAUX':'ewss', 'VpVp':'VpVp','VpQp':'VpQp','EKE':'EKE'}
    vardo_era = mapping_var_dict[vardo]

    if vardo_era == 'tp':
        ERAi = ERAi[vardo_era]*10000
    elif vardo_era == 'precip':
        ERAi = ERAi[vardo_era]
    elif vardo_era == 'ewss':
        ERAi = ERAi[vardo_era]
    elif vardo_era =='q':
        ERAi = ERAi[vardo_era]*10000
    elif np.isin(vardo_era,['VpVp','VpQp','EKE']):
        ERAi = ERAds6[vardo_era].sel(lev=levdo)
        if vardo_era =='VpQp':
            ERAi = ERAi*10000
    else: 
        ERAi = ERAi[vardo_era]

    if 'hyam' in keys_list:
        ERAi = (ERAi.sel(level=[3, 7, 20, 30, 50, 70, 100, 125, 150, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800, 850, 900, 925, 950, 975, 1000]))
        ERAi =  ERAi.rename({"level": "lev"})
        ERAi = ERAi.sel(lev=levdo)

    ERAi = ERAi.compute()

# #add an exception for VpQp

if 'client' in locals():
    client.shutdown()
    print('...shutdown client...')
else:
    print('client does not exist yet')

    

# %%time
##read this... confusing result with doing replacement:
#https://web.ma.utexas.edu/users/parker/sampling/woreplshort.htm#without
#https://stats.stackexchange.com/questions/69744/why-at-all-consider-sampling-without-replacement-in-a-practical-application
#Bootstrap: 
bs_nummy = 500
LF_scale = 0.1 
if vardo=='TREFHT':
    LF_scale=1
    print('Land Scale:', 1)
seas = ['DJF','MAM','JJA','SON']
#latitude weighting.
weights_cos = np.cos(np.deg2rad(DS_free_int.lat))
weights_cos.name = "weights"

# # set up years: 

yers_len = len(np.unique(DS_comp_int['time.year']))

DJF_ints = np.arange(0,3)
DJF_all=[]
for ii in range(yers_len):
    DJF_all.append(list(DJF_ints+12*ii))
DJF_all = np.array(DJF_all).flatten()

MAM_ints = np.arange(3,6)
MAM_all=[]
for ii in range(yers_len):
    MAM_all.append(list(MAM_ints+12*ii))
MAM_all = np.array(MAM_all).flatten()

JJA_ints = np.arange(6,9)
JJA_all=[]
for ii in range(yers_len):
    JJA_all.append(list(JJA_ints+12*ii))
JJA_all = np.array(JJA_all).flatten()

SON_ints = np.arange(9,12)
SON_all=[]
for ii in range(yers_len):
    SON_all.append(list(SON_ints+12*ii))
SON_all = np.array(SON_all).flatten()

#dictionaries for RMSE
RMSE_dict_free={'DJF_global':[],'MAM_global':[],'JJA_global':[],'SON_global':[],'ANN_global':[],
               'DJF_trop':[],'MAM_trop':[],'JJA_trop':[],'SON_trop':[],'ANN_trop':[],
               'DJF_extrop':[],'MAM_extrop':[],'JJA_extrop':[],'SON_extrop':[],'ANN_extrop':[],
               'DJF_land':[],'MAM_land':[],'JJA_land':[],'SON_land':[],'ANN_land':[],
               'DJF_ocean':[],'MAM_ocean':[],'JJA_ocean':[],'SON_ocean':[],'ANN_ocean':[]}

RMSE_dict_comp={'DJF_global':[],'MAM_global':[],'JJA_global':[],'SON_global':[],'ANN_global':[],
               'DJF_trop':[],'MAM_trop':[],'JJA_trop':[],'SON_trop':[],'ANN_trop':[],
               'DJF_extrop':[],'MAM_extrop':[],'JJA_extrop':[],'SON_extrop':[],'ANN_extrop':[],
               'DJF_land':[],'MAM_land':[],'JJA_land':[],'SON_land':[],'ANN_land':[],
               'DJF_ocean':[],'MAM_ocean':[],'JJA_ocean':[],'SON_ocean':[],'ANN_ocean':[]}


lat = DS_free_int['lat']
res_all = []
for bs_ii in range(bs_nummy):
    if bs_ii % 20 ==0:
        print(bs_ii)
    
    #sample from each season equally: 
    
    D_int=random.sample(list(DJF_all),k=int(len(DJF_all)*0.8))
    M_int=random.sample(list(MAM_all),k=int(len(DJF_all)*0.8))
    J_int=random.sample(list(JJA_all),k=int(len(DJF_all)*0.8))
    S_int=random.sample(list(SON_all),k=int(len(DJF_all)*0.8))
    res = list(np.array([D_int,M_int,J_int,S_int]).flatten())
    res_all.append(res)
    #select equally random in time per season.....
    
    
    DS_free_temp = DS_free_int.isel(time=res)
    DS_comp_temp = DS_comp_int.isel(time=res)
    ERAi_temp = ERAi.isel(time=res)
    
    month_length = DS_free_temp.time.dt.days_in_month
    weights = (month_length.groupby("time.season") / month_length.groupby("time.season").sum())
    np.testing.assert_allclose(weights.groupby("time.season").sum().values, np.ones(4))
    DS_free_weighted = (DS_free_temp * weights).groupby("time.season").sum(dim="time",skipna=False)
    DS_comp_weighted = (DS_comp_temp * weights).groupby("time.season").sum(dim="time",skipna=False)
    ERAi_weighted = (ERAi_temp * weights).groupby("time.season").sum(dim="time",skipna=False)
    ERAi_weighted.to_dataset(name=vardo)
    DS_free_weighted.to_dataset(name=vardo)
    DS_comp_weighted.to_dataset(name=vardo)
    
    
    #get RMSE by season. 
    for seas_do in seas:
        if vardo=='TREFHT': #correct for prescribed ocean... 
            plotter_obs = ERAi_weighted.sel(season=seas_do)
            plotter_obs = plotter_obs.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
        
            plotter_free = DS_free_weighted.sel(season=seas_do)
            plotter_free = plotter_free.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
        
            plotter_comp = DS_comp_weighted.sel(season=seas_do)
            plotter_comp = plotter_comp.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
            
            #global
            RMSE_dict_free[seas_do+'_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_free.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
            RMSE_dict_comp[seas_do+'_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_comp.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

            #extropics 
            plotter_free_extrop = plotter_free.where((lat>25)|(lat<-25),np.nan)
            plotter_free_extrop = plotter_free_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
        
            plotter_comp_extrop = plotter_comp.where((lat>25)|(lat<-25),np.nan)
            plotter_comp_extrop = plotter_comp_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()

            plotter_obs_extrop = plotter_obs.where((lat>25)|(lat<-25),np.nan)
            plotter_obs_extrop = plotter_obs_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()

            RMSE_dict_free[seas_do+'_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_free_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
            RMSE_dict_comp[seas_do+'_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_comp_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

            #tropics 
            plotter_free_trop = plotter_free.where((lat<25)&(lat>-25),np.nan)
            plotter_comp_trop = plotter_comp.where((lat<25)&(lat>-25),np.nan)
            plotter_obs_trop = plotter_obs.where((lat<25)&(lat>-25),np.nan)

            RMSE_dict_free[seas_do+'_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_free_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
            RMSE_dict_comp[seas_do+'_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_comp_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        elif vardo=='TAUX':
            plotter_obs = ERAi_weighted.sel(season=seas_do)
            plotter_obs = plotter_obs.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
        
            plotter_free = DS_free_weighted.sel(season=seas_do)
            plotter_free = plotter_free.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
        
            plotter_comp = DS_comp_weighted.sel(season=seas_do)
            plotter_comp = plotter_comp.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
            
            #global
            RMSE_dict_free[seas_do+'_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_free.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
            RMSE_dict_comp[seas_do+'_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_comp.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

            #extropics 
            plotter_free_extrop = plotter_free.where((lat>25)|(lat<-25),np.nan)
            plotter_free_extrop = plotter_free_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
        
            plotter_comp_extrop = plotter_comp.where((lat>25)|(lat<-25),np.nan)
            plotter_comp_extrop = plotter_comp_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()

            plotter_obs_extrop = plotter_obs.where((lat>25)|(lat<-25),np.nan)
            plotter_obs_extrop = plotter_obs_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()

            RMSE_dict_free[seas_do+'_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_free_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
            RMSE_dict_comp[seas_do+'_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_comp_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

            #tropics 
            plotter_free_trop = plotter_free.where((lat<25)&(lat>-25),np.nan)
            plotter_free_trop = plotter_free_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
            plotter_comp_trop = plotter_comp.where((lat<25)&(lat>-25),np.nan)
            plotter_comp_trop = plotter_comp_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
            plotter_obs_trop = plotter_obs.where((lat<25)&(lat>-25),np.nan)
            plotter_obs_trop = plotter_obs_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()


            RMSE_dict_free[seas_do+'_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_free_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
            RMSE_dict_comp[seas_do+'_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_comp_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
            
        else:
            plotter_obs = ERAi_weighted.sel(season=seas_do)
            plotter_free = DS_free_weighted.sel(season=seas_do)
            plotter_comp = DS_comp_weighted.sel(season=seas_do)

            #global
            RMSE_dict_free[seas_do+'_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_free.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
            RMSE_dict_comp[seas_do+'_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_comp.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

            #extropics 
            plotter_free_extrop = plotter_free.where((lat>25)|(lat<-25),np.nan)
            plotter_comp_extrop = plotter_comp.where((lat>25)|(lat<-25),np.nan)
            plotter_obs_extrop = plotter_obs.where((lat>25)|(lat<-25),np.nan)

            RMSE_dict_free[seas_do+'_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_free_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
            RMSE_dict_comp[seas_do+'_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_comp_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

            #tropics 
            plotter_free_trop = plotter_free.where((lat<25)&(lat>-25),np.nan)
            plotter_comp_trop = plotter_comp.where((lat<25)&(lat>-25),np.nan)
            plotter_obs_trop = plotter_obs.where((lat<25)&(lat>-25),np.nan)

            RMSE_dict_free[seas_do+'_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_free_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
            RMSE_dict_comp[seas_do+'_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_comp_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

        if surf_var:
            if vardo=="TREFHT":
                seas_do_lf = 'ANN'
            else:
                seas_do_lf = seas_do
            
            plotter_obs = ERAi_weighted.sel(season=seas_do)
            plotter_free = DS_free_weighted.sel(season=seas_do)
            plotter_comp = DS_comp_weighted.sel(season=seas_do)
            
            plotter_obs_ocean = plotter_obs.where(DS_LandFrac_season.sel(season=seas_do_lf).LANDFRAC<=LF_scale,np.nan).squeeze()
            plotter_obs_land = plotter_obs.where(DS_LandFrac_season.sel(season=seas_do_lf).LANDFRAC>=LF_scale,np.nan).squeeze()
            plotter_free_ocean = plotter_free.where(DS_LandFrac_season.sel(season=seas_do_lf).LANDFRAC<=LF_scale,np.nan).squeeze()
            plotter_free_land = plotter_free.where(DS_LandFrac_season.sel(season=seas_do_lf).LANDFRAC>=LF_scale,np.nan).squeeze()
            plotter_comp_ocean = plotter_comp.where(DS_LandFrac_season.sel(season=seas_do_lf).LANDFRAC<=LF_scale,np.nan).squeeze()
            plotter_comp_land = plotter_comp.where(DS_LandFrac_season.sel(season=seas_do_lf).LANDFRAC>=LF_scale,np.nan).squeeze()

            #land            
            RMSE_dict_free[seas_do+'_land'].append(np.round(wgt_rmse(plotter_obs_land.sel(lat=slice(-87,87)),plotter_free_land.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
            RMSE_dict_comp[seas_do+'_land'].append(np.round(wgt_rmse(plotter_obs_land.sel(lat=slice(-87,87)),plotter_comp_land.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        
            #ocean 
            RMSE_dict_free[seas_do+'_ocean'].append(np.round(wgt_rmse(plotter_obs_ocean.sel(lat=slice(-87,87)),plotter_free_ocean.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
            RMSE_dict_comp[seas_do+'_ocean'].append(np.round(wgt_rmse(plotter_obs_ocean.sel(lat=slice(-87,87)),plotter_comp_ocean.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))


print('...doing actual...')
month_length = DS_free_int.time.dt.days_in_month
weights = (month_length.groupby("time.season") / month_length.groupby("time.season").sum())
np.testing.assert_allclose(weights.groupby("time.season").sum().values, np.ones(4))

DS_free_weighted = (DS_free_int * weights).groupby("time.season").sum(dim="time",skipna=False)
DS_comp_weighted = (DS_comp_int * weights).groupby("time.season").sum(dim="time",skipna=False)
ERAi_weighted = (ERAi * weights).groupby("time.season").sum(dim="time",skipna=False)

ERAi_weighted.to_dataset(name=vardo)
DS_free_weighted.to_dataset(name=vardo)
DS_comp_weighted.to_dataset(name=vardo)

for seas_do in seas:
    if vardo =='TREFHT': #correct for prescribed ocean... 
                
        plotter_obs = ERAi_weighted.sel(season=seas_do)
        plotter_obs = plotter_obs.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
        
        plotter_free = DS_free_weighted.sel(season=seas_do)
        plotter_free = plotter_free.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
        
        plotter_comp = DS_comp_weighted.sel(season=seas_do)
        plotter_comp = plotter_comp.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()

        #global
        RMSE_dict_free[seas_do+'_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_free.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp[seas_do+'_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_comp.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

        #extropics 
        plotter_free_extrop = plotter_free.where((lat>25)|(lat<-25),np.nan)
        plotter_free_extrop = plotter_free_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
        
        plotter_comp_extrop = plotter_comp.where((lat>25)|(lat<-25),np.nan)
        plotter_comp_extrop = plotter_comp_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()

        plotter_obs_extrop = plotter_obs.where((lat>25)|(lat<-25),np.nan)
        plotter_obs_extrop = plotter_obs_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()

        RMSE_dict_free[seas_do+'_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_free_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp[seas_do+'_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_comp_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

        #tropics 
        plotter_free_trop = plotter_free.where((lat<25)&(lat>-25),np.nan)
        plotter_free_trop = plotter_free_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()

        plotter_comp_trop = plotter_comp.where((lat<25)&(lat>-25),np.nan)
        plotter_comp_trop = plotter_comp_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
        
        plotter_obs_trop = plotter_obs.where((lat<25)&(lat>-25),np.nan)
        plotter_obs_trop = plotter_obs_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()

        RMSE_dict_free[seas_do+'_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_free_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp[seas_do+'_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_comp_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3)) 
        
    elif vardo =='TAUX': #correct for prescribed ocean... 
        plotter_obs = ERAi_weighted.sel(season=seas_do)
        plotter_obs = plotter_obs.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
        
        plotter_free = DS_free_weighted.sel(season=seas_do)
        plotter_free = plotter_free.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
        
        plotter_comp = DS_comp_weighted.sel(season=seas_do)
        plotter_comp = plotter_comp.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()

        #global
        RMSE_dict_free[seas_do+'_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_free.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp[seas_do+'_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_comp.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

        #extropics 
        plotter_free_extrop = plotter_free.where((lat>25)|(lat<-25),np.nan)
        plotter_free_extrop = plotter_free_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
        
        plotter_comp_extrop = plotter_comp.where((lat>25)|(lat<-25),np.nan)
        plotter_comp_extrop = plotter_comp_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()

        plotter_obs_extrop = plotter_obs.where((lat>25)|(lat<-25),np.nan)
        plotter_obs_extrop = plotter_obs_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()

        RMSE_dict_free[seas_do+'_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_free_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp[seas_do+'_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_comp_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

        #tropics 
        plotter_free_trop = plotter_free.where((lat<25)&(lat>-25),np.nan)
        plotter_free_trop = plotter_free_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()

        plotter_comp_trop = plotter_comp.where((lat<25)&(lat>-25),np.nan)
        plotter_comp_trop = plotter_comp_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
        
        plotter_obs_trop = plotter_obs.where((lat<25)&(lat>-25),np.nan)
        plotter_obs_trop = plotter_obs_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()

        RMSE_dict_free[seas_do+'_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_free_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp[seas_do+'_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_comp_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        
    else:
        plotter_obs = ERAi_weighted.sel(season=seas_do)
        plotter_free = DS_free_weighted.sel(season=seas_do)
        plotter_comp = DS_comp_weighted.sel(season=seas_do)

        #global
        RMSE_dict_free[seas_do+'_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_free.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp[seas_do+'_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_comp.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

        #extropics 
        plotter_free_extrop = plotter_free.where((lat>25)|(lat<-25),np.nan)
        plotter_comp_extrop = plotter_comp.where((lat>25)|(lat<-25),np.nan)
        plotter_obs_extrop = plotter_obs.where((lat>25)|(lat<-25),np.nan)

        RMSE_dict_free[seas_do+'_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_free_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp[seas_do+'_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_comp_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

        #tropics 
        plotter_free_trop = plotter_free.where((lat<25)&(lat>-25),np.nan)
        plotter_comp_trop = plotter_comp.where((lat<25)&(lat>-25),np.nan)
        plotter_obs_trop = plotter_obs.where((lat<25)&(lat>-25),np.nan)

        RMSE_dict_free[seas_do+'_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_free_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp[seas_do+'_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_comp_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
    
    if surf_var:
        
        if vardo=="TREFHT":
            seas_do_lf = 'ANN'
        else:
            seas_do_lf = seas_do
                
        plotter_obs = ERAi_weighted.sel(season=seas_do)
        plotter_free = DS_free_weighted.sel(season=seas_do)
        plotter_comp = DS_comp_weighted.sel(season=seas_do)
        
        plotter_obs_ocean = plotter_obs.where(DS_LandFrac_season.sel(season=seas_do_lf).LANDFRAC<=LF_scale,np.nan).squeeze()
        plotter_obs_land = plotter_obs.where(DS_LandFrac_season.sel(season=seas_do_lf).LANDFRAC>=LF_scale,np.nan).squeeze()
        plotter_free_ocean = plotter_free.where(DS_LandFrac_season.sel(season=seas_do_lf).LANDFRAC<=LF_scale,np.nan).squeeze()
        plotter_free_land = plotter_free.where(DS_LandFrac_season.sel(season=seas_do_lf).LANDFRAC>=LF_scale,np.nan).squeeze()
        plotter_comp_ocean = plotter_comp.where(DS_LandFrac_season.sel(season=seas_do_lf).LANDFRAC<=LF_scale,np.nan).squeeze()
        plotter_comp_land = plotter_comp.where(DS_LandFrac_season.sel(season=seas_do_lf).LANDFRAC>=LF_scale,np.nan).squeeze()

        
        #global
        RMSE_dict_free[seas_do+'_land'].append(np.round(wgt_rmse(plotter_obs_land.sel(lat=slice(-87,87)),plotter_free_land.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp[seas_do+'_land'].append(np.round(wgt_rmse(plotter_obs_land.sel(lat=slice(-87,87)),plotter_comp_land.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        
        #ocean
        RMSE_dict_free[seas_do+'_ocean'].append(np.round(wgt_rmse(plotter_obs_ocean.sel(lat=slice(-87,87)),plotter_free_ocean.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp[seas_do+'_ocean'].append(np.round(wgt_rmse(plotter_obs_ocean.sel(lat=slice(-87,87)),plotter_comp_ocean.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

 

print('###################')
print('...doing annual...')
print('###################')

#create annual: 
DS_free_annual=weighted_temporal_mean(DS_free_int.to_dataset(name=vardo),vardo)
DS_comp_annual=weighted_temporal_mean(DS_comp_int.to_dataset(name=vardo),vardo)
ERAi_annual=weighted_temporal_mean(ERAi.to_dataset(name=vardo),vardo)

#set nan values
DS_free_weighted = DS_free_weighted.where( DS_free_weighted != 0)
DS_comp_weighted = DS_comp_weighted.where( DS_comp_weighted != 0)
ERAi_weighted = ERAi_weighted.where( DS_comp_weighted != 0)

lat = DS_free_int['lat']
res_all = []
all_inds = np.arange(0,29)

for bs_ii in range(bs_nummy):
    res = random.sample(list(all_inds),k=int(len(all_inds)*0.8))
    if bs_ii % 20 ==0:
        print(bs_ii)
    DS_free_annual_temp = DS_free_annual.isel(time=res).mean('time')
    DS_comp_annual_temp = DS_comp_annual.isel(time=res).mean('time')
    ERAi_annual_temp = ERAi_annual.isel(time=res).mean('time')

    #set nan values
    
    plotter_obs = ERAi_annual_temp
    plotter_free = DS_free_annual_temp
    plotter_comp = DS_comp_annual_temp
    
    if vardo == 'TREFHT':
        #global
        RMSE_dict_free['ANN_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_free.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp['ANN_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_comp.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

        #extropics 
        plotter_free_extrop = plotter_free.where((lat>25)|(lat<-25),np.nan)
        plotter_free_extrop = plotter_free_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()

        plotter_comp_extrop = plotter_comp.where((lat>25)|(lat<-25),np.nan)
        plotter_comp_extrop = plotter_comp_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
    
        plotter_obs_extrop = plotter_obs.where((lat>25)|(lat<-25),np.nan)
        plotter_obs_extrop = plotter_obs_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()

        RMSE_dict_free['ANN_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_free_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp['ANN_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_comp_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

        #tropics 
        plotter_free_trop  = plotter_free.where((lat<25)&(lat>-25),np.nan)
        plotter_free_trop = plotter_free_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
    
        plotter_comp_trop = plotter_comp.where((lat<25)&(lat>-25),np.nan)
        plotter_comp_trop = plotter_comp_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
    
        plotter_obs_trop = plotter_obs.where((lat<25)&(lat>-25),np.nan)
        plotter_obs_trop = plotter_obs_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()

        RMSE_dict_free['ANN_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_free_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp['ANN_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_comp_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        
    elif vardo == 'TAUX':
        #global
        RMSE_dict_free['ANN_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_free.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp['ANN_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_comp.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

        #extropics 
        plotter_free_extrop = plotter_free.where((lat>25)|(lat<-25),np.nan)
        plotter_free_extrop = plotter_free_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()

        plotter_comp_extrop = plotter_comp.where((lat>25)|(lat<-25),np.nan)
        plotter_comp_extrop = plotter_comp_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
    
        plotter_obs_extrop = plotter_obs.where((lat>25)|(lat<-25),np.nan)
        plotter_obs_extrop = plotter_obs_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()

        RMSE_dict_free['ANN_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_free_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp['ANN_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_comp_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

        #tropics 
        plotter_free_trop  = plotter_free.where((lat<25)&(lat>-25),np.nan)
        plotter_free_trop = plotter_free_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
    
        plotter_comp_trop = plotter_comp.where((lat<25)&(lat>-25),np.nan)
        plotter_comp_trop = plotter_comp_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
    
        plotter_obs_trop = plotter_obs.where((lat<25)&(lat>-25),np.nan)
        plotter_obs_trop = plotter_obs_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()

        RMSE_dict_free['ANN_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_free_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp['ANN_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_comp_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        
    else:
        #global
        RMSE_dict_free['ANN_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_free.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp['ANN_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_comp.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        
        #extropics 
        plotter_free_extrop = plotter_free.where((lat>25)|(lat<-25),np.nan)
        plotter_comp_extrop = plotter_comp.where((lat>25)|(lat<-25),np.nan)
        plotter_obs_extrop = plotter_obs.where((lat>25)|(lat<-25),np.nan)
    
        RMSE_dict_free['ANN_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_free_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp['ANN_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_comp_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        
        #tropics 
        plotter_free_trop = plotter_free.where((lat<25)&(lat>-25),np.nan)
        plotter_comp_trop = plotter_comp.where((lat<25)&(lat>-25),np.nan)
        plotter_obs_trop = plotter_obs.where((lat<25)&(lat>-25),np.nan)
    
        RMSE_dict_free['ANN_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_free_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp['ANN_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_comp_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
    
    if surf_var:
        if vardo=="TREFHT":
            seas_do_lf = 'ANN'
        else:
            seas_do_lf = seas_do
                
        plotter_obs = ERAi_annual_temp
        plotter_free = DS_free_annual_temp
        plotter_comp = DS_comp_annual_temp
         
        plotter_obs_ocean = plotter_obs.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
        plotter_obs_land = plotter_obs.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
        plotter_free_ocean = plotter_free.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
        plotter_free_land = plotter_free.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
        plotter_comp_ocean = plotter_comp.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
        plotter_comp_land = plotter_comp.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
        
        #global
        RMSE_dict_free['ANN_land'].append(np.round(wgt_rmse(plotter_obs_land.sel(lat=slice(-87,87)),plotter_free_land.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp['ANN_land'].append(np.round(wgt_rmse(plotter_obs_land.sel(lat=slice(-87,87)),plotter_comp_land.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        
        #extropics
        RMSE_dict_free['ANN_ocean'].append(np.round(wgt_rmse(plotter_obs_ocean.sel(lat=slice(-87,87)),plotter_free_ocean.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        RMSE_dict_comp['ANN_ocean'].append(np.round(wgt_rmse(plotter_obs_ocean.sel(lat=slice(-87,87)),plotter_comp_ocean.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))


DS_free_annual_temp = DS_free_annual.mean('time')
DS_comp_annual_temp = DS_comp_annual.mean('time')
ERAi_annual_temp = ERAi_annual.mean('time')

plotter_obs = ERAi_annual_temp
plotter_free = DS_free_annual_temp
plotter_comp = DS_comp_annual_temp


if vardo == 'TREFHT':
    #global
    RMSE_dict_free['ANN_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_free.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
    RMSE_dict_comp['ANN_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_comp.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

    #extropics 
    plotter_free_extrop = plotter_free.where((lat>25)|(lat<-25),np.nan)
    plotter_free_extrop = plotter_free_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()

    plotter_comp_extrop = plotter_comp.where((lat>25)|(lat<-25),np.nan)
    plotter_comp_extrop = plotter_comp_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
    
    plotter_obs_extrop = plotter_obs.where((lat>25)|(lat<-25),np.nan)
    plotter_obs_extrop = plotter_obs_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()

    RMSE_dict_free['ANN_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_free_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
    RMSE_dict_comp['ANN_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_comp_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

    #tropics 
    plotter_free_trop  = plotter_free.where((lat<25)&(lat>-25),np.nan)
    plotter_free_trop = plotter_free_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
    
    plotter_comp_trop = plotter_comp.where((lat<25)&(lat>-25),np.nan)
    plotter_comp_trop = plotter_comp_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
    
    plotter_obs_trop = plotter_obs.where((lat<25)&(lat>-25),np.nan)
    plotter_obs_trop = plotter_obs_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()

    RMSE_dict_free['ANN_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_free_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
    RMSE_dict_comp['ANN_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_comp_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

elif vardo=='TAUX':
    #global
    RMSE_dict_free['ANN_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_free.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
    RMSE_dict_comp['ANN_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_comp.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

    #extropics 
    plotter_free_extrop = plotter_free.where((lat>25)|(lat<-25),np.nan)
    plotter_free_extrop = plotter_free_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()

    plotter_comp_extrop = plotter_comp.where((lat>25)|(lat<-25),np.nan)
    plotter_comp_extrop = plotter_comp_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
    
    plotter_obs_extrop = plotter_obs.where((lat>25)|(lat<-25),np.nan)
    plotter_obs_extrop = plotter_obs_extrop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()

    RMSE_dict_free['ANN_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_free_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
    RMSE_dict_comp['ANN_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_comp_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

    #tropics 
    plotter_free_trop  = plotter_free.where((lat<25)&(lat>-25),np.nan)
    plotter_free_trop = plotter_free_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
    
    plotter_comp_trop = plotter_comp.where((lat<25)&(lat>-25),np.nan)
    plotter_comp_trop = plotter_comp_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
    
    plotter_obs_trop = plotter_obs.where((lat<25)&(lat>-25),np.nan)
    plotter_obs_trop = plotter_obs_trop.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()

    RMSE_dict_free['ANN_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_free_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
    RMSE_dict_comp['ANN_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_comp_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
else: 
    #global
    RMSE_dict_free['ANN_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_free.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
    RMSE_dict_comp['ANN_global'].append(np.round(wgt_rmse(plotter_obs.sel(lat=slice(-87,87)),plotter_comp.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

    #extropics 
    plotter_free_extrop = plotter_free.where((lat>25)|(lat<-25),np.nan)
    plotter_comp_extrop = plotter_comp.where((lat>25)|(lat<-25),np.nan)
    plotter_obs_extrop = plotter_obs.where((lat>25)|(lat<-25),np.nan)

    RMSE_dict_free['ANN_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_free_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
    RMSE_dict_comp['ANN_extrop'].append(np.round(wgt_rmse(plotter_obs_extrop.sel(lat=slice(-87,87)),plotter_comp_extrop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

    #tropics 
    plotter_free_trop = plotter_free.where((lat<25)&(lat>-25),np.nan)
    plotter_comp_trop = plotter_comp.where((lat<25)&(lat>-25),np.nan)
    plotter_obs_trop = plotter_obs.where((lat<25)&(lat>-25),np.nan)

    RMSE_dict_free['ANN_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_free_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
    RMSE_dict_comp['ANN_trop'].append(np.round(wgt_rmse(plotter_obs_trop.sel(lat=slice(-87,87)),plotter_comp_trop.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))


if surf_var:
    plotter_obs = ERAi_annual_temp
    plotter_free = DS_free_annual_temp
    plotter_comp = DS_comp_annual_temp
    
    plotter_obs_ocean = plotter_obs.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
    plotter_obs_land = plotter_obs.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
    plotter_free_ocean = plotter_free.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
    plotter_free_land = plotter_free.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
    plotter_comp_ocean = plotter_comp.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC<=LF_scale,np.nan).squeeze()
    plotter_comp_land = plotter_comp.where(DS_LandFrac_season.sel(season='ANN').LANDFRAC>=LF_scale,np.nan).squeeze()
        
        
    #land
    RMSE_dict_free['ANN_land'].append(np.round(wgt_rmse(plotter_obs_land.sel(lat=slice(-87,87)),plotter_free_land.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
    RMSE_dict_comp['ANN_land'].append(np.round(wgt_rmse(plotter_obs_land.sel(lat=slice(-87,87)),plotter_comp_land.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
        
    #ocean
    RMSE_dict_free['ANN_ocean'].append(np.round(wgt_rmse(plotter_obs_ocean.sel(lat=slice(-87,87)),plotter_free_ocean.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))
    RMSE_dict_comp['ANN_ocean'].append(np.round(wgt_rmse(plotter_obs_ocean.sel(lat=slice(-87,87)),plotter_comp_ocean.sel(lat=slice(-87,87)),weights_cos.sel(lat=slice(-87,87))),3))

print('...done bootstrapping...')



outdir_text = '/glade/u/home/wchapman/ADF/RMSE_text/'

if do_JRA55:
    outfil = outdir_text + vardo+'_'+str(levdo)+'mb_JRA55_obsvar_'+vardo_era+'_'+freemod+'.txt'
else:
    outfil = outdir_text + vardo+'_'+str(levdo)+'mb_obsvar_'+vardo_era+'_'+freemod+'.txt'
    
if os.path.exists(outfil):
    os.remove(outfil)

with open(outfil, 'a') as the_file:
    the_file.write('model name: '+ freemod +'\n')
    
    for keekee in RMSE_dict_free.keys():
        if len(np.array(RMSE_dict_free[keekee])) > 0:
            the_file.write('################################### \n')
            
            the_file.write(keekee + ' mean:               '+ str(np.array(RMSE_dict_free[keekee])[-1]) +'\n')
            the_file.write(keekee + ' 5th percentile:     '+ str(np.percentile(np.array(RMSE_dict_free[keekee]),5))+'\n')
            the_file.write(keekee + ' 95th percentile:    '+ str(np.percentile(np.array(RMSE_dict_free[keekee]),95))+'\n')
            
            the_file.write('################################### \n')


outdir_text = '/glade/u/home/wchapman/ADF/RMSE_text/'

if do_JRA55:
    outfil = outdir_text + vardo+'_'+str(levdo)+'mb_JRA55_obsvar_'+vardo_era+'_'+compare_model+'.txt'
else:
    outfil = outdir_text + vardo+'_'+str(levdo)+'mb_obsvar_'+vardo_era+'_'+compare_model+'.txt'

if os.path.exists(outfil):
    os.remove(outfil)

with open(outfil, 'a') as the_file:
    the_file.write('model name: '+ compare_model +'\n')
    
    for keekee in RMSE_dict_comp.keys():
        if len(np.array(RMSE_dict_comp[keekee])) > 0:
            the_file.write('################################### \n')
            perc_improve = (np.array(RMSE_dict_free[keekee])[-1] - np.array(RMSE_dict_comp[keekee])[-1])/np.array(RMSE_dict_free[keekee])[-1]
            perc_improve = np.round(perc_improve,4)
            the_file.write(keekee + ' mean:               '+ str(np.array(RMSE_dict_comp[keekee])[-1]) +'\n')
            the_file.write(keekee + ' perc improved:      '+ str(perc_improve*100) +' %\n')
            the_file.write(keekee + ' 5th percentile:     '+ str(np.percentile(np.array(RMSE_dict_comp[keekee]),5))+'\n')
            the_file.write(keekee + ' 95th percentile:    '+ str(np.percentile(np.array(RMSE_dict_comp[keekee]),95))+'\n')
            the_file.write('################################### \n')


