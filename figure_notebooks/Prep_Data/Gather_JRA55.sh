#!/bin/bash


module load eccodes 
# Path to the directory containing GRIB files
grib_directory="/glade/campaign/collections/rda/data/ds628.1/anl_p125/"

# Directory for the output NetCDF files
output_directory="/glade/scratch/wchapman/MERRA_regrid_out/"

# Loop through the years (from 1958 to 2017)
for year in {1958..2017}; do
    # Loop through the GRIB files for the current year
    for grib_file in "$grib_directory$year/"anl_p125.011_tmp.${year}01_${year}12; do
        # Check if the GRIB file exists
        if [ -f "$grib_file" ]; then
            # Generate the output NetCDF filename with the same name in the output directory
            output_netcdf="$output_directory${grib_file##*/}.nc"
            
            # Convert the GRIB file to NetCDF using grib_to_netcdf
            grib_to_netcdf "$grib_file" -o "$output_netcdf" 
            
            # Optionally, you can add more commands to process the NetCDF file here.
        else
            echo "GRIB file not found for year $year: $grib_file"
        fi
    done
done
