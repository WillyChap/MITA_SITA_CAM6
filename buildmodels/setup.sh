#!/usr/bin/env bash
# type "source ./setup.sh" to run this script first

PATH=$(echo "$PATH" | sed -e 's,/glade\/work\/wchapman\/miniconda3/[^:]\+\(:\|$\),,g')
PATH=$(echo "$PATH" | sed -e 's,/glade\/u\/home\/wchapman\/anaconda/[^:]\+\(:\|$\),,g')
module purge
module load ncarenv/1.3 intel/19.0.5 ncarcompilers/0.5.0 mpt/2.22 netcdf/4.7.3 nco/4.9.5 ncl/6.6.2 python/2.7.16

tcsh
setenv PBS_ACCOUNT P54048000
setenv resolution f09_d025
setenv user_grid '  '
set user_grid = "${user_grid} --gridfile /glade/work/raeder/Models/CAM_init/SST" 
set user_grid = "${user_grid}/config_grids+fv1+2deg_oi0.25_gland20.xml"
setenv sst_dataset "/glade/work/raeder/Models/CAM_init/SST/avhrr-only-v2.2011-202001_0Z_filled_c200810.nc"
setenv sst_grid  /glade/work/raeder/Models/CAM_init/SST/domain.ocn.d025.120821.nc
setenv compset HIST_CAM60_CLM50%BGC-CROP_CICE%PRES_DOCN%DOM_MOSART_SGLC_SWAV
setenv CESM_ROOT /glade/work/wchapman/cesm2_1_relsd_m5.6_STOCHai//


module load python/3.7.9
ncar_pylib
