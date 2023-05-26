#!/usr/bin/env python
import os, sys

cesmroot = os.environ.get('CESM_ROOT')

if cesmroot is None:
    raise SystemExit("ERROR: CESM_ROOT must be defined in environment")

_LIBDIR = os.path.join(cesmroot,"cime","scripts","Tools")
sys.path.append(_LIBDIR)
_LIBDIR = os.path.join(cesmroot,"cime","scripts","lib")
sys.path.append(_LIBDIR)

import datetime, glob, shutil
import CIME.build as build
from standard_script_setup import *
from CIME.case             import Case
from CIME.utils            import safe_copy
from argparse              import RawTextHelpFormatter
from CIME.locked_files          import lock_file, unlock_file


def stage_source_mods(case, user_mods_dir):
    print('Work in Progress... check to see if this works.')
    caseroot = case.get_value("CASEROOT")
    for usermod in glob.iglob(user_mods_dir+"/*.F90"):
        safe_copy(usermod, caseroot+'/SourceMods/src.cam/')

def create_directory(directory_path):
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)
        print(f"Directory '{directory_path}' created.")
    else:
        print(f"Directory '{directory_path}' already exists.")

def write_line_to_file(file_path, line):
    with open(file_path, 'w') as file:
        file.write(line + '\n')

def stage_current_time(rundir,modname):
    fn_curr_time = rundir +'/current_time_file.txt'
    points_len = sorted(glob.glob(rundir+'/rpointer*'))
    
    if len(points_len) > 0:
        for dat_path in sorted(glob.glob(rundir+'/rpointer*')):
            with open(dat_path, 'r') as file:
                data = file.read().replace('\n', '')
            rpoint_dat = data.split('.')[-2]
        write_line_to_file(fn_curr_time,modname+'.cam.r.'+rpoint_dat+'.nc')
    else: 
        write_line_to_file(fn_curr_time,modname+'.cam.r.1979-01-01-00000.nc')

def per_run_case_updates(case, user_mods_dir, rundir):
    caseroot = case.get_value("CASEROOT")
    basecasename = os.path.basename(caseroot)
    unlock_file("env_case.xml",caseroot=caseroot)
    casename = basecasename
    case.set_value("CASE",casename)
    case.flush()
    lock_file("env_case.xml",caseroot=caseroot)
    case.set_value("CONTINUE_RUN",False)
    case.set_value("PROJECT","P54048000") #replace path
    for usermod in glob.iglob(user_mods_dir+"/user*"):
        safe_copy(usermod, caseroot)
    case.case_setup()
    
    stage_source_mods(case, user_mods_dir)


def build_base_case(baseroot, basecasename,res, compset, overwrite,
                    , project, pecount=None):
    
    caseroot = os.path.join(baseroot,basecasename)

    if overwrite and os.path.isdir(caseroot):
        shutil.rmtree(caseroot)
            
    with Case(caseroot, read_only=False) as case:
        if not os.path.isdir(caseroot):
            
            case.create(os.path.basename(caseroot), cesmroot, compset, res,
                        run_unsupported=True, answer="r",walltime="04:00:00",
                        user_mods_dir=user_mods_dir, pecount=pecount, project=project,machine_name="cheyenne")
            
            # make sure that changing the casename will not affect these variables
         
            #xml change all of our shit

            case.set_value("STOP_OPTION","nyears")
            case.set_value("STOP_N", 1)
            case.set_value("JOB_QUEUE", "regular")
            case.set_value("SSTICE_DATA_FILENAME", "/glade/scratch/wchapman/SST_avhrr/avhrr_v2.1/avhrr_v2.1-only-v2.19810901_cat_20111231_filled_c221104.nc")
            case.set_value("SSTICE_GRID_FILENAME", "/glade/scratch/wchapman/SST_avhrr/avhrr_v2.1/avhrr_v2.1-only-v2.19810901_cat_20111231_filled_c221104.nc")
            case.set_value("CALENDAR", "GREGORIAN")
            case.set_value("RUN_REFDATE", "1982-01-01")
            case.set_value("RUN_REFDATE", "1982-01-01")
            case.set_value("JOB_WALLCLOCK_TIME", "03:30:00")
            case.set_value("SSTICE_YEAR_ALIGN", "1981")
            case.set_value("SSTICE_YEAR_START", "1981")
            case.set_value("SSTICE_YEAR_END", "2011")


            #user_namelist_cam:

        rundir = case.get_value("RUNDIR")
        per_run_case_updates(case, user_mods_dir, rundir)
        update_namelist(baseroot,basecasename,psuedo_obs_dir)
        stage_source_mods(basecasename, './sourcemods/')
        print('...building case...')
        build.case_build(caseroot, case=case, save_build_provenance=False)
        print('...done build...')

        return caseroot

def update_namelist(baseroot,basecasename,psuedo_obs_dir):
    
    
    if basecasename =='f.e21.DAcompset.f09_d025_Seasonal_DA_stochai_UV_05_1982_V2':
        caseroot = os.path.join(baseroot,basecasename)
        fn_nl = caseroot+'/user_nl_cam'

        lines =[" ",
            "nhtfrq = 0, -24",
            "mfilt = 1, 1",
            "ndens = 2, 2",
            "fincl2 = 'U', 'V', 'T', 'Q', 'CLOUD', 'SST', 'CLDICE', 'CLDLIQ', 'TAUX', 'TAUY', 'PSL','PS','Z500','Nudge_U', 'Nudge_V', 'Nudge_Q', 'Nudge_T', 'Stochai_U','Stochai_V','Stochai_T','Stochai_Q',
            "&nudging_nl",
             " Nudge_Model        =.true.",
             " Nudge_Path         ='/glade/scratch/wchapman/inputdata/nudging/DAInc_1000/',
             " Nudge_File_Template='DA_INCS.%y-%m-%d-%s.nc'",
             " Nudge_Beg_Year =1981",
             " Nudge_Beg_Month=1",
             " Nudge_Beg_Day=1",
             " Nudge_End_Year =2019",
             " Nudge_End_Month=8",
             " Nudge_End_Day  =31",
             " Nudge_Uprof =2",
             " Nudge_Vprof =2",
             " Nudge_Tprof =0",
             " Nudge_Qprof =0",
             " Nudge_PSprof =0",
             " Nudge_Ucoef =1.0",
             " Nudge_Vcoef =1.0",
             " Nudge_Tcoef =1.0",
             " Nudge_Qcoef =0.0",
             " Nudge_Force_Opt = 1",
             " Nudge_Times_Per_Day = 4",
             " Model_Times_Per_Day = 48",
             " Nudge_TimeScale_Opt = 0",
             " Nudge_Vwin_Lindex = 6.",
             " Nudge_Vwin_Ldelta = 0.001",
             " Nudge_Vwin_Hindex = 33.",
             " Nudge_Vwin_Hdelta = 0.001",
             " Nudge_Vwin_Invert = .false.",
             " Nudge_Hwin_lat0     = 0.",
             " Nudge_Hwin_latWidth = 999.",
             " Nudge_Hwin_latDelta = 1.0",
             " Nudge_Hwin_lon0     = 180.",
             " Nudge_Hwin_lonWidth = 999.",
             " Nudge_Hwin_lonDelta = 1.0",
             " Nudge_Hwin_Invert   = .false.",
                
             "Stochai_Model        =.true.",
             "Stochai_Path         ='/glade/scratch/wchapman/inputdata/nudging/DA_StochAI/',
             "Stochai_File_Template='Stochai_DA_INCS.%y-%m-%d-%s.nc'",
             "Stochai_Beg_Year =1981",
             "Stochai_Beg_Month=1",
             "Stochai_Beg_Day=1",
             "Stochai_End_Year =2019",
             "Stochai_End_Month=8",
             "Stochai_End_Day  =31",
             "Stochai_Uprof =2",
             "Stochai_Vprof =2",
             "Stochai_Tprof =0",
             "Stochai_Qprof =0",
             "Stochai_PSprof =0",
             "Stochai_Ucoef =1.0",
             "Stochai_Vcoef =1.0",
             "Stochai_Tcoef =1.0",
             "Stochai_Qcoef =0.0",
             "Stochai_Force_Opt = 1",
             "Stochai_Times_Per_Day = 4",
             "Model_Times_Per_Day_Stochai = 48",
             "Stochai_TimeScale_Opt = 0",
             "Stochai_Vwin_Lindex = 6.",
             "Stochai_Vwin_Ldelta = 0.001",
             "Stochai_Vwin_Hindex = 33.",
             "Stochai_Vwin_Hdelta = 0.001",
             "Stochai_Vwin_Invert = .false.",
             "Stochai_Hwin_lat0     = 0.",
             "Stochai_Hwin_latWidth = 999.",
             "Stochai_Hwin_latDelta = 1.0",
             "Stochai_Hwin_lon0     = 180.",
             "Stochai_Hwin_lonWidth = 999.",
             "Stochai_Hwin_lonDelta = 1.0",
             "Stochai_Hwin_Invert   = .false.",
            ]

        with open(fn_nl, "a") as file:
            for line in lines:
                file.write(line + "\n")
                
    elif basecasename =='f.e21.DAcompset.f09_d025_Seasonal_stochai_UV_05_1982_MJO_v3':
        
        caseroot = os.path.join(baseroot,basecasename)
        fn_nl = caseroot+'/user_nl_cam'

        lines =[" ",
            "nhtfrq = 0, -24",
            "mfilt = 1, 1",
            "ndens = 2, 2",
            "fincl2 = 'U', 'V', 'T', 'Q', 'CLOUD', 'SST', 'CLDICE', 'CLDLIQ', 'TAUX', 'TAUY', 'PSL','PS','Z500','Nudge_U', 'Nudge_V', 'Nudge_Q', 'Nudge_T', 'Stochai_U','Stochai_V','Stochai_T','Stochai_Q',
            "&nudging_nl",
             " Nudge_Model        =.true.",
             " Nudge_Path         ='/glade/scratch/wchapman/inputdata/nudging/NudgingInc_UV/',
             " Nudge_File_Template='NUDGING_INCS.%y-%m-%d-%s.nc'",
             " Nudge_Beg_Year =1981",
             " Nudge_Beg_Month=1",
             " Nudge_Beg_Day=1",
             " Nudge_End_Year =2019",
             " Nudge_End_Month=8",
             " Nudge_End_Day  =31",
             " Nudge_Uprof =2",
             " Nudge_Vprof =2",
             " Nudge_Tprof =0",
             " Nudge_Qprof =0",
             " Nudge_PSprof =0",
             " Nudge_Ucoef =1.0",
             " Nudge_Vcoef =1.0",
             " Nudge_Tcoef =1.0",
             " Nudge_Qcoef =0.0",
             " Nudge_Force_Opt = 1",
             " Nudge_Times_Per_Day = 4",
             " Model_Times_Per_Day = 48",
             " Nudge_TimeScale_Opt = 0",
             " Nudge_Vwin_Lindex = 6.",
             " Nudge_Vwin_Ldelta = 0.001",
             " Nudge_Vwin_Hindex = 33.",
             " Nudge_Vwin_Hdelta = 0.001",
             " Nudge_Vwin_Invert = .false.",
             " Nudge_Hwin_lat0     = 0.",
             " Nudge_Hwin_latWidth = 999.",
             " Nudge_Hwin_latDelta = 1.0",
             " Nudge_Hwin_lon0     = 180.",
             " Nudge_Hwin_lonWidth = 999.",
             " Nudge_Hwin_lonDelta = 1.0",
             " Nudge_Hwin_Invert   = .false.",
            ]

        with open(fn_nl, "a") as file:
            for line in lines:
                file.write(line + "\n")
                
    elif basecasename =='f.e21.DAcompset.f09_d025_Seasonal_stochai_UV_05_1982_MJO_v3':
        caseroot = os.path.join(baseroot,basecasename)
        fn_nl = caseroot+'/user_nl_cam'

        lines =[" ",
            "nhtfrq = 0, -24",
            "mfilt = 1, 1",
            "ndens = 2, 2",
            "fincl2 = 'U', 'V', 'T', 'Q', 'CLOUD', 'SST', 'CLDICE', 'CLDLIQ', 'TAUX', 'TAUY', 'PSL','PS','Z500','Nudge_U', 'Nudge_V', 'Nudge_Q', 'Nudge_T', 'Stochai_U','Stochai_V','Stochai_T','Stochai_Q',
            "&nudging_nl",
             " Nudge_Model        =.true.",
             " Nudge_Path         ='/glade/scratch/wchapman/inputdata/nudging/StochAI_UV/',
             " Nudge_File_Template='NUDGING_INCS.%y-%m-%d-%s.nc'",
             " Nudge_Beg_Year =1981",
             " Nudge_Beg_Month=1",
             " Nudge_Beg_Day=1",
             " Nudge_End_Year =2019",
             " Nudge_End_Month=8",
             " Nudge_End_Day  =31",
             " Nudge_Uprof =2",
             " Nudge_Vprof =2",
             " Nudge_Tprof =0",
             " Nudge_Qprof =0",
             " Nudge_PSprof =0",
             " Nudge_Ucoef =1.0",
             " Nudge_Vcoef =1.0",
             " Nudge_Tcoef =1.0",
             " Nudge_Qcoef =0.0",
             " Nudge_Force_Opt = 1",
             " Nudge_Times_Per_Day = 4",
             " Model_Times_Per_Day = 48",
             " Nudge_TimeScale_Opt = 0",
             " Nudge_Vwin_Lindex = 6.",
             " Nudge_Vwin_Ldelta = 0.001",
             " Nudge_Vwin_Hindex = 33.",
             " Nudge_Vwin_Hdelta = 0.001",
             " Nudge_Vwin_Invert = .false.",
             " Nudge_Hwin_lat0     = 0.",
             " Nudge_Hwin_latWidth = 999.",
             " Nudge_Hwin_latDelta = 1.0",
             " Nudge_Hwin_lon0     = 180.",
             " Nudge_Hwin_lonWidth = 999.",
             " Nudge_Hwin_lonDelta = 1.0",
             " Nudge_Hwin_Invert   = .false.",
                
             "Stochai_Model        =.true.",
             "Stochai_Path         ='/glade/scratch/wchapman/inputdata/nudging/StochAI_UV/',
             "Stochai_File_Template='Stochai_INCS.%y-%m-%d-%s.nc'",
             "Stochai_Beg_Year =1981",
             "Stochai_Beg_Month=1",
             "Stochai_Beg_Day=1",
             "Stochai_End_Year =2019",
             "Stochai_End_Month=8",
             "Stochai_End_Day  =31",
             "Stochai_Uprof =2",
             "Stochai_Vprof =2",
             "Stochai_Tprof =0",
             "Stochai_Qprof =0",
             "Stochai_PSprof =0",
             "Stochai_Ucoef =1.0",
             "Stochai_Vcoef =1.0",
             "Stochai_Tcoef =1.0",
             "Stochai_Qcoef =0.0",
             "Stochai_Force_Opt = 1",
             "Stochai_Times_Per_Day = 4",
             "Model_Times_Per_Day_Stochai = 48",
             "Stochai_TimeScale_Opt = 0",
             "Stochai_Vwin_Lindex = 6.",
             "Stochai_Vwin_Ldelta = 0.001",
             "Stochai_Vwin_Hindex = 33.",
             "Stochai_Vwin_Hdelta = 0.001",
             "Stochai_Vwin_Invert = .false.",
             "Stochai_Hwin_lat0     = 0.",
             "Stochai_Hwin_latWidth = 999.",
             "Stochai_Hwin_latDelta = 1.0",
             "Stochai_Hwin_lon0     = 180.",
             "Stochai_Hwin_lonWidth = 999.",
             "Stochai_Hwin_lonDelta = 1.0",
             "Stochai_Hwin_Invert   = .false.",
            ]

        with open(fn_nl, "a") as file:
            for line in lines:
                file.write(line + "\n")
                
    elif basecasename =='f.e21.DAcompset.f09_d025_Seasonal_stochai_UV_00_1982':
        
        caseroot = os.path.join(baseroot,basecasename)
        fn_nl = caseroot+'/user_nl_cam'

        lines =[" ",
            "nhtfrq = 0, -24",
            "mfilt = 1, 1",
            "ndens = 2, 2",
            "fincl2 = 'U', 'V', 'T', 'Q', 'CLOUD', 'SST', 'CLDICE', 'CLDLIQ', 'TAUX', 'TAUY', 'PSL','PS','Z500','Nudge_U', 'Nudge_V', 'Nudge_Q', 'Nudge_T', 'Stochai_U','Stochai_V','Stochai_T','Stochai_Q',
            "&nudging_nl",
             " Nudge_Model        =.true.",
             " Nudge_Path         ='/glade/scratch/wchapman/inputdata/nudging/DAInc_1000/',
             " Nudge_File_Template='DA_INCS.%y-%m-%d-%s.nc'",
             " Nudge_Beg_Year =1981",
             " Nudge_Beg_Month=1",
             " Nudge_Beg_Day=1",
             " Nudge_End_Year =2019",
             " Nudge_End_Month=8",
             " Nudge_End_Day  =31",
             " Nudge_Uprof =2",
             " Nudge_Vprof =2",
             " Nudge_Tprof =0",
             " Nudge_Qprof =0",
             " Nudge_PSprof =0",
             " Nudge_Ucoef =1.0",
             " Nudge_Vcoef =1.0",
             " Nudge_Tcoef =1.0",
             " Nudge_Qcoef =0.0",
             " Nudge_Force_Opt = 1",
             " Nudge_Times_Per_Day = 4",
             " Model_Times_Per_Day = 48",
             " Nudge_TimeScale_Opt = 0",
             " Nudge_Vwin_Lindex = 6.",
             " Nudge_Vwin_Ldelta = 0.001",
             " Nudge_Vwin_Hindex = 33.",
             " Nudge_Vwin_Hdelta = 0.001",
             " Nudge_Vwin_Invert = .false.",
             " Nudge_Hwin_lat0     = 0.",
             " Nudge_Hwin_latWidth = 999.",
             " Nudge_Hwin_latDelta = 1.0",
             " Nudge_Hwin_lon0     = 180.",
             " Nudge_Hwin_lonWidth = 999.",
             " Nudge_Hwin_lonDelta = 1.0",
             " Nudge_Hwin_Invert   = .false.",
            ]

        with open(fn_nl, "a") as file:
            for line in lines:
                file.write(line + "\n")
            
    elif basecasename =='f.e21.DAcompset.f09_d025_free_MJO_1982':
        
        caseroot = os.path.join(baseroot,basecasename)
        fn_nl = caseroot+'/user_nl_cam'

        lines =[" ",
            "nhtfrq = 0, -24",
            "mfilt = 1, 1",
            "ndens = 2, 2",
            "fincl2 = 'U', 'V', 'T', 'Q', 'CLOUD', 'SST', 'CLDICE', 'CLDLIQ', 'TAUX', 'TAUY', 'PSL','PS','Z500',
            ]

        with open(fn_nl, "a") as file:
            for line in lines:
                file.write(line + "\n")
            

def _main_func(description):
    
    # -- CNTRL
    baseroot="/path/to/this/directory" #replace path
    basecasename5="f.e21.DAcompset.f09_d025_free_MJO_1982"
    res = "f09_g16"
    compset= "HIST_CAM60_CLM50%BGC-CROP_CICE%PRES_DOCN%DOM_MOSART_SGLC_SWAV"
    overwrite = False
    caseroot = build_base_case(baseroot, basecasename5, res,
                            compset, overwrite,project="P54048000") #replace path /project code
    
    # -- Nu.M1.S0
    baseroot="/path/to/this/directory" #replace path
    basecasename5="f.e21.DAcompset.f09_d025_Seasonal_stochai_UV_00_1982"
    res = "f09_g16"
    compset= "HIST_CAM60_CLM50%BGC-CROP_CICE%PRES_DOCN%DOM_MOSART_SGLC_SWAV"
    overwrite = False
    caseroot = build_base_case(baseroot, basecasename5, res,
                            compset, overwrite,project="P54048000") #replace path /project code
    
    # -- Nu.M1.S.5
    baseroot="/path/to/this/directory" #replace path
    basecasename5="f.e21.DAcompset.f09_d025_Seasonal_stochai_UV_05_1982_MJO_v3"
    res = "f09_g16"
    compset= "HIST_CAM60_CLM50%BGC-CROP_CICE%PRES_DOCN%DOM_MOSART_SGLC_SWAV"
    overwrite = False
    caseroot = build_base_case(baseroot, basecasename5, res,
                            compset, overwrite,project="P54048000") #replace path /project code
    
    # -- DArt.M1.S0
    baseroot="/path/to/this/directory" #replace path
    basecasename5="f.e21.DAcompset.f09_d025_Seasonal_DA_stochai_UV_00_1982"
    res = "f09_g16"
    compset= "HIST_CAM60_CLM50%BGC-CROP_CICE%PRES_DOCN%DOM_MOSART_SGLC_SWAV"
    overwrite = False
    caseroot = build_base_case(baseroot, basecasename5, res,
                            compset, overwrite,project="P54048000") #replace path /project code
    
    # -- DArt.M1.S.5
    baseroot="/path/to/this/directory" #replace path
    basecasename5="f.e21.DAcompset.f09_d025_Seasonal_DA_stochai_UV_05_1982"
    res = "f09_g16"
    compset= "HIST_CAM60_CLM50%BGC-CROP_CICE%PRES_DOCN%DOM_MOSART_SGLC_SWAV"
    overwrite = False
    caseroot = build_base_case(baseroot, basecasename5, res,
                            compset, overwrite,project="P54048000") #replace path /project code
    
    

if __name__ == "__main__":
    _main_func(__doc__)
