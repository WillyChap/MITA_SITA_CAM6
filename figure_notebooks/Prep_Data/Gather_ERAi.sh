#!/bin/bash


module load eccodes 
# Path to the directory containing GRIB files
grib_directory="/glade/campaign/collections/rda/data/ds627.1/ei.moda.an.sfc/"

# Directory for the output NetCDF files
output_directory="/glade/scratch/wchapman/ERAi_regrid_out/"

# Loop through the years (from 1958 to 2017)
for year in {1979..2019}; do
    for month in {1..12}; do
        # Loop through the GRIB files for the current year
        for grib_file in "$grib_directory/"ei.moda.an.sfc.regn128sc.${year}$(printf "%02d" $month)0100; do
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
done
