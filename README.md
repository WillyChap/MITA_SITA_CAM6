# Repo for MITA_SITA_Adjustments 

# Benefits of Deterministic and Stochastic Tendency Adjustments in a Climate Model

William E. Chapman & Judith Berner 

National Center for Atmospheric Research, Boulder, Colorado

### Please use the citation, if you use the material in this repo: 

Chapman, W.E., Berner, J.; Benefits of Deterministic and Stochastic Tendency Adjustments in a Climate Model, *arXiv preprint arXiv:* (2023)

# Abstract: 

We develop and compare model-error representation schemes derived from data assimilation increments and nudging tendencies in multi-decadal simulations of the community atmosphere model, version 6. Each scheme applies a bias correction during simulation run-time to the zonal and meridional winds. We quantify to which extent such online adjustment schemes improve the model climatology and variability on daily to seasonal timescales. Generally, we observe a ca. 30\% improvement to annual upper-level zonal winds, with largest improvements in boreal spring (ca. 35\%) and winter (ca. 47\%). Despite only adjusting the wind fields, we additionally observe a ca. 20\% improvement to annual precipitation over land, with the largest improvements in boreal fall (ca. 36\%) and winter (ca. 25\%), and a ca. 50\% improvement to annual sea level pressure, globally. With mean state adjustments alone, the dominant pattern of boreal low-frequency variability over the Atlantic (the North Atlantic Oscillation) is significantly improved. Additional stochasticity further increases the modal explained variances, which brings it closer to the observed value. A streamfunction tendency decomposition reveals that the improvement is due to an adjustment to the high- and low-frequency eddy-eddy interaction terms. In the Pacific, the mean state adjustment alone led to an erroneous deepening of the Aleutian low, but this was remedied with the addition of stochastically selected tendencies. Finally, from a practical standpoint, we discuss the performance of using data assimilation increments versus nudging tendencies for an online model-error representation.

# CAM Model Builds + Namelist are found: 
- ./buildmodels/ 

# Source Mods to Add Nudging and Stochastic Increments: 
- ./sourcemods/ 

# Jupyter Notebooks to create figures / do analysis: 
- ./figure_notebooks/

# Stream Function Tendency cookbooks and calculations:

- ./figure_notebooks/

