# Repo for MITA_SITA_Adjustments 


# Abstract: 


We compare bias correction in a state-of-the-art climate model, the community atmosphere model version 6 (CAM6), utilizing an online correction to the zonal and meridional wind learned from the atmospheric tendency adjustments of two data-assimilation (henceforth DA increments) systems. The two systems, The Data Assimilation Research Testbed (DART) reanalysis and a linear relaxation to observations scheme (Nudging) DA increments are pitted against each other in ~30-year climate runs. We focus on the extent to which correcting biases in atmospheric tendencies improves the model climatology, and model variability (on daily, intraseasonal, and seasonal timescales). We find that introducing mean diurnal and seasonal tendencies to the zonal and meridional wind fields vastly improves the model climatological state but introduces significant biases to the model variability. The addition of stochastically selected tendency anomalies acts to correct the model variability while leaving the climatological mean state bias adjustment static. 

# Model Builds + Namelist are found: 
- ./buildmodels/ 

# Source Mods to Add Nudging and Stochastic Increments: 
- ./sourcemods/ 

# Jupyter Notebooks to create figures / do analysis: 
- ./figure_notebooks/ 
